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

# Base data containers for lpms database
from lpms.types import LCollect
from lpms.types import PackageItem

# Low level databases
from lpms.db import filesdb
from lpms.db import installdb
from lpms.db import repositorydb
from lpms.db import file_relationsdb
from lpms.db import reverse_dependsdb

from lpms.exceptions import DatabaseAPIError, MissingInternalParameter

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
        slot = kwargs.get("package_slot", None)
        available_arches = kwargs.get("available_arches", None)

        # Get the package query
        package_query = self.database.find_package(
                package_id=p_id, 
                package_repo=repo,
                package_category=category, 
                package_name=name, 
                package_version=version,
                package_slot=slot,
                package_available_arches=available_arches
        )

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
            pkg_obj.pk = pkg_obj.category+"/"+pkg_obj.name+"/"+pkg_obj.slot
            results.add(pkg_obj)

            # Delete the object to prevent overrides
            del pkg_obj
            # Create it again
            pkg_obj = LCollect()

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

        if p_id is not None:
            package_query = self.database.get_package_metadata(package_id=p_id)
        else:
            if None in (repo, category, name, version):
                raise MissingInternalParameter("%s/%s/%s-%s is meaningless") 
            package_query = self.database.get_package_metadata(package_repo=repo, \
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
        if p_id is not None:
            self.database.delete_package(package_id=p_id, commit=package_commit)
        else:
            if None in (repo, category, name, version):
                raise MissingInternalParameter("%s/%s/%s-%s is meaningless")
            self.database.delete_package(package_repo=repo, package_category=category, \
                    package_name=name, package_version=version, commit=package_commit)

    def delete_repository(self, repo, commit=False):
        '''Basic wrapper method to delete_repository method of the repository database'''
        self.database.delete_repository(repo, commit)

    def get_repository_names(self):
        '''Basic wrapper method to get_repository_names method of the repository database'''
        return [name[0] for name in self.database.get_repository_names()]

class InstallDB:
    def __init__(self):
        self.database = installdb.InstallDatabase()

    def insert_inline_options(self, package_id, target, options):
        self.database.insert_inline_options(package_id, target, options)

    def update_inline_options(self, package_id, target, options):
        self.database.update_inline_options(package_id, target, options)

    def delete_inline_options(self, **kwargs):
        package_id = kwargs.get("package_id", None)
        target = kwargs.get("target", None)
        commit = kwargs.get("commit", None)
        self.database.delete_inline_options(package_id, target, commit)

    def find_inline_options(self, **kwargs):
        package_id = kwargs.get("package_id", None)
        target = kwargs.get("target", None)
        results = self.database.find_inline_options(package_id, target)
        result_objs = PackageItem()
        for result in results:
            result_obj = LCollect()
            result_obj.package_id = result[0]
            result_obj.target = result[1]
            result_obj.options = pickle.loads(str(result[2]))
            result_objs.append(result_obj)
            del result_obj
        return result_objs

    def insert_conditional_versions(self, package_id, target, decision_point):
        self.database.insert_conditional_versions(package_id, target, decision_point)

    def update_conditional_versions(self, package_id, target, decision_point):
        self.database.update_conditional_versions(package_id, target, decision_point)

    def delete_conditional_versions(self, **kwargs):
        package_id = kwargs.get("package_id", None)
        target = kwargs.get("target", None)
        commit = kwargs.get("commit", None)
        self.database.delete_conditional_versions(package_id, target, commit)

    def find_conditional_versions(self, **kwargs):
        package_id = kwargs.get("package_id", None)
        target = kwargs.get("target", None)
        results = self.database.find_conditional_versions(package_id, target)
        result_objs = PackageItem()
        for result in results:
            result_obj = LCollect()
            result_obj.package_id = result[0]
            result_obj.target = result[1]
            result_obj.decision_point = pickle.loads(str(result[2]))
            result_objs.append(result_obj)
            del result_obj
        return result_objs

    def insert_package(self, dataset, commit=False):
        '''Creates a new installed package entry.'''
        self.database.insert_package(dataset, commit)

    def update_package(self, dataset, commit=False):
        '''Updates an installed package entry.'''
        self.database.update_package(dataset, commit)

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
                'parent',
                'applied_options',
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
        slot = kwargs.get("package_slot", None)
        version = kwargs.get("package_version", None)

        # Get the package query
        package_query = self.database.find_package(
                package_id=p_id, 
                package_repo=repo,
                package_category=category, 
                package_name=name, 
                package_version=version,
                package_slot=slot
        )
        
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
                if index >= 8:
                    setattr(pkg_obj, item, pickle.loads(str(package[index])))
                    continue
                setattr(pkg_obj, item, package[index])
            pkg_obj.pk = pkg_obj.category+"/"+pkg_obj.name+"/"+pkg_obj.slot
            results.add(pkg_obj)

            # Delete the object to prevent overrides
            del pkg_obj
            # Create it again
            pkg_obj = LCollect()

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

        if p_id is not None:
            package_query = self.database.get_package_metadata(package_id=p_id)
        else:
            if None in (repo, category, name, version):
                raise MissingInternalParameter("%s/%s/%s-%s is meaningless")
            package_query = self.database.get_package_metadata(package_repo=repo, \
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
        p_id = kwargs.get("package_id", None)
        repo = kwargs.get("package_repo", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)
        package_commit = kwargs.get("commit", False)
        if p_id is not None:
            self.database.delete_package(package_id=p_id)
        else:
            if None in (repo, category, name, version):
                raise MissingInternalParameter("%s/%s/%s-%s is meaningless")
            self.database.delete_package(package_repo=repo, package_category=category, \
                    package_name=name, package_version=version, commit=package_commit)

    def delete_repository(self, repo, commit=False):
        self.database.delete_repository(repo, commit)

    def get_all_packages(self):
        return self.database.get_all_packages()

    def insert_build_info(self, **kwargs):
        fields = ('repo',
            'category',
            'name',
            'version',
            'slot',
            'arch',
            'start_time',
            'end_time',
            'requestor',
            'requestor_id',
            'host',
            'cflags',
            'cxxflags',
            'ldflags',
            'makeopts',
            'size'
        )
        
        data_obj = LCollect()
        
        for field in fields:
            if not field in kwargs:
                raise MissingInternalParameter("%s is missing." % field)
            else:
                setattr(data_obj, field, kwargs[field])
        self.database.insert_build_info(data_obj)

    def get_parent_package(self, **kwargs):
        if "package_id" in kwargs:
            parent = self.database.get_parent_package(package_id=kwargs["package_id"])

        for key in ("package_category", "package_name", "package_version"):
            if not key in kwargs:
                raise DatabaseAPIError("%s is missing." % key)

        name = kwargs.get("package_name", None)
        category = kwargs.get("package_category", None)
        version = kwargs.get("package_version", None)

        parent = self.database.get_parent_package(category, name, version)
        
        package = LCollect()
        if parent is None: return
        package.category, package.name, package.slot = parent.split("/")
        return package

# For backward compatibility
FilesDB = filesdb.FilesDatabase
FileRelationsDB = file_relationsdb.FileRelationsDatabase
ReverseDependsDB = reverse_dependsdb.ReverseDependsDatabase
