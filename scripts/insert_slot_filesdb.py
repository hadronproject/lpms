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

import sys
import sqlite3
from lpms.db import dbapi
from lpms.db import filesdb

def insert_slot():
    installdb = dbapi.InstallDB()
    fdb = filesdb.FilesDatabase("/var/db/lpms/filesdb.db")
    try:
        fdb.cursor.execute("ALTER TABLE files ADD slot text")
    except sqlite3.OperationalError:
        pass
    packages = installdb.get_all_names()
    for package in packages:
        repo, category, name = package
        version_data = installdb.get_version(name, repo_name = \
                repo, pkg_category=category)
        for slot in version_data:
            print(category, name, slot, version_data[slot][0])
            fdb.cursor.execute('UPDATE files SET slot=(?) WHERE category=(?) \
                    and name=(?) and version=(?)', (slot, category, name, version_data[slot][0]))
    fdb.commit()

if "-h" in sys.argv or "--help" in sys.argv:
    print("this script adds slot column to filesdb")
else:
    insert_slot()

