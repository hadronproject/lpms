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

class FileRelationsDatabase(object):
    '''This class defines a database to store shared library and executable file relations'''
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
            print(err)
            lpms.terminate()

    def add_file(self, data, commit=False):
        '''Adds the file with its package data and depends'''
        repo, category, name, version, file_path, depends = data
        for depend in depends:
            self.cursor.execute('''insert into file_relations values(?, ?, ?, ?, ?, ?)''', (
                repo, category, name, version, file_path, depend,))
        if commit: self.commit()

    def get_package_by_depend(self, depend):
        '''Gets package data by depend'''
        self.cursor.execute('''select repo, category, name, version from \
                file_relations where depend=(?)''', (depend,))
        return self.cursor.fetchall()

    def get_package_by_file_path(self, file_path):
        '''Gets package data by file path'''
        self.cursor.execute('''select repo, category, name, version from \
                file_relations where file_path=(?)''', (file_path,))
        return self.cursor.fetchall()
    
    def delete_item_by_pkgdata(self, pkgdata, commit=False):
        '''Deletes item by package data'''
        repo, category, name, version = pkgdata
        self.cursor.execute('''delete from file_relations where repo=(?) and \
                category=(?) and name=(?) and version=(?)''',
                (repo, category, name, version,))
        if commit: self.commit()

    def delete_item_by_file_path(self, file_path, commit=False):
        '''Deletes item by file path'''
        self.cursor.execute('''delete from file_relations where file_path=(?)''',
                (file_path,))
        if commit: self.commit()

    def delete_item_by_depend(self, depend, commit=False):
        '''Deletes item by depend'''
        self.cursor.execute('''delete from file_relations where depend=(?)''',
                (depend,))
        if commit: self.commit()

