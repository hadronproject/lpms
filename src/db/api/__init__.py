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

# Database access api for lpms and related applications

import cPickle as pickle

from lpms.exceptions import DatabaseAPIError

from lpms.types import LCollect
from lpms.types import PackageItem

from lpms.db import installdb
from lpms.db import repositorydb

class RepositoryDB:
    def __init__(self):
        self.database = repositorydb.RepositoryDatabase()
        
    def insert_package(self, dataset, commit=False):
        self.database.insert_package(dataset, commit)

    def find_package(self, **kwargs):
        results = PackageItem()
        added_packages = []
        object_items = (
                'id', 
                'repo', 
                'category', 
                'name', 
                'version', 
                'slot', 
                'arch', 
                'options',
                'optional_depends_build', 
                'optional_depends_runtime', 
                'optional_depends_postmerge',
                'optional_depends_conflict', 
                'static_depends_build', 
                'static_depends_runtime',
                'static_depends_postmerge',
                'static_depends_conflict'
        )

        # Set the keywords
        name = kwargs.get("package_name", None)
        p_id = kwargs.get("package_id", None)
        if p_id is None and name is None:
            raise DatabaseAPIError("you must give package_name parameter.")
        repo = kwargs.get("package_repo", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)

        # Get the package query
        package_query = self.database.find_package(package_id=p_id, package_repo=repo, \
                package_category=category, package_name=name, package_version=version)
        
        # Create a LCollect object
        pkg_obj = LCollect()

        # Add the packages to the object
        for package in package_query:
            # [0] => repo, [1] => category [2] => name, [3] => version, [6] => arch
            if not (package[1], package[2], package[3], package[4], package[6]) in added_packages:
                added_packages.append((package[1], package[2], package[3], package[4], package[6]))
            else: continue
            for item in object_items:
                index = object_items.index(item)
                if index >= 7:
                    setattr(pkg_obj, item, pickle.loads(str(package[index])))
                    continue
                setattr(pkg_obj, item, package[index])
            results.add(pkg_obj)
        return results

    def get_package_metadata(self, **kwargs):
        object_items = (
                'id', 
                'repo', 
                'category', 
                'name', 
                'version', 
                'slot', 
                'summary',
                'homepage', 
                'license', 
                'src_uri', 
                'arch', 
                'options'
        )

        # Set the keywords
        name = kwargs.get("package_name", None)
        p_id = kwargs.get("package_id", None)
        repo = kwargs.get("package_repo", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)

        package_query = self.database.get_package_metadata(package_id=p_id, package_repo=repo, \
                package_category=category, package_name=name, package_version=version)
        
        # Create a LCollect object
        pkg_obj = LCollect()

        # Add the packages to the object
        for item in object_items:
            index = object_items.index(item)
            if index == 11:
                setattr(pkg_obj, item, pickle.loads(str(package_query[index])))
                continue
            setattr(pkg_obj, item, package_query[index])
        return pkg_obj

    def get_package_dependencies(self, package_id):
        object_items = (
                'optional_depends_build', 
                'optional_depends_runtime', 
                'optional_depends_postmerge',
                'optional_depends_conflict', 
                'static_depends_build', 
                'static_depends_runtime',
                'static_depends_postmerge',
                'static_depends_conflict', 
 
        )

        package_query = self.database.get_package_dependencies(package_id)
        
        # Create a LCollect object
        pkg_obj = LCollect()

        for item in object_items:
            index = object_items.index(item)
            setattr(pkg_obj, item, pickle.loads(str(package_query[index])))
        return pkg_obj


    def delete_package(self, **kwargs):
        '''Basic wrapper method to delete_package method of the repository database'''
        # Set the keywords
        name = kwargs.get("package_name", None)
        p_id = kwargs.get("package_id", None)
        repo = kwargs.get("package_repo", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)
        package_commit = kwargs.get("commit", False)
        self.database.delete_package(package_id=p_id, package_repo=repo, package_category=category, \
                package_name=name, package_version=version, commit=package_commit)

    def delete_repository(self, repo, commit=False):
        '''Basic wrapper method to delete_repository method of the repository database'''
        self.database.delete_repository(repo, commit)

    def get_repository_names(self):
        '''Basic wrapper method to get_repository_names method of the repository database'''
        return self.database.get_repository_names()

class InstallDB:
    def __init__(self):
        self.database = installdb.InstallDatabase()

    def insert_package(self, dataset, commit=False):
        self.database.insert_package(dataset, commit)

    def find_package(self, **kwargs):
        results = PackageItem()
        added_packages = []
        object_items = (
                'id', 
                'repo', 
                'category', 
                'name', 
                'version', 
                'slot', 
                'arch', 
                'options',
                'optional_depends_build', 
                'optional_depends_runtime', 
                'optional_depends_postmerge',
                'optional_depends_conflict', 
                'static_depends_build', 
                'static_depends_runtime',
                'static_depends_postmerge', 
                'static_depends_conflict',
                'optional_reverse_build', 
                'optional_reverse_runtime', 
                'optional_reverse_postmerge', 
                'optional_reverse_conflict', 
                'static_reverse_build', 
                'static_reverse_runtime', 
                'static_reverse_postmerge', 
                'static_reverse_conflict'
        )

        # Set the keywords
        name = kwargs.get("package_name", None)
        if p_id is None and name is None:
            raise DatabaseAPIError("you must give package_name parameter.")
        p_id = kwargs.get("package_id", None)
        repo = kwargs.get("package_repo", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)
        
        # Get the package query
        package_query = self.database.find_package(package_id=p_id, package_repo=repo, \
                package_category=category, package_name=name, package_version=version)

        # Create a LCollect object
        pkg_obj = LCollect()

        # Add the packages to the object
        for package in package_query:
            # [0] => repo, [1] => category [2] => name, [3] => version, [6] => arch
            if not (package[1], package[2], package[3], package[4], package[6]) in added_packages:
                added_packages.append((package[1], package[2], package[3], package[4], package[6]))
            else: continue
            for item in object_items:
                index = object_items.index(item)
                if index >= 7:
                    setattr(pkg_obj, item, pickle.loads(str(package[index])))
                    continue
                setattr(pkg_obj, item, package[index])
            results.add(pkg_obj)
        return results

    def get_package_metadata(self, **kwargs):
        object_items = ('id', 
                'repo', 
                'category', 
                'name', 
                'version', 
                'slot', 
                'summary',
                'homepage', 
                'license', 
                'src_uri', 
                'arch', 
                'options'
        )

        # Set the keywords
        name = kwargs.get("package_name", None)
        p_id = kwargs.get("package_id", None)
        repo = kwargs.get("package_repo", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)

        package_query = self.database.get_package_metadata(package_id=p_id, package_repo=repo, \
                package_category=category, package_name=name, package_version=version)
        
        # Create a LCollect object
        pkg_obj = LCollect()

        # Add the packages to the object
        for item in object_items:
            index = object_items.index(item)
            if index == 11:
                setattr(pkg_obj, item, pickle.loads(str(package_query[index])))
                continue
            setattr(pkg_obj, item, package_query[index])
        return pkg_obj

    def get_package_dependencies(self, package_id):
        object_items = (
                'optional_depends_build', 
                'optional_depends_runtime', 
                'optional_depends_postmerge', 
                'optional_depends_conflict', 
                'static_depends_build', 
                'static_depends_runtime', 
                'static_depends_postmerge', 
                'static_depends_conflict', 
                'optional_reverse_build',
                'optional_reverse_runtime', 
                'optional_reverse_postmerge',
                'optional_reverse_conflict', 
                'static_reverse_build', 
                'static_reverse_runtime',
                'static_reverse_postmerge', 
                'static_reverse_conflict'
        )
        package_query = self.database.get_package_dependencies(package_id)
        
        # Create a LCollect object
        pkg_obj = LCollect()

        for item in object_items:
            index = object_items.index(item)
            setattr(pkg_obj, item, pickle.loads(str(package_query[index])))
        return pkg_obj


    def delete_package(self, **kwargs):
        # Set the keywords
        name = kwargs.get("package_name", None)
        package_id = kwargs.get("package_id", None)
        repo = kwargs.get("package_repo", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)
        package_commit = kwargs.get("commit", False)
        self.repositorydb.delete_package(package_id=p_id, package_repo=repo, package_category=category, \
                package_name=name, package_version=version, commit=package_commit)

    def delete_repository(self, repo, commit=False):
        self.repositorydb.delete_repository(repo, commit)

# For testing purposes
"""
a = InstallDB()

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

dataset.optional_reverse_build = { 'nls': ["sys-libs/ncurses"] }
dataset.optional_reverse_runtime = { 'nls': ["sys-libs/ncurses"] }
dataset.optional_reverse_postmerge = {}
dataset.optional_reverse_conflict = {}
dataset.static_reverse_build = ["sys-libs/glibc"]
dataset.static_reverse_runtime = ["sys-libs/glibc"]
dataset.static_reverse_postmerge = []
dataset.static_reverse_conflict = []
"""
