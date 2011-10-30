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
from lpms.db import skel

# build_dep value is defined as 1 for runtime and post merge dependencies

class ReverseDependsDatabase(object):
    '''This class defines a database to store reverse package relations'''
    def __init__(self, db_path):
        self.db_path =  db_path
        try:
            self.connection = sqlite3.connect(self.db_path)
        except sqlite3.OperationalError:
            lpms.terminate("lpms could not connected to the database (%s)" % self.db_path)

        self.cursor = self.connection.cursor()
        table = self.cursor.execute('select * from sqlite_master where type = "table"')
        if table.fetchone() is None:
            self.initialize_db()

    def initialize_db(self):
        '''Initializes database, create the table if it does not exist'''
        tablelist = self.cursor.execute('select * from sqlite_master where type="table"')
        tablelist = self.cursor.fetchall()
        content = []
        for i in tablelist:
            content += list(i)

        # get list of tables and drop them
        for t in content:
            try:
                self.cursor.execute('drop table %s' % (t,))
            except sqlite3.OperationalError:
                # skip, can not drop table...
                continue
        self.cursor.executescript(skel.schema(self.db_path))

    def commit(self):
        '''Commits changes to database'''
        try:
            return self.connection.commit()
        except sqlite3.OperationalError as err:
            # FIXME: print error message by more convenient way
            print(err)
            lpms.terminate()

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
        self.cursor.execute('''delete item from reverse_depends where category=(?) \
                and name=(?) and version=(?)''', (category, name, version))
        if commit: self.commit()
