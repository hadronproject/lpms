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

    def add_reverse_depend(self, package_id, reverse_package_id, \
            build_dependency=1, commit=False):
        '''Saves reverse dependency item for the given package'''
        self.cursor.execute('''INSERT InTO reverse_depends \
                values(?, ?, ?, ?)''', (None, package_id, reverse_package_id, \
                build_dependency))
        if commit: self.commit()

    def get_reverse_depends(self, package_id):
        '''Gets reverse depends of the given package'''
        self.cursor.execute('''SELECT * FROM reverse_depends WHERE package_id = (?)''', \
                (package_id,))
        return self.cursor.fetchall()

    def get_package_by_reverse_depend(self, reverse_package_id):
        '''Gets package by the reverse depend'''
        self.cursor.execute('''SELECT * FROM reverse_depends WHERE package_id=(?)''', \
                ((reverse_package_id,)))
        self.cursor.fetchall()

    def delete_item(self, package_id, commit=False):
        '''Deletes all items that added by the given item'''
        self.cursor.execute('''DELETE FROM reverse_depends WHERE package_id=(?)''', (package_id,))
        if commit: self.commit()
