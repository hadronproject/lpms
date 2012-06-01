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
import lpms

from lpms import out
from lpms import utils
from lpms import shelltools
from lpms import constants as cst

from lpms.db import api as dbapi

# TODO:
# (-) config protect
# (-) directory symlinks
# (-) warning messages

class Remove:
    def __init__(self, repo, category, name, version, real_root):
        self.repo = repo
        self.category = category
        self.name = name
        self.version = version
        self.real_root = real_root
        if self.real_root is None:
            self.real_root = cst.root
        self.filesdb = dbapi.FilesDB()

    def remove_content(self):
        dirs = []
        for _file in self.filesdb.get_paths_by_package(self.name, category=self.category, version=self.version):
            _file = _file[0]
            target = os.path.join(self.real_root, _file[1:])
            if os.path.dirname(_file[1:]) == cst.info:
                utils.update_info_index(target, dir_path=os.path.join(self.real_root, cst.info, "dir"), delete=True)

            if os.path.islink(target):
                os.unlink(target)
            elif os.path.isfile(target):
                if os.path.exists(target):
                    shelltools.remove_file(target)
            else:
                dirs.append(target)

        dirs.reverse()
        for target in dirs:
            if os.path.isdir(target) and not os.listdir(target):
                shelltools.remove_dir(target)

def main(pkgname, real_root):
    instdb = dbapi.InstallDB()
    filesdb = dbapi.FilesDB()

    # start remove operation
    repo, category, name, version = pkgname
    # initialize remove class
    rmpkg = Remove(repo, category, name, version, real_root)
    
    lpms.logger.info("removing %s/%s/%s-%s from %s" % \
            (repo, category, name, version, rmpkg.real_root))
    out.normal("removing %s/%s/%s-%s from %s" % \
            (repo, category, name, version, rmpkg.real_root))
    
    # remove the package content
    rmpkg.remove_content()
    # remove entries from the database
    package_id = instdb.find_package(package_repo=repo, package_category=category, \
            package_name=name, package_version=version).get(0).id
    instdb.delete_inline_options(package_id=package_id)
    instdb.delete_package(package_repo=repo, package_category=category, \
            package_name=name, package_version=version, commit=True)
    # remove paths from files table
    filesdb.delete_item_by_pkgdata(category, name, version, commit=True)
    # unlock
    if shelltools.is_exists(cst.lock_file):
        shelltools.remove_file(cst.lock_file)
