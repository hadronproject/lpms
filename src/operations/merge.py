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
        self.conf = conf.LPMSConfig()
        self.info_files = []
        self.previous_files = []
        self.merge_conf_data = []
        self.filesdb = api.FilesDB()
        self.file_relationsdb = api.FileRelationsDB()
        self.reverse_dependsdb = api.ReverseDependsDB()
        self.merge_conf_file = os.path.join(self.env.real_root, \
                cst.merge_conf_file)
        #self.version_data = self.instdb.get_version(self.env.name, \
        #        pkg_category = self.env.category)
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

    def is_fresh(self):
        return self.instdb.find_package(package_name=self.env.name, \
                package_category=self.env.category)

    def is_reinstall(self):
        return self.instdb.find_package(package_name=self.env.name, \
                package_category=self.env.category, package_version=self.env.version)

    def is_different(self):
        return self.is_reinstall()

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
                    if not os.path.isdir(target):
                        if os.path.isfile(target):
                            shelltools.remove_file(target)
                    else:
                        shelltools.remove_dir(target)
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
        # write metadata
        # FIXME: do we need a function called update_db or like this?
        
        installed = self.instdb.find_package(
                package_name=self.env.name, \
                        package_category=self.env.category)
        print self.env.package.get_raw_dict()
        print self.env.dependencies.get_raw_dict()
        def rmpkg(data):
            '''removes installed versions from database'''
            # last object of 'data' list is a dictonary that contains
            # versions with slot. It likes this:
            # {"0": ['0.14', '0.12'], "1": ["1.2"]}
            for key in data[-1]:
                if key == self.env.slot:
                    for ver in data[-1][key]:
                        self.instdb.remove_pkg(data[0], self.env.category, 
                                self.env.name, ver)

        if installed:
            if isinstance(installed, list):
                # remove the db entry if the package is found more than one repositories.
                for i in installed:
                    rmpkg(i)
            elif isinstance(installed, tuple):
                # remove the db entry if the package is installed from a single repository.
                rmpkg(installed)

        data =(self.env.repo, self.env.category, 
            self.env.name, self.env.version, 
            self.env.summary, self.env.homepage, 
            self.env.license, self.env.src_url, 
            " ".join(self.env.valid_opts), self.env.slot, self.env.arch)

        # FIXME: I dont like this
        if "build" in self.env.todb:
            builddeps = self.env.todb["build"]
        else:
            builddeps = []

        if "runtime" in self.env.todb:
            runtimedeps = self.env.todb["runtime"]
        else:
            runtimedeps = []

        if "postmerge" in self.env.todb:
            postmerge = self.env.todb["postmerge"]
        else:
            postmerge = []

        if "conflict" in self.env.todb:
            conflict = self.env.todb["conflict"]
        else:
            conflict = []

        # write package data to install db
        self.instdb.add_pkg(data, commit=True)
        self.instdb.add_depends((self.env.repo, self.env.category, self.env.name, 
                self.env.version, builddeps, runtimedeps, postmerge, conflict), commit=True)
        
        # write reverse dependencies
        self.reverse_dependsdb.delete_item(self.env.category, self.env.name, \
                self.env.version, commit=True)
        i = 0
        for key in (runtimedeps, builddeps, postmerge, conflict):
            i += 1
            for reverse_data in key:
                # a ugly workaround for conflicts
                if len(reverse_data) == 4:
                    # this seems a conflict
                    reverse_repo, reverse_category, reverse_name, reverse_version = reverse_data
                else:
                    # a normal dependency
                    reverse_repo, reverse_category, reverse_name, reverse_version = reverse_data[:-1]
                if i == 2:
                    self.reverse_dependsdb.add_reverse_depend((self.env.repo, self.env.category, \
                            self.env.name, self.env.version, reverse_repo, reverse_category, \
                            reverse_name, reverse_version), build_dep=0)
                else:
                    self.reverse_dependsdb.add_reverse_depend((self.env.repo, self.env.category, \
                            self.env.name, self.env.version, reverse_repo, reverse_category, \
                            reverse_name, reverse_version))
        self.reverse_dependsdb.commit()

        # write build info. flags, build time and etc.
        #self.instdb.drop_buildinfo(self.env.repo, self.env.category, self.env.name, self.env.version)
        if "HOST" in os.environ:
            host = os.environ["HOST"]
        else:
            host = ""

        if "CFLAGS" in os.environ:
            cflags = os.environ["CFLAGS"]
        else:
            cflags = ""
         
        if "CXXFLAGS" in os.environ:
            cxxflags = os.environ["CXXFLAGS"]
        else:
            cxxflags = ""

        if "LDFLAGS" in os.environ:
            ldflags = os.environ["LDFLAGS"]
        else:
            ldflags = ""

        data = (self.env.repo, self.env.category, self.env.name, self.env.version, time.time(), 
                host, cflags, cxxflags, ldflags, " ".join(self.env.valid_opts), self.total)
        self.instdb.add_buildinfo(data)

    def clean_previous(self):
        if not self.is_fresh():
            if self.is_different() or self.is_reinstall():
                obsolete = self.comparison()

                if not obsolete: return

                out.normal("cleaning obsolete content")
                dirs = []
                for item in obsolete:
                    target = os.path.join(self.env.real_root, item[0][1:])
                    if not os.path.exists(target):
                        continue
                    if os.path.islink(target):
                        os.unlink(target)
                    elif os.path.isfile(target):
                        shelltools.remove_file(target)
                    else:
                        dirs.append(target)

                dirs.reverse()
                for item in dirs:
                    if not os.listdir(item): shelltools.remove_dir(item)

    def comparison(self):
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
    
    # merge
    opr.merge_pkg()

    opr.save_merge_conf_file()

    # clean previous version if it is exists
    opr.clean_previous()

    # write to database
    #opr.write_db()

    
    # create or update /usr/share/info/dir 
    opr.update_info_index()

    if opr.backup:
        out.warn_notify("%s configuration file changed. Use %s to fix these files." % 
                (len(opr.backup), out.color("merge-conf", "red")))

    if shelltools.is_exists(cst.lock_file):
        shelltools.remove_file(cst.lock_file)
