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
from lpms.db import filesdb

installdb = dbapi.InstallDB()

def main(pkgname):
    pkgdata = installdb.find_pkg(pkgname)

    if not pkgdata:
        out.error("%s not installed." % pkgname)
        lpms.terminate()
    
    for pkg in pkgdata:
        repo, category, name, version_data =  pkg
        
        versions = []
        map(lambda x: versions.extend(x), version_data.values())

        for version in versions:
            # create the filesdb object.
            fdb = filesdb.FilesDB(repo, category, 
                    name, version, "/")
            # load the content file
            fdb.import_xml()

            out.normal("%s/%s/%s-%s" % (repo, category, name, version))

            def press(tag):
                # the content file a bit dirty
                data = fdb.content[tag]
                if tag == "dirs":
                    data = data[1:]

                for path in data:
                    if os.path.islink(path):
                        print("%s -> %s" % (path, os.path.realpath(path)))
                    else:
                        print(path)

            for tag in ('dirs', 'file'):
                press(tag)
