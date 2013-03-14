# Copyright 2009 - 2011 Burak Sezer <purak@hadronproject.org>
# 
# This file is part of lpms
#  
# lpms is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#   
# lpms is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#   
# You should have received a copy of the GNU General Public License
# along with lpms.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
import gzip
import shutil
import shelve

import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import internals
from lpms import shelltools
from lpms import file_relations
from lpms import constants as cst

from lpms.db import api

class Merge(object):
    '''
    This class performs merge operation and creates database entries for the package
    '''
    def __init__(self, environment):
        self.symlinks = []
        self.backup = []
        self.environment = environment
        self.instdb = api.InstallDB()
        self.repodb = api.RepositoryDB()
        self.conf = conf.LPMSConfig()
        self.info_files = []
        self.previous_files = []
        self.filesdb = api.FilesDB()
        self.file_relationsdb = api.FileRelationsDB()
        self.reverse_dependsdb = api.ReverseDependsDB()
        self.binary_filetypes = ('application/x-executable', 'application/x-archive', \
                'application/x-sharedlib')
        self.merge_conf_file = os.path.join(self.environment.real_root, \
                cst.merge_conf_file)
        self.previous_files = self.filesdb.get_paths_by_package(self.environment.name, \
                repo=self.environment.repo, category=self.environment.category, \
                version=self.environment.previous_version)
        # Unfortunately, this seems very ugly :(
        self.strip_debug_symbols = True if self.environment.no_strip is not None and \
                ((self.environment.applied_options is not None and \
                "debug" in self.env.applied_options) or \
                utils.check_cflags("-g") or utils.check_cflags("-ggdb") \
                or utils.check_cflags("-g3")) else False

    def append_merge_conf(self, item):
        '''Handles merge-conf file'''
        try:
            if not os.access(self.merge_conf_file, os.F_OK) \
                    or os.access(self.merge_conf_file, os.R_OK):
                        self.merge_conf_data = shelve.open(self.merge_conf_file)
            else:
                # TODO: We should develop a message system for warning the user 
                out.error("%s seems not readable." % self.merge_conf_file)
                out.error("Merge process is going to proceed but you must handle configuration files manually.")
                out.error("Please check this file for merging: %s" % item)
                return

            package = str(os.path.join(self.environment.category, self.environment.name, \
                    self.environment.version)+":"+self.environment.slot)
            if package in self.merge_conf_data:
                self.merge_conf_data[package].add(item)
            else:
                self.merge_conf_data[package] = set([item])
        finally:
            self.merge_conf_data.close()

    def is_parent_symlink(self, target):
        for symlink in self.symlinks:
            if target.startswith(symlink):
                return True

    def append_filesdb(self, _type, target, perms, **kwargs):
        '''Executes a filesdb query for adding items to files database'''
        sha1sum = kwargs.get("sha1sum", None)
        size = kwargs.get("size", None)
        realpath = kwargs.get("realpath", None)
        if _type in ("dir", "file"):
            gid, mod, uid  = perms['gid'], perms['mod'], perms['uid']
        elif _type == "link":
            gid, mod, uid = None, None, None
        self.filesdb.append_query(
                (self.environment.repo,
                    self.environment.category,
                    self.environment.name,
                    self.environment.version,
                    target,
                    _type,
                    size,
                    gid,
                    mod,
                    uid,
                    sha1sum,
                    realpath,
                    self.environment.slot
                )
        )

    def merge_package(self):
        '''Moves files to the target destination in the most safest way.'''
        def get_perms(path):
            '''Get permissions of given path, it may be file or directory'''
            return {"uid": utils.get_uid(path),
                    "gid": utils.get_gid(path),
                    "mod": utils.get_mod(path)
            }
        out.normal("%s/%s/%s-%s:%s is merging to %s" % (self.environment.repo, self.environment.category, \
                self.environment.name, self.environment.version, self.environment.slot, \
                self.environment.real_root))
        # Remove files db entries for this package:slot if it exists
        self.filesdb.delete_item_by_pkgdata(self.environment.category, self.environment.name, \
            self.environment.previous_version, commit=True)

        # Remove file_relations db entries for this package:slot if it exists
        self.file_relationsdb.delete_item_by_pkgdata(self.environment.category, \
                self.environment.name, self.environment.previous_version, commit=True)

        # Merge the package, now
        walk_iter = os.walk(self.environment.install_dir, followlinks=True)
        while True:
            try:
                parent, directories, files = next(walk_iter)
                # TODO: Check the target path's permissions for writing or reading
                # Remove install_dir from parent to get real parent path
                pruned_parent = parent.replace(self.environment.install_dir, "")
                # create directories
                for directory in directories:
                    source = os.path.join(parent, directory)
                    target = os.path.join(self.environment.real_root, pruned_parent, directory)
                    real_target = "/".join([pruned_parent, directory])
                    if self.is_parent_symlink(target):
                        break
                    if os.path.islink(source):
                        self.symlinks.append(target+"/")
                        realpath = os.path.realpath(source)
                        if os.path.islink(target):
                            shelltools.remove_file(target)
                        # create real directory
                        if len(realpath.split(self.environment.install_dir)) > 1:
                            realpath = realpath.split(self.environment.install_dir)[1][1:]

                        shelltools.makedirs(os.path.join(self.environment.real_root, realpath))
                        # make symlink
                        if os.path.isdir(target):
                            shelltools.remove_dir(target)
                        elif os.path.isfile(target):
                            shelltools.remove_file(target)
                        shelltools.make_symlink(os.readlink(source), target)
                    else:
                        if os.path.isfile(target):
                            # TODO: Rename this file and warn the user
                            shelltools.remove_file(target)
                        shelltools.makedirs(target)
                    # Get permissions
                    perms = get_perms(source)
                    # if path is a symlink, pass permission mumbo-jumbos
                    if not os.path.islink(source):
                        # Set permissions
                        shelltools.set_id(target, perms["uid"], perms["gid"])
                        shelltools.set_mod(target, perms["mod"])
                        # TODO: Common items?
                        # Add the item to filesdb
                        self.append_filesdb("dir", real_target, perms)
                    else:
                        # Add the item to filesdb
                        self.append_filesdb("link", real_target, perms, \
                                realpath=os.path.realpath(source))

                # Merge regular files to the target
                # Firstly, handle reserved files
                reserve_files = []
                if self.environment.reserve_files:
                    if isinstance(self.environment.reserve_files, basestring):
                        reserve_files.extend([f_item for f_item in self.environment.reserve_files.split(" ") \
                                if f_item != ""])
                    elif isinstance(self.environment.reserve_files, list) or isinstance(self.environment.reserve_files, tuple):
                        reserve_files.extend(self.environment.reserve_files)

                if os.path.isfile(os.path.join(cst.user_dir, cst.protect_file)):
                    with open(os.path.join(cst.user_dir, cst.protect_file)) as data:
                        for rf in data.readlines():
                            if not rf.startswith("#"):
                                reserve_files.append(rf.strip())

                # Here we are starting to merge
                for _file in files:
                    source = os.path.join(parent, _file)
                    target = os.path.join(self.environment.real_root, pruned_parent, _file)
                    real_target = "/".join([pruned_parent, _file])
                    if self.is_parent_symlink(target):
                        break
                    # Keep file relations for using after to handle reverse dependencies
                    if os.path.exists(source) and os.access(source, os.X_OK):
                        if utils.get_mimetype(source) in self.binary_filetypes:
                            self.file_relationsdb.append_query((
                                self.environment.repo,
                                self.environment.category,
                                self.environment.name,
                                self.environment.version,
                                target,
                                file_relations.get_depends(source))
                            )
                    # Strip binary files and keep them smaller
                    if self.strip_debug_symbols and utils.get_mimetype(source) in self.binary_filetypes:
                        utils.run_strip(source)
                    if self.environment.ignore_reserve_files:
                        reserve_files = []
                        self.environment.reserve_files = True

                    def add_file_item():
                        # Prevent code duplication
                        if not os.path.islink(target):
                            shelltools.set_id(target, perms["uid"], perms["gid"])
                            shelltools.set_mod(target, perms["mod"])
                            self.append_filesdb("file", real_target, perms, \
                                    sha1sum=utils.sha1sum(target),
                                    size = utils.get_size(source, dec=True)
                            )
                        else:
                            self.append_filesdb("link", real_target, perms,\
                                    realpath=os.path.realpath(source))

                    if self.environment.reserve_files is not False:
                        conf_file = os.path.join(pruned_parent, _file)
                        isconf = (_file.endswith(".conf") or _file.endswith(".cfg"))
                        def is_reserve():
                            if self.environment.ignore_reserve_files:
                                return False
                            elif not conf_file in reserve_files:
                                return False
                            return True

                        if os.path.exists(target) and not is_reserve():
                            if pruned_parent[0:4] == "/etc" or isconf:
                                if os.path.isfile(conf_file) and utils.sha1sum(source) != utils.sha1sum(conf_file):
                                    self.append_merge_conf(conf_file)
                                    target = target+".lpms-backup" 
                                    self.backup.append(target)

                        if os.path.exists(target) and is_reserve():
                            # The file is reserved.
                            # Adds to filesdb
                            add_file_item()
                            # We don't need the following operations
                            continue

                    if os.path.islink(source):
                        sha1 = False
                        realpath = os.readlink(source)
                        if self.environment.install_dir in realpath:
                            realpath = realpath.split(self.environment.install_dir)[1]

                        if os.path.isdir(target):
                            shelltools.remove_dir(target)
                        elif os.path.isfile(target) or os.path.islink(target):
                            shelltools.remove_file(target)
                        shelltools.make_symlink(realpath, target)
                    else:
                        sha1 = utils.sha1sum(source)
                        perms = get_perms(source)
                        shelltools.move(source, target)
                    # Adds to filesdb
                    add_file_item()
            except StopIteration as err:
                break

        self.file_relationsdb.insert_query(commit=True)
        self.filesdb.insert_query(commit=True)

        lpms.logger.info("%s/%s has been merged to %s." % (self.environment.category, self.environment.fullname, \
                self.environment.real_root))
        
    def write_db(self):
        '''Updates package data in the database or create a new entry'''
        if self.environment.dependencies is not None:
            for keyword in self.environment.dependencies:
                setattr(self.environment.package, keyword, self.environment.dependencies[keyword])

        package_metadata = self.repodb.get_package_metadata(package_id=self.environment.package.id)
        self.environment.package.applied_options = self.environment.applied_options
        for item in ('homepage', 'summary', 'license', 'src_uri'):
            setattr(self.environment.package, item, getattr(package_metadata, item))
        
        installed_package = self.instdb.find_package(
                package_name=self.environment.name,
                package_category=self.environment.category,
                package_slot=self.environment.slot
        )
        
        if installed_package:
            package_id = self.environment.package.package_id = installed_package.get(0).id
            self.instdb.update_package(self.environment.package, commit=True)
        else:
            self.instdb.insert_package(self.environment.package, commit=True)
            package_id = self.instdb.find_package(
                    package_repo=self.environment.package.repo,
                    package_category=self.environment.package.category,
                    package_name=self.environment.package.name,
                    package_version=self.environment.package.version
            ).get(0).id

        # Create or update inline_options table entries.
        if self.environment.inline_option_targets is not None:
            for target in self.environment.inline_option_targets:
                if self.instdb.find_inline_options(package_id=package_id, target=target):
                    self.instdb.update_inline_options(package_id, target, \
                            self.environment.inline_option_targets[target])
                else:
                    self.instdb.insert_inline_options(package_id, target, \
                            self.environment.inline_option_targets[target])

        # Create or update conditional_versions table entries.
        if self.environment.conditional_versions is not None:
            for decision_point in self.environment.conditional_versions:
                target = decision_point["target"]
                del decision_point["target"]
                if not self.instdb.find_conditional_versions(package_id=package_id, target=target):
                    self.instdb.insert_conditional_versions(package_id, target, \
                            decision_point)
                else:
                    self.instdb.update_conditional_versions(package_id, target, \
                            decision_point)

        self.instdb.database.delete_build_info(package_id)
        
        # requestor values are temporary
        # TODO: requestor and related fields are going to be removed 
        requestor = os.getenv("USER")
        requestor_id = os.getuid()
        end_time = time.time()
        host = os.environ["HOST"] if "HOST" in os.environ else ""
        cflags = os.environ["CFLAGS"] if "CFLAGS" in os.environ else ""
        cxxflags = os.environ["CXXFLAGS"] if "CXXFLAGS" in os.environ else ""
        ldflags = os.environ["LDFLAGS"] if "LDFLAGS" in os.environ else "" 
        jobs = os.environ["JOBS"] if "JOBS" in os.environ else ""
        cc = os.environ["CC"] if "CC" in os.environ else ""
        cxx = os.environ["CXX"] if "CXX" in os.environ else ""
        self.instdb.database.insert_build_info(
                package_id, 
                self.environment.start_time,
                end_time,
                requestor,
                requestor_id,
                host,
                cflags,
                cxxflags,
                ldflags,
                jobs,
                cc,
                cxx,
        )

    def clean_obsolete_content(self):
        '''Cleans obsolete content which belogs to previous installs'''
        if self.instdb.find_package(package_name=self.environment.name, \
                package_category=self.environment.category,
                package_slot=self.environment.slot):
            obsolete = self.compare_different_versions()
            if not obsolete:
                return
            out.normal("cleaning obsolete content")
            directories = []
            for item in obsolete:
                target = os.path.join(self.environment.real_root, item[0][1:])
                if not os.path.exists(target):
                    continue
                if os.path.islink(target):
                    os.unlink(target)
                elif os.path.isfile(target):
                    shelltools.remove_file(target)
                else:
                    directories.append(target)

            directories.reverse()
            for directory in directories:
                if not os.listdir(directory):
                    # Remove directory if it does not include anything
                    shelltools.remove_dir(directory)

    def compare_different_versions(self):
        '''Compares file lists of different installations of the same package and finds obsolete content'''
        current_files = self.filesdb.get_paths_by_package(self.environment.name, \
                        repo=self.environment.repo, category=self.environment.category, version=self.environment.version)
        obsolete = []
        for item in self.previous_files:
            if not item in current_files:
                obsolete.append(item)
        return obsolete

    def create_info_archive(self):
        info_path = os.path.join(self.environment.install_dir, cst.info)
        if not os.path.isdir(info_path): return
        for item in os.listdir(os.path.join(self.environment.install_dir, cst.info)):
            info_file = os.path.join(info_path, item)
            with open(info_file, 'rb') as content:
                with gzip.open(info_file+".gz", 'wb') as output:
                    output.writelines(content)
                    self.info_files.append(os.path.join(self.environment.real_root, cst.info, item)+".gz")
            shelltools.remove_file(info_file)

    def update_info_index(self):
        for info_file in self.info_files:
            if os.path.exists(info_file):
                utils.update_info_index(info_file)

    def perform_operation(self):
        # create $info_file_name.gz archive and remove info file
        self.create_info_archive()
        # merge the package
        self.merge_package()
        # clean the previous version if it is exists
        self.clean_obsolete_content()
        # write to database
        self.write_db()
        # create or update /usr/share/info/dir 
        self.update_info_index()

        if self.backup:
            out.write("%s%s configuration file changed. Use %s to fix these files.\n" % 
                    (out.color(" > ", "green"), len(self.backup), \
                            out.color("merge-conf", "red")))

        if shelltools.is_exists(cst.lock_file):
            shelltools.remove_file(cst.lock_file)
