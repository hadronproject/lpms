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
from lpms.db import dbapi

# Initial version of upgrade operation

class UpgradeSystem(object):
    def __init__(self):
        self.upgrade_pkg = []
        self.notfound_pkg = []
        self.packages = []
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()

    def select_pkgs(self):
        for pkg in self.instdb.get_all_names():
            repo, category, name = pkg
            
            # catch packages which is from the outside
            if not self.repodb.find_pkg(name, pkg_category = category):
                self.notfound_pkg.append((category, name))

            # get version data from repository database
            repovers = self.repodb.get_version(name, repo, category)

            # comparise versions
            for slot, instver in self.instdb.get_version(name, repo, category).items():
                # a slot must inclue single version for installed packages database.
                # But get_version method returns a dict and instver is a list.
                # Hence, I used instver[0] in the code.
                if not repovers or not slot in repovers:
                    continue

                best = utils.best_version(repovers[slot])
                result = utils.vercmp(best, instver[0]) 

                if result != 0:
                    self.packages.append(os.path.join(repo, category, name,))

        if self.notfound_pkg:
            out.write("%s: the following packages were installed but they could not be found in the database:\n\n" 
                    % out.color("WARNING", "brightyellow"))
            for pkg in self.notfound_pkg:
                category, name = pkg
                out.notify("%s/%s\n" % (category, name))
            out.write("\n")
