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
from lpms.db import dbapi

class ListFiles:
    def __init__(self, pkgname):
        self.pkgname = pkgname
        self.filesdb = dbapi.FilesDB()
        self.installdb = dbapi.InstallDB()

    def usage(self):
        out.normal("Lists files of the given package")
        out.write("no extra command found.\n")
        lpms.terminate()

    def main(self):
        if lpms.getopt("--help"):
            self.usage()

        pkgdata = self.installdb.find_pkg(self.pkgname)

        if not pkgdata:
            out.error("%s not installed." % self.pkgname)
            lpms.terminate()
        
        for pkg in pkgdata:
            repo, cat, name, version_data =  pkg
            
            versions = []
            map(lambda x: versions.extend(x), version_data.values())

            for ver in versions:
                out.normal("%s/%s/%s-%s" % (repo, cat, name, ver))

                content = self.filesdb.get_paths_by_package(name, category=cat, version=ver)
                for item in content:
                    item = item[0]
                    if os.path.islink(item):
                        print("%s -> %s" % (item, os.path.realpath(item)))
                    else:
                        print(item)
