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

class InstallDatabase(base.LpmsDatabase):
    def __init__(self):
        super(InstallDatabase, self).__init__()
    
    def insert_package(self, dataset, commit=False):
        # Firstly, convert Python data types to store in the SQLite3 database.
        applied_options = sqlite3.Binary(pickle.dumps(dataset.applied_options, 1))
        options = sqlite3.Binary(pickle.dumps(dataset.options, 1))

        parent = None
        if hasattr(dataset, "parent"):
            parent = dataset.parent
        
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

        self.cursor.execute('''INSERT INTO package VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, \
                ?, ?, ?, ?, ?, ?, ?)''', (None, dataset.repo, dataset.category, \
                dataset.name, dataset.version, dataset.slot, \
                dataset.summary, dataset.homepage, dataset.license, dataset.src_uri, applied_options, options, \
                dataset.arch, parent, optional_depends_build, optional_depends_runtime, optional_depends_postmerge, \
                optional_depends_conflict, static_depends_build, static_depends_runtime, static_depends_postmerge, \
                static_depends_conflict))

        if commit:
            self.commit()

    def update_package(self, dataset, commit=False):
        # Firstly, convert Python data types to store in the SQLite3 database.
        applied_options = sqlite3.Binary(pickle.dumps(dataset.applied_options, 1))
        options = sqlite3.Binary(pickle.dumps(dataset.options, 1))

        # WARNING
        parent = None
        if hasattr(dataset, "parent"):
            parent = dataset.parent
        # WARNING

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

        self.cursor.execute('''UPDATE package SET repo = (?), category = (?), name = (?), \
                version = (?), slot = (?), summary = (?), homepage = (?), license = (?), \
                src_uri = (?), applied_options = (?), options = (?), arch = (?), parent = (?), \
                optional_depends_build = (?), optional_depends_runtime = (?), optional_depends_postmerge = (?), \
                optional_depends_conflict = (?), static_depends_build = (?), static_depends_runtime = (?), \
                static_depends_postmerge = (?), static_depends_conflict = (?) WHERE id = (?)''', \
                (dataset.repo, dataset.category, \
                dataset.name, dataset.version, dataset.slot, dataset.summary, dataset.homepage, dataset.license, \
                dataset.src_uri, applied_options, options, dataset.arch, parent, optional_depends_build, \
                optional_depends_runtime, optional_depends_postmerge, optional_depends_conflict, \
                static_depends_build, static_depends_runtime, static_depends_postmerge, \
                static_depends_conflict, dataset.package_id))

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
                self.cursor.execute('''DELETE FROM package WHERE repo = (?) AND category = (?) and name = (?) and version = (?)''', (repo, category, name, version))
            elif repo is not None and category is not None and name is not None:
                self.cursor.execute('''DELETE FROM package WHERE repo = (?) AND category = (?) and name = (?)''', (repo, category, name))
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
        slot = kwargs.get("package_slot", None)
        query_body = '''
        SELECT 
            id, 
            repo, 
            category, 
            name, 
            version, 
            slot, 
            arch,
            parent,
            applied_options,
            options, 
            optional_depends_build, 
            optional_depends_runtime, 
            optional_depends_postmerge,
            optional_depends_conflict, 
            static_depends_build, 
            static_depends_runtime,
            static_depends_postmerge, 
            static_depends_conflict
        '''
        if package_id is not None:
            self.cursor.execute('''%s FROM package WHERE id = (?)''' % query_body, (package_id,))
        else:
            if repo is None and category is None and version is None:
                self.cursor.execute('''%s FROM package where name = (?)''' \
                        % query_body, (name,))
            elif slot is not None and name is not None and category is not None:
                self.cursor.execute('''%s FROM package WHERE category = (?) AND name = (?) AND slot = (?)''' \
                        % query_body, (category, name, slot))
            elif repo is not None and category is None and version is None:
                self.cursor.execute('''%s FROM package where repo = (?) and name = (?)''' \
                        % query_body, (repo, name,))
            elif repo is None and category is not None and version is None:
                self.cursor.execute('''%s FROM package where category = (?) and name = (?)''' \
                        % query_body, (category, name,))
            elif repo is None and category is None and version is not None:
                self.cursor.execute('''%s FROM package where version = (?) and name = (?)''' \
                        % query_body, (version, name,))
            elif repo is not None and category is not None and version is None:
                self.cursor.execute('''%s FROM package where repo = (?) and category = (?) and name = (?)''' \
                        % query_body, (repo, category, name,))
            elif repo is None and category is not None and version is not None:
                self.cursor.execute('''%s FROM package where version = (?) AND category = (?) AND name = (?)''' \
                        % query_body, (version, category, name,))
            elif repo is not None and category is None and version is not None:
                self.cursor.execute('''%s FROM package where version = (?) AND repo = (?) AND name = (?)''' \
                        % query_body, (version, repo, name,))
            elif repo is not None and category is not None and name is not None and version is not None:
                self.cursor.execute('''%s FROM package WHERE repo = (?) AND category = (?) AND name = (?) AND \
                        version = (?)''' % query_body, (repo, category, name, version))
        return self.cursor.fetchall()

    def get_package_metadata(self, dataset):
        if hasattr(dataset, 'package_id'):
            self.cursor.execute('''SELECT id, repo, category, name, version, slot, summary, homepage, \
                    license, src_uri, arch, options FROM package WHERE id = (?)''', (dataset.package_id,))
        else:
            self.cursor.execute('''SELECT id, repo, category, name, version, slot, summary, homepage, \
                    license, src_uri, arch, options FROM package where repo = (?) AND category = (?)  \
                    AND name = (?) AND version = (?)''', (dataset.repo, dataset.category, dataset.name, dataset.version,))
        return self.cursor.fetchone()

    def get_package_dependencies(self, package_id):
        self.cursor.execute('''SELECT optional_depends_build, optional_depends_runtime, optional_depends_postmerge, \
                        optional_depends_conflict, static_depends_build, static_depends_runtime, static_depends_postmerge, static_depends_conflict, \
                        optional_reverse_build, optional_reverse_runtime, optional_reverse_postmerge, \
                        optional_reverse_conflict, static_reverse_build, static_reverse_runtime, static_reverse_postmerge, static_reverse_conflict 
                        FROM package WHERE id = (?)''', (package_id,))
        return self.cursor.fetchone()

    def delete_build_info(self, package_id, commit=True):
        self.cursor.execute('''DELETE FROM build_info WHERE package_id = (?)''', (package_id,))
        if commit: self.commit()

    def insert_build_info(self, package_id, start_time, end_time, requestor, \
            requestor_id, host, cflags, cxxflags, ldflags, jobs, cc, cxx, commit=True):
        self.cursor.execute('''INSERT INTO build_info VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', \
                (package_id, start_time, end_time, requestor, requestor_id, host, cflags, cxxflags, \
                ldflags, jobs, cc, cxx))
        if commit: self.commit()

    def get_package_build_info(self, package_id):
        self.cursor.execute('''SELECT * FROM build_info WHERE package_id = (?)''', (package_id,))
        return self.cursor.fetchone()

    def insert_inline_options(self, package_id, target, options, commit=True):
        options = sqlite3.Binary(pickle.dumps(options, 1))
        self.cursor.execute('''INSERT INTO inline_options VALUES (?, ?, ?)''', \
                (package_id, target, options))
        if commit: self.commit()

    def update_inline_options(self, package_id, target, options, commit=True):
        options = sqlite3.Binary(pickle.dumps(options, 1))
        self.cursor.execute('''UPDATE inline_options SET options = (?) WHERE package_id = (?) AND target = (?)''', \
                (options, package_id, target))
        if commit: self.commit()

    def find_inline_options(self, package_id, target):
        if package_id is not None and target is None:
            self.cursor.execute('''SELECT * FROM inline_options WHERE package_id = (?)''', (package_id,))
        elif package_id is None and target is not None:
            self.cursor.execute('''SELECT * FROM inline_options WHERE target = (?)''', (target,))
        elif package_id is not None and target is not None:
            self.cursor.execute('''SELECT * FROM inline_options WHERE target = (?) AND package_id = (?)''', \
                    (target, package_id))
        return self.cursor.fetchall()

    def delete_inline_options(self, package_id, target, commit):
        if package_id is not None:
            self.cursor.execute('''DELETE FROM inline_options WHERE package_id = (?)''', (package_id,))
        elif target is not None:
            self.cursor.execute('''DELETE FROM inline_options WHERE target = (?)''', (target,))
        elif target is not None and package_id is not None:
            self.cursor.execute('''DELETE FROM inline_options WHERE package_id = (?) AND target = (?)''', \
                    (package_id, target))
        if commit is not None: 
            self.commit()

    def insert_conditional_versions(self, package_id, target, decision_point, commit=True):
        decision_point = sqlite3.Binary(pickle.dumps(decision_point, 1))
        self.cursor.execute('''INSERT INTO conditional_versions VALUES (?, ?, ?)''', \
                (package_id, target, decision_point))
        if commit: self.commit()

    def update_conditional_versions(self, package_id, target, decision_point, commit=True):
        decision_point = sqlite3.Binary(pickle.dumps(decision_point, 1))
        self.cursor.execute('''UPDATE conditional_versions SET decision_point = (?) WHERE package_id = (?) AND target = (?)''', \
                (decision_point, package_id, target))
        if commit: self.commit()

    def find_conditional_versions(self, package_id, target):
        if package_id is not None and target is None:
            self.cursor.execute('''SELECT * FROM conditional_versions WHERE package_id = (?)''', (package_id,))
        elif package_id is None and target is not None:
            self.cursor.execute('''SELECT * FROM conditional_versions WHERE target = (?)''', (target,))
        elif package_id is not None and target is not None:
            self.cursor.execute('''SELECT * FROM conditional_versions WHERE target = (?) AND package_id = (?)''', \
                    (target, package_id))
        return self.cursor.fetchall()

    def delete_conditional_versions(self, package_id, target, commit):
        if package_id is not None:
            self.cursor.execute('''DELETE FROM conditional_versions WHERE package_id = (?)''', (package_id,))
        elif target is not None:
            self.cursor.execute('''DELETE FROM conditional_versions WHERE target = (?)''', (target,))
        elif target is not None and package_id is not None:
            self.cursor.execute('''DELETE FROM conditional_versions  WHERE package_id = (?) AND target = (?)''', \
                    (package_id, target))
        if commit is not None: 
            self.commit()

    def get_all_packages(self):
        self.cursor.execute('''SELECT repo, category, name, version, slot FROM package''')
        return self.cursor.fetchall()

    def get_parent_package(self, category=None, name=None, version=None, package_id=None):
        if package_id is not None:
            self.cursor.execute('''SELECT parent FROM package WHERE package_id = (?)''', (package_id,))
            return self.cursor.fetchone()[0]
        self.cursor.execute('''SELECT parent FROM package WHERE category = (?) and name = (?) \
                and version = (?)''', (category, name, version))
        return self.cursor.fetchone()[0]


