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

class API(object):
    def __init__(self, db_path):
        self.db = db.PackageDatabase(db_path)

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
        return self.db.get_version(pkgname, repo_name, pkg_category)

    def get_options(self, repo_name, pkgname, pkg_category, version):
        return self.db.get_options(repo_name, pkgname, pkg_category, version)

    def get_slot(self, repo_name, pkgname, pkg_category, pkg_version):
        return self.db.get_slot(repo_name, pkgname, pkg_category, pkg_version)

    def add_depends(self, data, commit=False):
        return self.db.add_depends(data, commit)

    def get_depends(self, repo_name, category, pkgname, version=None):
        return self.db.get_depends(repo_name, category, pkgname, version)

    def get_arch(self, repo_name, category, pkgname, version = None):
        return self.db.get_arch(repo_name, category, pkgname, version)

    def get_repo(self, category, pkgname, version = None):
        result = self.find_pkg(pkgname, selection = True)
        
        for pkg in result:
            repo, catgry, name, gversions = pkg
            # FIXME: Unicode issues
            if catgry == category and name == pkgname:
                if version is not None:
                    versions = []
                    map(lambda v: versions.extend(v), gversions.values())
                    if version in versions:
                        return repo
                    else:
                        return False
                return repo

        with open("/etc/lpms/repo.conf") as repo_file:
            for repo in [repo.strip() for repo in repo_file.readlines()[1:] \
                    if not repo.startswith("#")]:
                raw_result = self.find_pkg(pkgname, repo_name = repo, \
                        pkg_category = category)
                if raw_result:
                    return repo
        
        return False

    #def add_status(self, data):
    #    if self.__class__.__name__ == "InstallDB":
    #        return self.db.add_status(data)

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
