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

from lpms.db import api as dbapi

# Initial version of upgrade operation

class UpgradeSystem(object):
    def __init__(self):
        self.upgrade_pkg = []
        self.notfound_pkg = []
        self.packages = []
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()
        self.locked_packages = {}
        lock_file = os.path.join(cst.user_dir, "lock")
        if os.access(lock_file, os.R_OK):
            with open(lock_file) as data:
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
        for pkg in self.instdb.get_all_packages():
            self.repo, self.category, self.name, self.version, self.slot = pkg
            # catch packages which are from the outside
            if not self.repodb.find_package(package_name=self.name, \
                    package_category=self.category):
                if not (self.category, self.name) in self.notfound_pkg:
                    self.notfound_pkg.append((self.category, self.name))

            # get version data from repository database
            repository_items = self.repodb.find_package(package_name=self.name, \
                    package_category=self.category)
            if not repository_items:
                # if the installed package could not found in the repository database
                # add the item to not-founds list
                self.notfound_pkg.append((self.category, self.name))
                continue

            # collect available package version by slot value
            available_versions = {}
            for item in repository_items:
                if item.slot in available_versions:
                    available_versions[item.slot].append(item.version)
                else:
                    available_versions[item.slot] = [item.version]

            # comparise versions
            for item in repository_items:
                if item.slot == self.slot:
                    best_version = utils.best_version(available_versions[item.slot])
                    result = utils.vercmp(best_version, self.version)
                    if result != 0:
                        self.packages.append(os.path.join(self.category, self.name)+":"+self.slot)
                        break

        if self.notfound_pkg:
            out.write("%s: the following packages were installed but they could not be found in the database:\n\n" 
                    % out.color("WARNING", "brightyellow"))
            for no_category, no_name, in self.notfound_pkg:
                out.notify("%s/%s" % (no_category, no_name))
            out.write("\n")

