# Copyright 2009 - 2011 Burak Sezer <burak.sezer@linux.org.tr>
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

import sys
import glob

from lpms import singleton
from lpms import exceptions

# Based on PiSi and a Stack Overflow entry in this part
# http://stackoverflow.com/questions/31875/is-there-a-simple-elegant-way-to-define-singletons-in-python/33201#33201

class Value:   
    def __setattr__(self, name, value):
        if name in self.__dict__:
            raise exceptions.ConstError, "can't rebind constant: %s" % name
        # Binding an attribute once to a const is available
        self.__dict__[name] = value
        
    def __delattr__(self, name):
        if name in self.__dict__:
            raise exceptions.ConstError, "can't unbind constant: %s" % name
        # we don't have an attribute by this name
        raise NameError, name

class ConstantValues:
    __metaclass__ = singleton.Singleton

    val = Value()

    def __init__(self):
        # FIXME: values should be cleaned
        self.val.root = "/"
        self.val.stages = ('extract', 'prepare', 'configure', 'build', 'install', 'merge', \
                'post_install', 'post_remove', 'pre_merge', 'pre_remove')
        self.val.config_dir = "/etc/lpms"
        self.val.xmlfile_suffix = ".xml"
        self.val.lpms_path = "/usr/lib/python%s.%s/site-packages/lpms" % (sys.version_info[0], sys.version_info[1])
        self.val.logfile = "/var/log/lpms.log"
        self.val.user_dir = "/etc/lpms/user"
        self.val.user_defined_files = ('%s/lock' % self.val.user_dir, '%s/unlock' % self.val.user_dir,  \
                '%s/options' % self.val.user_dir)
        self.val.local_env_variable_files = ('%s/ldflags' % self.val.user_dir, '%s/cflags' % self.val.user_dir, \
                '%s/cxxflags' % self.val.user_dir, '%s/env' % self.val.user_dir)
        self.val.protect_file = "reserve_files.conf"
        self.val.sets_dir = "sets"
        self.val.user_sets_dir = self.val.user_dir+"/"+self.val.sets_dir
        self.val.repo_conf = "/etc/lpms/repo.conf"
        self.val.configure_pending_file = "var/tmp/configure_pending.lpms"
        self.val.merge_conf_file = "var/tmp/merge_conf_file.lpms"
        self.val.repo_file = "info/repo.conf"
        self.val.repo_info = "info"
        self.val.categories = "categories.xml"
        self.val.files_dir = "files"
        self.val.patch_suffix = ".patch"
        self.val.repos = "/var/lib/lpms"
        self.val.db_path = "/var/db/lpms"
        self.val.filesdb = "filesdb"
        self.val.repositorydb_path = "/var/db/lpms/repositorydb.db"
        self.val.reverse_dependsdb_path = "/var/db/lpms/reverse_depends.db"
        self.val.file_relationsdb_path = "/var/db/lpms/file_relationsdb.db"
        self.val.installdb_path = "/var/db/lpms/installdb.db"
        self.val.filesdb_path = "/var/db/lpms/filesdb.db"
        self.val.spec_suffix = ".py"
        self.val.sandbox_file = "sandbox.conf"
        self.val.spec_dir = "/usr/lpms"
        self.val.lpms_conf_file = "lpms.conf"
        self.val.build_conf_file = "build.conf"
        self.val.extract_dir = "/var/tmp/lpms/"
        self.val.lock_file = self.val.extract_dir+"lock"
        self.val.resume_file = "var/tmp/lpms/"+"resume"
        self.val.src_cache = "/var/cache/lpms/sources"
        self.val.news_dir = "news"
        self.val.news_read = "news.read"
        self.val.sandbox_log = '/var/log/sydbox.log'
        self.val.sandbox_app = '/usr/bin/sydbox'
        self.val.sandbox_config = '/etc/sydbox.conf'
        self.val.sandbox_paths = (self.val.extract_dir, self.val.src_cache)
        self.val.sandbox_exception_stages = ['post_install', 'post_remove', 'pre_remove', 'pre_merge']

        # lpms.conf is unhealty in this case.
        with open(self.val.config_dir+"/"+self.val.lpms_conf_file) as data:
            for line in data.readlines():
                if line.startswith("userland") and line.split("=")[1].strip() == "GNU":
                    self.val.doc = 'usr/share/doc'
                    self.val.sbin = 'usr/sbin'
                    self.val.man = 'usr/share/man'
                    self.val.info = 'usr/share/info'
                    self.val.data = 'usr/share'
                    self.val.libexec = 'usr/libexec'
                    self.val.prefix = 'usr'
                    break
                elif line.startswith("userland") and line.split("=")[1].strip() == "BSD":
                    self.val.doc = 'usr/local/share/doc'
                    self.val.sbin = 'usr/local/sbin'
                    self.val.man = 'usr/local/share/man'
                    self.val.info = 'usr/local/share/info'
                    self.val.data = 'usr/local/share'
                    self.val.libexec = 'usr/local/libexec'
                    self.val.prefix = 'usr/local'
                    break
        self.val.conf = 'etc'
        self.val.localstate = 'var'

        self.val.builtin_files = glob.glob(self.val.lpms_path+"/built-in/*.py")


    def __getattr__(self, attr):
        return getattr(self.val, attr)

    def __setattr__(self, attr, value):
        setattr(self.val, attr, value)

    def __delattr__(self, attr):
        delattr(self.val, attr)

