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
import cPickle as pickle

import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import internals
from lpms import shelltools
from lpms import file_relations
from lpms import constants as cst

from lpms.db import api

class Merge(internals.InternalFuncs):
    '''Main class for package installation'''
    def __init__(self, environment):
        # Do I need this?
        super(Merge, self).__init__()
        self.total = 0
        self.myfile = None
        self.filesdb_path = None
        self.versions = []
        self.symlinks = []
        self.backup = []
        self.env = environment
        self.instdb = api.InstallDB()
        self.repodb = api.RepositoryDB()
        self.conf = conf.LPMSConfig()
        self.info_files = []
        self.previous_files = []
        self.merge_conf_data = []
        self.filesdb = api.FilesDB()
        self.file_relationsdb = api.FileRelationsDB()
        self.reverse_dependsdb = api.ReverseDependsDB()
        self.merge_conf_file = os.path.join(self.env.real_root, \
                cst.merge_conf_file)
        self.previous_files = self.filesdb.get_paths_by_package(self.env.name, \
                repo=self.env.repo, category=self.env.category, \
                version=self.env.previous_version)

    def load_merge_conf_file(self):
        if os.path.isfile(self.merge_conf_file):
            with open(self.merge_conf_file, "rb") as raw_data:
                try:
                    self.merge_conf_data = pickle.load(raw_data)
                except EOFError:
                    shelltools.remove_file(self.merge_conf_file)

    def save_merge_conf_file(self):
        if self.merge_conf_data and os.path.isfile(self.merge_conf_file):
            shelltools.remove_file(self.merge_conf_file)

        if self.merge_conf_data:
            with open(self.merge_conf_file, "wb") as raw_data:
                pickle.dump(self.merge_conf_data, raw_data)

    def is_parent_symlink(self, target):
        for symlink in self.symlinks:
            if target.startswith(symlink):
                return True

    def merge_pkg(self):
        '''Merge the package to the system'''
        isstrip = True
        if (hasattr(self.env, "no_strip") and self.env.no_strip) or lpms.getopt("--no-strip") \
                or (self.env.applied_options is not None and "debug" in self.env.applied_options)\
                or utils.check_cflags("-g") \
                or utils.check_cflags("-ggdb") or utils.check_cflags("-g3"):
                    isstrip = False

        def get_perms(path):
            '''Get permissions of given path, it may be file or directory'''
            return {"uid": utils.get_uid(path),
                    "gid": utils.get_gid(path),
                    "mod": utils.get_mod(path)
            }


        self.filesdb.delete_item_by_pkgdata(self.env.category, self.env.name, \
            self.env.previous_version, commit=True)

        out.notify("merging the package to %s and creating database entries..." % self.env.real_root)
        
        self.file_relationsdb.delete_item_by_pkgdata(self.env.category, \
                self.env.name, self.env.previous_version, commit=True)
        # find content of the package
        for root_path, dirs, files in os.walk(self.env.install_dir, followlinks=True):
            root_path = root_path.split(self.env.install_dir)[1]

            # create directories
            for d in dirs:
                source = os.path.join(self.env.install_dir, root_path[1:], d)
                target = os.path.join(self.env.real_root, root_path[1:], d)
                
                real_target = "/".join([root_path, d])
                if self.is_parent_symlink(target): break

                if os.path.islink(source):
                    self.symlinks.append(target+"/")
                    realpath = os.path.realpath(source)
                    if os.path.islink(target):
                        shelltools.remove_file(target)
                    # create real directory
                    if len(realpath.split(self.env.install_dir)) > 1:
                        realpath = realpath.split(self.env.install_dir)[1][1:]

                    shelltools.makedirs(os.path.join(self.env.real_root, realpath))
                    # make symlink
                    if os.path.isdir(target):
                        shelltools.remove_dir(target)
                    elif os.path.isfile(target):
                        shelltools.remove_file(target)
                    shelltools.make_symlink(os.readlink(source), target)
                else:
                    if os.path.isfile(target):
                        shelltools.remove_file(target)
                    shelltools.makedirs(target)

                perms = get_perms(source)

                # if path is a symlink, pass permission mumbo-jumbos
                if not os.path.islink(source):
                    shelltools.set_id(target, perms["uid"], perms["gid"])
                    shelltools.set_mod(target, perms["mod"])

                    self.filesdb.append_query(
                            (self.env.repo, 
                                self.env.category, 
                                self.env.name,
                                self.env.version, 
                                real_target, 
                                "dir", 
                                None, 
                                perms['gid'],
                                perms['mod'], 
                                perms['uid'], 
                                None, 
                                None,
                                self.env.slot
                            )
                    )
                else:
                    self.filesdb.append_query(
                            (self.env.repo, 
                                self.env.category, 
                                self.env.name,
                                self.env.version, 
                                real_target, 
                                "link", 
                                None, 
                                None,
                                None, 
                                None, 
                                None, 
                                os.path.realpath(source),
                                self.env.slot
                            )
                    )


            # write regular files
            reserve_files = []
            if self.env.reserve_files:
                if isinstance(self.env.reserve_files, basestring):
                    reserve_files.extend([f for f in self.env.reserve_files.split(" ") \
                            if f != ""])
                elif isinstance(self.env.reserve_files, list) or isinstance(self.env.reserve_files, tuple):
                    reserve_files.extend(self.env.reserve_files)

            if os.path.isfile(os.path.join(cst.user_dir, cst.protect_file)):
                with open(os.path.join(cst.user_dir, cst.protect_file)) as data:
                    for rf in data.readlines():
                        if not rf.startswith("#"):
                            reserve_files.append(rf.strip())

            for f in files:
                source = os.path.join(self.env.install_dir, root_path[1:], f)
                target = os.path.join(self.env.real_root, root_path[1:], f)
                real_target = "/".join([root_path, f])
                
                if self.is_parent_symlink(target): break
                
                if os.path.exists(source) and os.access(source, os.X_OK):
                    if utils.get_mimetype(source) in ('application/x-executable', 'application/x-archive', \
                            'application/x-sharedlib'):
                        self.file_relationsdb.append_query((self.env.repo, self.env.category, self.env.name, \
                                        self.env.version, target, file_relations.get_depends(source)))
            
                # strip binary files
                if isstrip and utils.get_mimetype(source) in ('application/x-executable', 'application/x-archive', \
                        'application/x-sharedlib'):
                    utils.run_strip(source)

                if lpms.getopt("--ignore-reserve-files"):
                    reserve_files = []
                    self.env.reserve_files = True

                if self.env.reserve_files is not False:
                    conf_file = os.path.join(root_path, f)
                    isconf = (f.endswith(".conf") or f.endswith(".cfg"))
                    def is_reserve():
                        if lpms.getopt("--ignore-reserve-files"):
                            return False
                        elif not conf_file in reserve_files:
                            return False
                        return True

                    if os.path.exists(target) and not is_reserve():
                        if root_path[0:4] == "/etc" or isconf:
                            if os.path.isfile(conf_file) and utils.sha1sum(source) != utils.sha1sum(conf_file):
                                if not conf_file in self.merge_conf_data:
                                    self.merge_conf_data.append(conf_file)

                                target = target+".lpms-backup" 
                                self.backup.append(target)
                                
                    if os.path.exists(target) and is_reserve():
                        #FIXME: Code duplication!!!
                        # the file is reserved.
                        if not os.path.islink(target):
                            shelltools.set_id(target, perms["uid"], perms["gid"])
                            shelltools.set_mod(target, perms["mod"])
                            
                            sha1sum = utils.sha1sum(target)
                            self.filesdb.append_query(
                                    (self.env.repo, 
                                        self.env.category, 
                                        self.env.name,
                                        self.env.version, 
                                        real_target,
                                        "file", 
                                        utils.get_size(source, dec=True), 
                                        perms['gid'],
                                        perms['mod'], 
                                        perms['uid'], 
                                        sha1sum, 
                                        None,
                                        self.env.slot
                                    )
                            )
                        else:
                            self.filesdb.append_query(
                                    (self.env.repo, 
                                        self.env.category, 
                                        self.env.name,
                                        self.env.version, 
                                        real_target, 
                                        "link", 
                                        None, 
                                        None,
                                        None, 
                                        None, 
                                        None, 
                                        os.path.realpath(path),
                                        self.env.slot
                                    )
                            )
                        # We don't need the following operations
                        continue

                if os.path.islink(source):
                    sha1sum = False
                    realpath = os.readlink(source)
                    if self.env.install_dir in realpath:
                        realpath = realpath.split(self.env.install_dir)[1]

                    if os.path.isdir(target):
                        shelltools.remove_dir(target)
                    elif os.path.isfile(target) or os.path.islink(target):
                        shelltools.remove_file(target)
                    shelltools.make_symlink(realpath, target)
                else:
                    sha1sum = utils.sha1sum(source)
                    perms = get_perms(source)
                    shelltools.move(source, target)

                #FIXME: Code duplication!!!

                if not os.path.islink(source):
                    shelltools.set_id(target, perms["uid"], perms["gid"])
                    shelltools.set_mod(target, perms["mod"])

                    self.filesdb.append_query(
                            (self.env.repo, 
                                self.env.category, 
                                self.env.name,
                                self.env.version, 
                                real_target, 
                                "file", 
                                utils.get_size(source, dec=True), 
                                perms['gid'],
                                perms['mod'], 
                                perms['uid'], 
                                sha1sum, 
                                None,
                                self.env.slot
                            )
                    )
                else:
                    self.filesdb.append_query(
                            (self.env.repo, 
                                self.env.category, 
                                self.env.name,
                                self.env.version, 
                                real_target, 
                                "link", 
                                None, 
                                None,
                                None, 
                                None, 
                                None, 
                                os.path.realpath(source),
                                self.env.slot
                            )
                    )

        self.file_relationsdb.insert_query(commit=True)
        self.filesdb.insert_query(commit=True)

        lpms.logger.info("%s/%s merged to %s" % (self.env.category, self.env.fullname, \
                self.env.real_root))
        
    def write_db(self):
        '''Update package data in the database or create a new entry'''
        if self.env.dependencies is not None:
            for keyword in self.env.dependencies:
                setattr(self.env.package, keyword, self.env.dependencies[keyword])

        package_metadata = self.repodb.get_package_metadata(package_id=self.env.package.id)
        self.env.package.applied_options = self.env.applied_options
        for item in ('homepage', 'summary', 'license', 'src_uri'):
            setattr(self.env.package, item, getattr(package_metadata, item))
        
        installed_package = self.instdb.find_package(
                package_name=self.env.name,
                package_category=self.env.category,
                package_slot=self.env.slot
        )
        
        if installed_package:
            package_id = self.env.package.package_id = installed_package.get(0).id
            self.instdb.update_package(self.env.package, commit=True)
        else:
            self.instdb.insert_package(self.env.package, commit=True)
            package_id = self.instdb.find_package(
                    package_repo=self.env.package.repo,
                    package_category=self.env.package.category,
                    package_name=self.env.package.name,
                    package_version=self.env.package.version
            ).get(0).id

        # Create or update inline_options table entries.
        if hasattr(self.env, "inline_option_targets"):
            for target in self.env.inline_option_targets:
                if self.instdb.find_inline_options(package_id=package_id, target=target):
                    self.instdb.update_inline_options(package_id, target, \
                            self.env.inline_option_targets[target])
                else:
                    self.instdb.insert_inline_options(package_id, target, \
                            self.env.inline_option_targets[target])

        # Create or update conditional_versions table entries.
        if hasattr(self.env, "conditional_versions"):
            for decision_point in self.env.conditional_versions:
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
                self.env.start_time,
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
        if self.instdb.find_package(package_name=self.env.name, \
                package_category=self.env.category):
            obsolete = self.compare_different_versions()
            if not obsolete:
                return
            out.normal("cleaning obsolete content")
            directories = []
            for item in obsolete:
                target = os.path.join(self.env.real_root, item[0][1:])
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
        current_files = self.filesdb.get_paths_by_package(self.env.name, \
                        repo=self.env.repo, category=self.env.category, version=self.env.version)
        obsolete = []
        for item in self.previous_files:
            if not item in current_files:
                obsolete.append(item)
        return obsolete

    def create_info_archive(self):
        info_path = os.path.join(self.env.install_dir, cst.info)
        if not os.path.isdir(info_path): return
        for item in os.listdir(os.path.join(self.env.install_dir, cst.info)):
            info_file = os.path.join(info_path, item)
            with open(info_file, 'rb') as content:
                with gzip.open(info_file+".gz", 'wb') as output:
                    output.writelines(content)
                    self.info_files.append(os.path.join(self.env.real_root, cst.info, item)+".gz")
            shelltools.remove_file(info_file)

    def update_info_index(self):
        for info_file in self.info_files:
            if os.path.exists(info_file):
                utils.update_info_index(info_file)

def main(environment):
    opr = Merge(environment)

    opr.load_merge_conf_file()

    # create $info_file_name.gz archive and remove info file
    opr.create_info_archive()

    # merge the package
    opr.merge_pkg()

    opr.save_merge_conf_file()

    # clean the previous version if it is exists
    opr.clean_obsolete_content()

    # write to database
    opr.write_db()


    # create or update /usr/share/info/dir 
    opr.update_info_index()

    if opr.backup:
        out.warn_notify("%s configuration file changed. Use %s to fix these files." % 
                (len(opr.backup), out.color("merge-conf", "red")))

    if shelltools.is_exists(cst.lock_file):
        shelltools.remove_file(cst.lock_file)
