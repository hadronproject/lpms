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

from lpms.db import dbapi

filesdb = dbapi.FilesDB()
installdb = dbapi.InstallDB()

cmdline = sys.argv

if "--help" in cmdline:
    out.normal("A tool that to create reverse depends database from scratch.")
    out.write("To hide outputs use '--quiet' parameter.\n")

if "--quiet" in cmdline:
    out.normal("creating reverse depends database...") 

if os.path.exists("/var/db/lpms/reverse_depends.db"):
    shelltools.remove_file("/var/db/lpms/reverse_depends.db")

reversedb = dbapi.ReverseDependsDB()

for package in installdb.get_all_names():
    reverse_repo, reverse_category, reverse_name = package
    versions = []
    map(lambda ver: versions.extend(ver), installdb.get_version(reverse_name, pkg_category=reverse_category).values())
    for reverse_version in versions:
        depends = installdb.get_depends(reverse_repo, reverse_category, reverse_name, reverse_version)
        if not depends:
            print package, depends
            continue
        for dep in depends["runtime"]:
            if len(dep) != 5:
                continue
            repo, category, name, version = dep[:-1]
            reversedb.add_reverse_depend((repo, category, name, version, \
                    reverse_repo, reverse_category, reverse_name, reverse_version))
        for dep in depends["postmerge"]:
            if len(dep) != 5:
                continue
            repo, category, name, version = dep[:-1]
            reversedb.add_reverse_depend((repo, category, name, version, \
                    reverse_repo, reverse_category, reverse_name, reverse_version))
        
        for dep in depends["build"]:
            if len(dep) != 5:
                continue
            repo, category, name, version = dep[:-1]
            reversedb.add_reverse_depend((repo, category, name, version, \
                    reverse_repo, reverse_category, reverse_name, reverse_version), build_dep=0)

reversedb.commit()
out.write("OK\n")
