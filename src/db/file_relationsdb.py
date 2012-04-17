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

class FileRelationsDatabase(base.LpmsDatabase):
    '''This class defines a database to store shared library and executable file relations'''
    def __init__(self):
        super(FileRelationsDatabase, self).__init__()
        self.query = []

    def insert_query(self, commit=True):
        '''Inserts query'''
        self.cursor.execute('BEGIN TRANSACTION')
        for data in self.query:
            repo, category, name, version, file_path, depends = data
            for depend in depends:
                self.cursor.execute('''insert into file_relations values(?, ?, ?, ?, ?, ?)''', (
                    repo, category, name, version, file_path, depend,))
        del self.query
        self.query = []
        if commit: self.commit()

    def append_query(self, data):
        '''Appends the file with its package data and depends to query'''
        self.query.append(data)

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

    def get_file_paths_by_package(self, name, repo=None, category=None, version=None):
        '''Gets file_paths by package name'''
        if repo is None and category is None:
            self.cursor.execute('''select file_path from file_relations where name=(?)''', (name,))
        elif category is None and repo is not None:
            self.cursor.execute('''select file_path from file_relations where name=(?) and \
                    repo=(?)''', (name, repo,))
        elif category is not None and repo is None:
            if version is None:
                self.cursor.execute('''select file_path from file_relations where name=(?) and \
                        category=(?)''', (name, category,))
            else:
                self.cursor.execute('''select file_path from file_relations where name=(?) and \
                        category=(?) and version=(?)''', (name, category, version,))
        else:
            if version is None:
                self.cursor.execute('''select file_path from file_relations where repo=(?) and \
                        name=(?) and category=(?)''', (repo, name, category,))
            else:
                self.cursor.execute('''select file_path from file_relations where repo=(?) and \
                        name=(?) and category=(?) and version=(?)''', (repo, name, category, version,))
        return self.cursor.fetchall()
    
    def delete_item_by_pkgdata_and_file_path(self, pkgdata, file_path, commit=False):
        '''Deletes item by package data and file_path'''
        category, name, version = pkgdata
        self.cursor.execute('''delete from file_relations where \
                category=(?) and name=(?) and version=(?) and file_path=(?)''',
                (category, name, version, file_path,))
        if commit: self.commit()

    def delete_item_by_pkgdata(self, category, name, version, commit=False):
        '''Deletes item by package data'''
        self.cursor.execute('''delete from file_relations where \
                category=(?) and name=(?) and version=(?)''',
                (category, name, version,))
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

