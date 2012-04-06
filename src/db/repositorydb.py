# Copyright 2009 - 2012 Burak Sezer <purak@hadronproject.org>
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

from lpms.db import base

class RepositoryDatabase(base.LpmsDatabase):
    def __init__(self):
        super(RepositoryDatabase, self).__init__()
    
    def insert_package(self, dataset, commit=False):
        # Firstly, convert Python data types to store in the SQLite3 database.
        options = sqlite3.Binary(pickle.dumps(dataset.options, 1))
        # Optional dependencies 
        optional_depends_build = sqlite3.Binary(pickle.dumps(dataset.optional_depends_build, 1))
        optional_depends_runtime = sqlite3.Binary(pickle.dumps(dataset.optional_depends_runtime, 1))
        optional_depends_postmerge = sqlite3.Binary(pickle.dumps(dataset.optional_depends_postmerge, 1))
        optional_depends_conflict = sqlite3.Binary(pickle.dumps(dataset.optional_depends_conflict, 1))
        
        # Static dependencies
        static_depends_build = sqlite3.Binary(pickle.dumps(dataset.static_depends_build, 1))
        static_depends_runtime = sqlite3.Binary(pickle.dumps(dataset.static_depends_runtime, 1))
        static_depends_postmerge = sqlite3.Binary(pickle.dumps(dataset.static_depends_postmerge, 1))
        static_depends_conflict = sqlite3.Binary(pickle.dumps(dataset.static_depends_conflict, 1))
        
        self.cursor.execute('''INSERT INTO package VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', \
                (None,  dataset.repo, dataset.category, dataset.name, dataset.version, dataset.slot, \
                dataset.summary, dataset.homepage, dataset.license, dataset.src_uri, options, \
                dataset.arch, optional_depends_build, optional_depends_runtime, optional_depends_postmerge, \
                optional_depends_conflict, static_depends_build, static_depends_runtime, static_depends_postmerge, \
                static_depends_conflict))

        if commit:
            self.commit()

    def delete_package(self, **kwargs):
        # Set the keywords
        name = kwargs.get("package_name", None)
        package_id = kwargs.get("package_id", None)
        repo = kwargs.get("package_repo", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)
        commit = kwargs.get("commit", None)

        if package_id is not None:
            self.cursor.execute('''DELETE FROM package WHERE id = (?)''', (package_id,))
            if self.commit: self.commit()
        else:
            if repo is not None and category is not None and name is not None and version is not None:
                self.cursor.execute('''DELETE FROM package WHERE repo = (?) AND category = (?) \
                        AND name = (?) AND version = (?)''', (repo, category, name, version))
            elif repo is not None and category is not None and name is not None:
                self.cursor.execute('''DELETE FROM package WHERE repo = (?) AND category = (?) \
                        AND name = (?)''', (repo, category, name))
        if commit: self.commit()
    
    def delete_repository(self, repo, commit=False):
        self.cursor.execute('''DELETE FROM package WHERE repo = (?)''', (repo,))
        if self.commit: self.commit()

    def find_package(self, **kwargs):
        # Set the keywords
        name = kwargs.get("package_name", None)
        package_id = kwargs.get("package_id", None)
        repo = kwargs.get("package_repo", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)
        available_arches = kwargs.get("package_available_arches", None)
        
        query_body = '''SELECT id, repo, category, name, version, slot, arch, options, \
                    optional_depends_build, optional_depends_runtime, optional_depends_postmerge, \
                    optional_depends_conflict, static_depends_build, static_depends_runtime, \
                    static_depends_postmerge, static_depends_conflict'''
        
        and_arches = ""
        if available_arches is not None:
            arches = ['"'+arch+'"' for arch in available_arches]
            and_arches = '''AND arch IN %s''' % "("+", ".join(arches)+")"

        if package_id is not None:
            self.cursor.execute('''%s FROM package WHERE id = (?) %s''' % (query_body, \
                    and_arches), (package_id,))
        else:
            if repo is None and category is None and version is None:
                self.cursor.execute('''%s FROM package WHERE name = (?) %s''' \
                        % (query_body, and_arches), (name,))
            elif repo is not None and category is None and version is None:
                self.cursor.execute('''%s FROM package WHERE repo = (?) and name = (?) %s''' \
                                % (query_body, and_arches), (repo, name,))
            elif repo is None and category is not None and version is None:
                self.cursor.execute('''%s FROM package WHERE category = (?) and name = (?) %s''' \
                        % (query_body, and_arches), (category, name,))
            elif repo is None and category is None and version is not None:
                self.cursor.execute('''%s FROM package WHERE version = (?) and name = (?) %s''' \
                        % (query_body, and_arches), (version, name,))
            elif repo is not None and category is not None and version is None:
                self.cursor.execute('''%s FROM package WHERE repo = (?) and category = (?) and name = (?) %s''' \
                        % (query_body, and_arches), (repo, category, name,))
            elif repo is None and category is not None and version is not None:
                self.cursor.execute('''%s FROM package WHERE version = (?) AND category = (?) AND name = (?) %s''' \
                        % (query_body, and_arches), (version, category, name,))
            elif repo is not None and category is None and version is not None:
                self.cursor.execute('''%s FROM package WHERE version = (?) AND repo = (?) AND name = (?) %s''' \
                        % (query_body, and_arches) (version, repo, name,))
            elif repo is not None and category is not None and name is not None and version is not None:
                self.cursor.execute('''%s FROM package WHERE repo = (?) AND category = (?) AND name = (?) AND \
                        version = (?) %s''' % (query_body, and_arches), (repo, category, name, version))
        return self.cursor.fetchall()

    def get_package_metadata(self, **kwargs):
        if kwargs.get('package_id', None) is not None:
            self.cursor.execute('''SELECT id, repo, category, name, version, slot, summary, homepage, \
                    license, src_uri, arch, options FROM package WHERE id = (?)''', (kwargs['package_id'],))
        else:
            self.cursor.execute('''SELECT id, repo, category, name, version, slot, summary, homepage, \
                    license, src_uri, arch, options FROM package where repo = (?) AND category = (?)  \
                    AND name = (?) AND version = (?)''', (kwargs['repo'], kwargs['category'], \
                    kwargs['name'], kwargs['version'],))
        return self.cursor.fetchone()

    def get_package_dependencies(self, package_id):
        self.cursor.execute('''SELECT optional_depends_build, optional_depends_runtime, optional_depends_postmerge, \
                        optional_depends_conflict, static_depends_build, static_depends_runtime, \
                        static_depends_postmerge, static_depends_conflict FROM package WHERE id = (?)''', (package_id,))
        return self.cursor.fetchone()

    def get_repository_names(self):
        self.cursor.execute('''SELECT repo FROM package''')
        return list(set(self.cursor.fetchall()))

# For testing purposes
"""
db = RepositoryDatabase()

dataset = LCollect()
dataset.repo = "main"
dataset.category = "app-editors"
dataset.name = "nano"
dataset.version = "2.2.6"
dataset.slot = "0"
dataset.summary = "Pico editor clone with enhancements"
dataset.homepage = "http://www.nano-editor.org"
dataset.license = "GPL-2"
dataset.src_uri = "mirror:/hadronproject/nano-2.2.6.tar.gz"
dataset.options = ["X", "gtk", "nls", "curses"]
dataset.arch = "x86"
dataset.optional_depends_build = { 'nls': ["sys-libs/ncurses"] }
dataset.optional_depends_runtime = { 'nls': ["sys-libs/ncurses"] }
dataset.optional_depends_postmerge = {}
dataset.optional_depends_conflict = {}
dataset.static_depends_build = ["sys-libs/glibc"]
dataset.static_depends_runtime = ["sys-libs/glibc"]
dataset.static_depends_postmerge = []
dataset.static_depends_conflict = []
db.insert_package(dataset)

dataset.repo = "main"
dataset.category = "app-editors"
dataset.name = "nano"
dataset.version = "2.2.6"
dataset.slot = "0"
dataset.summary = "Pico editor clone with enhancements"
dataset.homepage = "http://www.nano-editor.org"
dataset.license = "GPL-2"
dataset.src_uri = "mirror:/hadronproject/nano-2.2.6.tar.gz"
dataset.options = ["X", "gtk", "nls", "curses"]
dataset.arch = "~x86"
dataset.optional_depends_build = { 'nls': ["sys-libs/ncurses"] }
dataset.optional_depends_runtime = { 'nls': ["sys-libs/ncurses"] }
dataset.optional_depends_postmerge = {}
dataset.optional_depends_conflict = {
dataset.static_depends_build = ["sys-libs/glibc"]
dataset.static_depends_runtime = ["sys-libs/glibc"]
dataset.static_depends_postmerge = []
dataset.static_depends_conflict = []
"""
