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
import cPickle as pickle

import lpms
from lpms.db import skel
from lpms.exceptions import NoSize

class FilesDatabase(object):
    '''This class defines a database to store files from packages'''
    def __init__(self, db_path):
        self.db_path = db_path
        try:
            self.connection = sqlite3.connect(self.db_path)
        except sqlite3.OperationalError:
            lpms.terminate("lpms could not connected to the database (%s)" % self.db_path)

        self.cursor = self.connection.cursor()
        table = self.cursor.execute('select * from sqlite_master where type = "table"')
        if table.fetchone() is None:
            self.initialize_db()
        self.query = []

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

    def insert_query(self, commit=False):
        '''Inserts query items'''
        self.cursor.execute('BEGIN TRANSACTION')
        for data in self.query:
            repo, category, name, version, path, _type, \
                    size, gid, mod, uid, sha1sum, realpath, slot  = data
            #FIXME:temporary fix for utf-8
            path = path.decode('utf-8')
            realpath = path.decode('utf-8')
            self.cursor.execute('''insert into files values(?, ?, ?, ?, ?, ?, \
                    ?, ?, ?, ?, ?, ?, ?)''', (repo, category, name, version, path, _type, \
                    sqlite3.Binary(pickle.dumps(size, 1)), gid, mod, uid, sha1sum, realpath, slot))
        del self.query
        self.query = []
        if commit: self.commit()

    def append_query(self, data):
        '''Appends given path with given data to query'''
        self.query.append(data)

    def get_files_and_links(self):
        '''Gets all fiels and links in the files database'''
        self.cursor.execute('''select category, name, slot, version, path from files where type="file" or type="link"''')
        return self.cursor.fetchall()

    def get_package_by_path(self, path):
        '''Gets package data by the path'''
        self.cursor.execute('''select repo, category, name, version from \
                files where path=(?)''', (path,))
        return self.cursor.fetchall()

    def get_type_by_path(self, path):
        '''Gets item type by the path'''
        self.cursor.execute('''select type from files where path=(?)''', (path,))
        return self.cursor.fetchall()

    def get_perms_by_path(self, path):
        '''Gets permissions of the path'''
        self.cursor.execute('''select gid, mod, uid from files where path=(?)''',
                (path,))
        return self.cursor.fetchall()

    def get_size_by_path(self, path):
        '''Get size of path'''
        self.cursor.execute('''select size from files where type='file' and path=(?)''', (path,))
        size = self.cursor.fetchall()
        if not size:
            raise NoSize("no size. %s is a directory or symlink" % path)
        return size

    def get_dirs_by_package(self, category, name, version):
        '''Gets directories of the package'''
        self.cursor.execute('''select path from files where type="dir" and category=(?) \
                and name=(?) and version=(?)''', (category, name, version,))
        return self.cursor.fetchall()

    def get_files_and_links_by_package(self, category, name, version):
        '''Gets files and links of the package'''
        self.cursor.execute('''select path from files where (type="file" or type="link") and category=(?) \
                and name=(?) and version=(?)''', (category, name, version,))
        return self.cursor.fetchall()

    def get_files_by_package(self, category, name, version):
        '''Gets files of the package'''
        self.cursor.execute('''select path from files where type="file" and category=(?) \
                and name=(?) and version=(?)''', (category, name, version,))
        return self.cursor.fetchall()

    def get_links_by_package(self, category, name, version):
        '''Gets links of the package'''
        self.cursor.execute('''select path from files where type="link" and category=(?) \
                and name=(?) and version=(?)''', (category, name, version,))
        return self.cursor.fetchall()

    def get_sha1sum_by_path(self, path):
        '''Gets sha1sum of path'''
        self.cursor.execute('''select sha1sum from files where path=(?)''',
                (path,))
        return self.cursor.fetchall()

    def get_paths_by_package(self, name, repo=None, category=None, version=None):
        '''Gets paths by package name'''
        if repo is None and category is None:
            self.cursor.execute('''select path from files where name=(?)''', (name,))
        elif category is None and repo is not None:
            self.cursor.execute('''select path from files where name=(?) and \
                    repo=(?)''', (name, repo,))
        elif category is not None and repo is None:
            if version is None:
                self.cursor.execute('''select path from files where name=(?) and \
                        category=(?)''', (name, category,))
            else:
                self.cursor.execute('''select path from files where name=(?) and \
                        category=(?) and version=(?)''', (name, category, version,))
        else:
            if version is None:
                self.cursor.execute('''select path from files where repo=(?) and \
                        name=(?) and category=(?)''', (repo, name, category,))
            else:
                self.cursor.execute('''select path from files where repo=(?) and \
                        name=(?) and category=(?) and version=(?)''', (repo, name, category, version,))
        return self.cursor.fetchall()
    
    def delete_item_by_pkgdata_and_path(self, pkgdata, path, commit=False):
        '''Deletes item by package data and path'''
        category, name, version = pkgdata
        self.cursor.execute('''delete from files where \
                category=(?) and name=(?) and version=(?) and path=(?)''',
                (category, name, version, path,))
        if commit: self.commit()

    def delete_item_by_pkgdata(self, category, name, version, commit=False):
        '''Deletes item by package data'''
        self.cursor.execute('''delete from files where \
                category=(?) and name=(?) and version=(?)''',
                (category, name, version,))
        if commit: self.commit()

    def delete_item_by_path(self, path, commit=False):
        '''Deletes item by file path'''
        self.cursor.execute('''delete from files where path=(?)''',
                (path,))
        if commit: self.commit()
