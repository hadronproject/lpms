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

class PackageDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        try:
            self.connection = sqlite3.connect(self.db_path)
        except sqlite3.OperationalError:
            lpms.terminate("lpms could not connected to the database(%s)" % self.db_path)

        self.cursor = self.connection.cursor()
        table = self.cursor.execute('select * from sqlite_master where type = "table"')
        if table.fetchone() is None:
            self.initialize_db()

    def initialize_db(self):
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
        return self.connection.commit()

    def get_repos(self):
        self.cursor.execute('''select repo from metadata''')
        return set(self.connection.fetchall())

    def add_pkg(self, data, commit=True):
        def get_slot():
            data = self.cursor.execute('''select version from metadata where repo=(?) and category=(?) and name=(?)''', 
                    (repo, category, name,))
            return pickle.loads(str(self.cursor.fetchone()[0]))

        repo, category, name, version, summary, homepage, _license, src_url, options, slot = data
        if not self.pkg_is_exists(repo, category, name):
            version_data = sqlite3.Binary(pickle.dumps({slot: [version]}, 1))
            self.cursor.execute('''insert into metadata values (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                repo, category, name, version_data, summary, homepage, _license, src_url, options))
        else:
            current_versions = get_slot()
            if slot in current_versions.keys():
                current_versions[slot].append(version)
            else:
                current_versions.update({slot: [version]})
            self.cursor.execute('''update metadata set version=(?) where repo=(?) and category=(?) and name=(?)''', (
                (sqlite3.Binary(pickle.dumps(current_versions, 1)), repo, category, name)))

        if commit:
            self.commit()

    def pkg_is_exists(self, repo, category, name):
        for pkg in self.find_pkg(name):
            if (repo, category, name) == pkg[:-1]:
                return True
        return False

    def find_pkg(self, name):
        self.cursor.execute('''select repo, category, name, version from metadata where name=(?)''', (name,))
        result = self.cursor.fetchall()
        if not result:
            return result
        return [(repo, category, name, pickle.loads(str(version))) for repo, category, name, version in result]
    
    def get_metadata(self, keyword, repo, category, name):
        self.cursor.execute('''select %s from metadata where repo=(?) and category=(?) and name=(?)''' 
                % keyword, (repo, category, name,))
        return self.cursor.fetchone()

    def get_all_names(self, repo=None):
        if repo is not None:
            self.cursor.execute('''select repo, category, name from metadata where repo=(?)''', (repo,))
        else:
            self.cursor.execute('''select repo, category, name from metadata''')
        return self.cursor.fetchall()

    def drop(self, rname, category=None, name=None, version=None):
        # FIXME: Use executescript
        def drop_others():
            self.cursor.execute('''delete from build_info where repo=(?) and category=(?) and name=(?) and version=(?)''', 
                    (rname, category, name, version,))
            #self.cursor.execute('''delete from depends where repo=(?) and category=(?) and name=(?) and version=(?)''', 
            ##        (rname, category, name, version,))

        if category is None and name is None and version is None:
            self.cursor.execute('''delete from metadata where repo=(?)''', (rname,))
            self.cursor.execute('''delete from depends where repo=(?)''', (rname,))
        else:
            for pkg in self.find_pkg(name):
                irepo, icategory, iname, iversion = pkg
                # FIXME: This is no good!
                if (irepo, icategory, iname) == (rname, category, name):
                    for key in iversion.keys():
                        if version in iversion[key]:
                            iversion[key].remove(version)
                    
                    versions = []
                    map(lambda x: versions.extend(x), iversion.values())
                    
                    if len(versions) >= 1:
                        #result = versions
                        #result.remove(version); new_version = " ".join(result)
                        self.cursor.execute('''update metadata set version=(?) where repo=(?) and category=(?) and name=(?)''', 
                                (sqlite3.Binary(pickle.dumps(iversion, 1)), rname, category, name,))
                        drop_others()
                        break
                    elif not versions:
                        self.cursor.execute('''delete from metadata where repo=(?) and category=(?) and name=(?)''', 
                            (rname, category, name,))
                        drop_others()
        self.commit()

    def add_buildinfo(self, data):
        repo, category, name, version, build_time, hosts, cflags, cxxflags, ldflags, applied, size = data
        self.cursor.execute('''insert into build_info values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                repo, category, name, version, build_time, hosts, cflags, cxxflags, ldflags, applied, size))
        self.commit()

    def drop_buildinfo(self, repo, category, name, version):
        self.cursor.execute('''delete from build_info where repo=(?) and category=(?) and name=(?) and version=(?)''', 
                (repo, category, name, version,))
        self.commit()

    def add_depends(self, data, commit=True):
        repo_name, category, name, version, build, runtime = data
        if not self.get_depends(repo_name, category, name, version) is not None:
            self.cursor.execute('''insert into depends values (?, ?, ?, ?, ?, ?)''', 
                    (repo_name, category, name, version,
                    sqlite3.Binary(pickle.dumps(build, 1)),
                    sqlite3.Binary(pickle.dumps(runtime, 1))
                    ))
        if commit:
            self.commit()

    def get_buildinfo(self, repo, category, name, version):
        self.cursor.execute('''select * from build_info where repo=(?) and category=(?) and name=(?) and version=(?)''', 
                (repo, category, name, version,))
        return self.cursor.fetchone()

    def get_depends(self, repo_name, category, name, version=None):
        data = self.cursor.execute('''select * from depends where repo=(?) and category=(?) and name=(?)''', 
                (repo_name, category, name,))
        if version is not None:
            data = self.cursor.execute('''select * from depends where repo=(?) and category=(?) and name=(?) and version=(?)''', (
                    repo_name, category, name, version,))

        for deps in data:
            result = {'build': pickle.loads(str(deps[4])),
                    'runtime': pickle.loads(str(deps[5]))}
            return result

    #def get_slot(self, repo, name, category, version):
    #    self.cursor.execute('''select slot from metadata where repo=(?) and category=(?) and name=(?) and version=(?)''', 
    #            (repo, category, name, version,))
    #    return pickle.loads(str(self.cursor.fetchone()[0]))
    
    def get_version(self, repo, name, category):
        self.cursor.execute('''select version from metadata where repo=(?) and category=(?) and name=(?)''', 
                (repo, category, name,))
        result = self.cursor.fetchall()
        if not result:
            return None
        return pickle.loads(str(result[0][0]))
