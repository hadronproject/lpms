#!/usr/bin/env python
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
import sys

from lpms import out
from lpms import utils
from lpms import shelltools
from lpms import file_relations

from lpms.db import dbapi

filesdb = dbapi.FilesDB()
installdb = dbapi.InstallDB()

cmdline = sys.argv

if "--help" in cmdline:
    out.normal("A tool that to create file relations database from scratch.")
    out.write("To hide outputs use '--quiet' parameter.\n")

if "--quiet" in cmdline:
    out.normal("creating file relations database...") 

if os.path.exists("/var/db/lpms/file_relations.db"):
    shelltools.remove_file("/var/db/lpms/file_relations.db")

relationsdb = dbapi.FileRelationsDB()

for package in installdb.get_all_names():
    repo, category, name = package
    versions = []
    map(lambda ver: versions.extend(ver), installdb.get_version(name, pkg_category=category).values())
    for version in versions:
        content = filesdb.list_files(category, name, version)
        for file_path in content["file"]:
            if os.path.exists(file_path) and os.access(file_path, os.X_OK):
                if utils.get_mimetype(file_path) in ('application/x-executable', 'application/x-archive', \
                        'application/x-sharedlib'):
                    if not "--quiet" in cmdline:
                        out.green("%s/%s/%s/%s\n" % (repo, category, name, version))
                        out.write("\t"+file_path+"\n")
                    relationsdb.add_file((repo, category, name, version, file_path, file_relations.get_depends(file_path)))

relationsdb.commit()
out.write("OK\n")
