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

import sqlite3

import lpms
from lpms.db import base

# build_dep value is defined as 1 for runtime and post merge dependencies

class ReverseDependsDatabase(base.LpmsDatabase):
    '''This class defines a database to store reverse package relations'''
    def __init__(self):
        super(ReverseDependsDatabase, self).__init__()

    def add_reverse_depend(self, data, build_dep=1, commit=False):
        '''Registers reverse depend item for given package'''
        repo, category, name, version = data[:4]
        reverse_repo, reverse_category, reverse_name, \
                reverse_version = data[4:]
        self.cursor.execute('''insert into reverse_depends \
                values(?, ?, ?, ?, ?, ?, ?, ?, ?)''', (repo, category, \
                name, version, reverse_repo, reverse_category, \
                reverse_name, reverse_version, build_dep))
        if commit: self.commit()

    def get_reverse_depends(self, category, name, version=None):
        '''Gets reverse depends of given package'''
        if version:
            self.cursor.execute('''select reverse_repo, reverse_category, \
                    reverse_name, reverse_version from reverse_depends where \
                    category=(?) and name=(?) and version=(?) and build_dep=1''', (category, \
                    name, version,))
        else:
            self.cursor.execute('''select reverse_repo, reverse_category, \
                    reverse_name, reverse_version from reverse_depends where \
                    category=(?) and name=(?) and build_dep=1''', (category, \
                    name))
        return self.cursor.fetchall()

    def get_package_by_reverse_depend(self, reverse_category, \
            reverse_name, reverse_version):
        '''Gets package by reverse depend'''
        self.cursor.execute('''select repo, category, version from reverse_depends \
                where reverse_category=(?) and reverse_name=(?) and \
                reverse_version=(?) and build_dep=1''',
                (category, name, version,))
        self.cursor.fetchall()

    def delete_item(self, category, name, version, commit=False):
        '''Deletes all entries of given item'''
        self.cursor.execute('''delete from reverse_depends where category=(?) and name=(?) and version=(?)''', (category, name, version,))
        if commit: self.commit()
