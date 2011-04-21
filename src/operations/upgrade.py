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


import lpms

from lpms import out
from lpms import utils
from lpms.db import dbapi

# Initial version of upgrade operation

class UpgradeSystem(object):
    def __init__(self):
        self.upgrade_pkg = []
        self.notfound_pkg = []
        self.downgrade_pkg = []
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()

    def select_pkgs(self):
        for pkg in self.instdb.get_all_names():
            repo, category, name = pkg
            
            # catch packages which is from the outside
            if not self.repodb.find_pkg(name, repo, category):
                self.notfound.append((repo, category, name))

            # get version data from repository database
            repovers = self.repodb.get_version(name, repo, category)
            
            # comparise versions
            for slot, instver in self.instdb.get_version(name, repo, category).items():
                # a slot must inclue single version for installed packages database.
                # But get_version method returns a dict and instver is a list.
                # Hence, I used instver[0] in the code.
                best = utils.best_version(repovers[slot])
                if utils.vercmp(best, instver[0]) == 1:
                    self.upgrade_pkg.append((repo, category, name, best, instver[0]))
                elif utils.vercmp(best, instver[0]) == -1:
                    self.downgrade_pkg.append((repo, category, name, best, instver[0]))

    def show_result(self):
        # show results to user
        if not self.upgrade_pkg and not self.downgrade_pkg:
            out.write("no upgrade found.\n")
            return

        if self.upgrade_pkg:
            out.normal("the following packages will be upgraded:")
            for pkg in self.upgrade_pkg:
                repo, category, name, newver, oldver = pkg
                out.write(" %s/%s/%s-%s -> %s\n" % (repo, category, out.color(name, "brightwhite"), 
                    out.color(oldver, "red"), out.color(newver, "brightgreen")))
            out.write("\n")

        if self.downgrade_pkg:
            out.normal("the following packages will be downgraded:")
            for pkg in self.downgrade_pkg:
                repo, category, name, newver, curver = pkg
                out.write(" %s/%s/%s-%s -> %s\n" % (repo, category, out.color(name, "brightwhite"), 
                    out.color(curver, "red"), out.color(newver, "brightgreen")))
            out.write("\n")

        if self.notfound_pkg:
            out.write("%s: the following packages were installed but they could not be found in the database:" 
                    % out.color("WARNING", "brightyellow"))
            for pkg in self.notfound_pkg:
                repo, category, name, version = pkg
                out.write(" %s/%s/%s-%s\n" % (repo, category, name, version))
            out.write("\n")
