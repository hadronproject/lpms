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
from lpms.db import api

class ListFiles:
    def __init__(self, pkgname):
        self.pkgname = pkgname
        self.filesdb = api.FilesDB()
        self.instdb = api.InstallDB()

    def main(self):
        parsed = self.pkgname.split("/")
        if len(parsed) == 3:
            repo, category, name = parsed
            name, version = utils.parse_pkgname(name)
            packages = self.instdb.find_package(
                    package_repo=repo,
                    package_category=category,
                    package_name=name,
                    package_version=version
                    )
        elif len(parsed) == 2:
            category, name = parsed
            name, version = utils.parse_pkgname(name)
            packages = self.instdb.find_package(
                    package_category=category,
                    package_name=name,
                    package_version=version
                    )
        elif len(parsed) == 1:
            name, version = utils.parse_pkgname(self.pkgname)
            packages = self.instdb.find_package(
                    package_name=name,
                    package_version=version
                    )
        else:
            out.error("%s could not be recognized." % self.pkgname)
            lpms.terminate()

        if not packages:
            out.error("%s not installed." % self.pkgname)
            lpms.terminate()
        
        for package in packages:        
            symdirs = {}
            out.normal("%s/%s/%s-%s" % (package.repo, package.category, \
                    package.name, package.version))
            content = self.filesdb.get_paths_by_package(package.name, \
                    category=package.category, version=package.version)
            for item in content:
                item = item[0]
                if os.path.islink(item):
                    out.write("%s -> %s\n" % (out.color(item, "green"), os.readlink(item)))
                    if os.path.isdir(os.path.realpath(item)):
                        symdirs[os.path.realpath(item)+"/"] = item+"/"
                else:
                    out.write(item+"\n")
                if symdirs:
                    for symdir in symdirs:
                        if item.startswith(symdir):
                            out.write("%s -> %s\n" % (out.color(item.replace(symdir, \
                                    symdirs[symdir]), "brightwhite"), out.color(item, "brightwhite")))
