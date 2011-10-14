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

import os
import sys

from lpms import utils
from lpms import constants as const

from lpms.db import db
from lpms.db import filesdb

from lpms.exceptions import NotInstalled

class FilesAPI(object):
    '''This class defines a simple abstraction layer for files database'''
    def __init__(self, real_root=None, suffix=None):
        self.instdb = InstallDB()
        self.real_root = real_root 
        self.suffix = suffix

    def cursor(self, repo, category, name, version):
        '''Connects files database'''
        self.repo = repo; self.category = category
        self.name = name; self.version = version
        filesdb_obj = filesdb.FilesDB(repo, category, name, \
                version, self.real_root, self.suffix)
        filesdb_obj.import_xml()
        return filesdb_obj

    def is_installed(self, repo, category, name, version):
        '''Checks package status'''
        result = self.instdb.get_version(name, pkg_category=category, \
                repo_name=repo)
        if result:
            for slot in result:
                if version in result[slot]:
                    return True
        return False

    def get_package(self, path):
        '''Returns package name or package names for the given path'''
        result = []
        for package in self.instdb.get_all_names():
            repo, category, name = package
            raw_versions = self.instdb.get_version(name, pkg_category=category, \
                    repo_name=repo)
            versions = []
            map(lambda ver: versions.extend(ver), raw_versions.values())
            for version in versions:
                filesdb_cursor = self.cursor(repo, category, \
                        name, version)
                if filesdb_cursor.has_path(path):
                    del filesdb_cursor
                    if not (repo, category, name, version) in result:
                        result.append((repo, category, name, version))
        if result:
            return result
        return False

    def list_files(self, repo, category, name, version):
        '''Returns content for the given package'''
        if not self.is_installed(repo, category, name, version):
            raise NotInstalled("%s/%s/%s-%s is not installed." % (repo, category, name, version))
        filesdb_cursor = self.cursor(repo, category, name, version)
        return filesdb_cursor.content

    def has_path(self, repo, category, name, version, path):
        '''Checks given package for given path'''
        if not self.is_installed(repo, category, name, version):
            raise NotInstalled("%s/%s/%s-%s is not installed." % (repo, category, name, version))
        filesdb_cursor = self.cursor(repo, category, name, version)
        return filesdb_cursor.has_path(path)

class API(object):
    def __init__(self, db_path):
        self.db = db.PackageDatabase(db_path)

    def invalid_repos(self):
        valid_repos = utils.valid_repos()
        invalids = []
        for repo in self.get_repos():
            if not repo[0] in valid_repos:
                invalids.append(repo[0])
        return invalids

    def find_pkg(self, pkgname, repo_name = None, pkg_category = None, 
            selection=False):
        package = []
        result = self.db.find_pkg(pkgname)
        if repo_name is None and pkg_category is None:
            if len(result) > 1 and selection:
                return utils.pkg_selection_dialog(result)
            return result
        elif repo_name is not None and pkg_category is None:
            for repo, category, name, version in result:
                if repo_name == repo:
                    package.append((repo, category, name, version))
        elif repo_name is None and pkg_category is not None:
            for repo, category, name, version in result:
                if pkg_category == category:
                    package.append((repo, category, name, version))
        elif repo_name is not None and pkg_category is not None:
            for repo, category, name, version in result:
                if repo_name == repo and pkg_category == category:
                    package.append((repo, category, name, version))
        
        if len(package) > 1 and selection:
            return utils.pkg_selection_dialog(package)

        if len(package) == 1:
            return package[0]

        return package

    def commit(self):
        return self.db.commit()

    def get_all_names(self, repo = None):
        return self.db.get_all_names(repo)

    def get_buildinfo(self, repo, category, name, version):
        return self.db.get_buildinfo(repo, category, name, version)

    def get_repos(self):
        return self.db.get_repos()

    def add_pkg(self, data, commit=False):
        return self.db.add_pkg(data, commit)

    def add_buildinfo(self, data):
        return self.db.add_buildinfo(data)

    def drop_buildinfo(self, repo, category, name, version):
        return self.db.drop_buildinfo(repo, category, name, version)

    def drop_repo(self, repo_name):
        return self.db.drop(repo_name)

    def remove_pkg(self, repo_name, category, pkgname, version):
        return self.db.drop(repo_name, category, pkgname, version)

    def get_category(self, pkgname, repo_name = None):
        result = self.db.find_pkg(pkgname)
        if repo_name is None:
            return result[1]
        else:
            if result[0] == repo_name:
                return result[1]

    def get_from_metadata(self, x, pkgname, repo_name = None, pkg_category = None):
        packages = self.db.find_pkg(pkgname); result = []
        if repo_name is None and pkg_category is None:
            for repo, category, pkgname, version in packages:
                result.append(self.db.get_metadata(x, repo, category, pkgname))
            return result

        elif repo_name is not None and pkg_category is None:
            for repo, category, pkgname, version in packages:
                if repo_name == repo:
                    result.append(self.db.get_metadata(x, repo, category, pkgname))
            return result

        elif repo_name is None and pkg_category is not None:
            for repo, category, pkgname, version in packages:
                if pkg_category == category:
                    result.append(self.db.get_metadata(x, repo, category, pkgname))
            return result

        elif repo_name is not None and pkg_category is not None:
            for repo, category, pkgname, version in packages:
                if repo_name == repo and pkg_category == category:
                    return self.db.get_metadata(x, repo, category, pkgname)

    def get_summary(self, pkgname, repo_name = None, pkg_category = None):
        return self.get_from_metadata("summary", pkgname, repo_name, pkg_category)
    
    def get_homepage(self, pkgname, repo_name = None, pkg_category = None):
        return self.get_from_metadata("homepage", pkgname, repo_name, pkg_category)
    
    def get_src_url(self, pkgname, repo_name = None, pkg_category = None):
        return self.get_from_metadata("src_url", pkgname, repo_name, pkg_category)
    
    def get_license(self, pkgname, repo_name = None, pkg_category = None):
        return self.get_from_metadata("license", pkgname, repo_name, pkg_category)
    
    def get_version(self, pkgname, repo_name = None, pkg_category = None):
        # FIXME: get_version function db.py seems buggy
        versions = {}

        result =  self.find_pkg(pkgname, repo_name, pkg_category)
        if isinstance(result, tuple):
            result = [result]

        for pkg in result:
            repovers = pkg[-1]
            for slot in repovers:
                if not slot in versions:
                    versions.update({slot: repovers[slot]})
                else:
                    for ver in repovers[slot]:
                        if not ver in versions[slot]:
                            versions[slot].append(ver)
        return versions

        #return self.db.get_version(pkgname, repo_name, pkg_category)

    def get_options(self, repo_name, pkgname, pkg_category):
        #FIXME: get_repos returns a list sometimes if the package 
        # installed from a unavaiable repository.
        if not repo_name:
            return
        elif isinstance(repo_name, list):
            # we use the first item of the list for this db version.
            repo_name = repo_name[0]

        return self.db.get_options(repo_name, pkgname, pkg_category)

    def get_slot(self, pkgname, pkg_category, pkg_version):
        return self.db.get_slot(pkgname, pkg_category, pkg_version)

    def add_depends(self, data, commit=False):
        return self.db.add_depends(data, commit)

    def get_depends(self, repo_name, category, pkgname, version=None):
        return self.db.get_depends(repo_name, category, pkgname, version)

    def get_arch(self, repo_name, category, pkgname, version = None):
        return self.db.get_arch(repo_name, category, pkgname, version)

    def get_repo(self, category, pkgname, version = None):
        valid_repos = utils.valid_repos()
        for repo in valid_repos:
            raw_result = self.find_pkg(pkgname, repo_name = repo, \
                    pkg_category = category)
            if raw_result:
                if version:
                    versions = []
                    map(lambda v: versions.extend(v), self.get_version(pkgname, \
                            repo_name = repo, pkg_category = category).values())
                    if version in versions:
                        return repo
                else:
                    return repo

        # if the package installed but repository is not available,
        # api runs this block.
        # if the package is not installed, returns a empty list.
        repos = []
        for repo in self.get_repos():
            if not repo in valid_repos:
                # repo is a tuple in (u'hebelek',) format.
                # i will fuck lpms database in the near future.
                repo = repo[0]
                raw_result = self.find_pkg(pkgname, repo_name = repo,
                        pkg_category = category)
                if raw_result:
                    if version:
                        versions = []
                        map(lambda v: versions.extend(v), self.get_version(pkgname, \
                                pkg_category = category).values())
                        if version in versions:
                            return repo
                    repos.append(repo)
        return repos

def fix_path(path):
    for arg in sys.argv:
        if arg.startswith("--change-root"):
            dbpath = os.path.join(arg.split("=")[1], path[1:])
            if not os.path.isdir(os.path.dirname(dbpath)):
                os.makedirs(os.path.dirname(dbpath))
            return dbpath
    return path

class RepositoryDB(API):
    def __init__(self):
        super(RepositoryDB, self).__init__(const.repositorydb_path)

class InstallDB(API):
    def __init__(self):
        super(InstallDB, self).__init__(fix_path(const.installdb_path))

class FilesDB(FilesAPI):
    def __init__(self, real_root=None, suffix=None):
        super(FilesDB, self).__init__(real_root, suffix)


