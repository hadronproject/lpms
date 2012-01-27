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

import lpms

from lpms import out
from lpms import utils
from lpms import constants as cst

from lpms.db import dbapi

# Initial version of upgrade operation

class UpgradeSystem(object):
    def __init__(self):
        self.upgrade_pkg = []
        self.notfound_pkg = []
        self.packages = []
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()
        self.locked_packages = {}
        with open(os.path.join(cst.user_dir, "lock")) as data:
            for line in data.readlines():
                lock_category, lock_name, lock_version = utils.parse_user_defined_file(line.strip(), \
                        self.repodb)
                key= lock_category+"/"+lock_name
                if key in self.locked_packages:
                    if isinstance(lock_version, list):
                        self.locked_packages[key].extend(lock_version)
                    else:
                        self.locked_packages[key].append(lock_version)
                else:
                    if isinstance(lock_version, list):
                        self.locked_packages[key] = lock_version
                    else:
                        self.locked_packages[key] = [lock_version]

    def filter_locked_packages(self, repovers):
        if not self.category+"/"+self.name in self.locked_packages:
            return repovers

        lock_versions = self.locked_packages[self.category+"/"+self.name]

        filtered_repovers = {}
        for slot in repovers:
            result = []
            for version in repovers[slot]:
                if not version in lock_versions:
                    result.append(version)
            if result:
                filtered_repovers[slot] = result
        return filtered_repovers

    def select_pkgs(self):
        for pkg in self.instdb.get_all_names():
            self.repo, self.category, self.name = pkg
            # catch packages which are from the outside
            if not self.repodb.find_pkg(self.name, pkg_category = self.category):
                self.notfound_pkg.append((self.category, self.name))

            # get version data from repository database
            data =  self.repodb.find_pkg(self.name, pkg_category = self.category, selection=True)
            if not data:
                continue
            
            # FIXME: this hack will be fixed in new database version
            if isinstance(data, list):
                repovers = self.filter_locked_packages(data[0][-1])
            else:
                repovers = self.filter_locked_packages(data[-1])

            # if repovers is a empty dict, the package is locked
            if not repovers: continue
            
            # comparise versions
            for slot, instver in self.instdb.get_version(self.name, self.repo, self.category).items():
                # a slot must inclue single version for installed packages database.
                # But get_version method returns a dict and instver is a list.
                # Hence, I used instver[0] in the code.
                if not repovers or not slot in repovers:
                    continue
                best = utils.best_version(repovers[slot])
                result = utils.vercmp(best, instver[0]) 

                if result != 0:
                    self.packages.append(os.path.join(self.category, self.name)+":"+slot)

        if self.notfound_pkg:
            out.write("%s: the following packages were installed but they could not be found in the database:\n\n" 
                    % out.color("WARNING", "brightyellow"))
            for pkg in self.notfound_pkg:
                no_category, no_name = pkg
                out.notify("%s/%s" % (no_category, no_name))
            out.write("\n")
