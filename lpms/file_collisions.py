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

import lpms
from lpms import out
from lpms import constants as cst

from lpms.db import api

class CollisionProtect:
    def __init__(self, category, name, slot, version=None, \
            real_root=None, source_dir=None):
        self.real_root = real_root
        self.files_and_links = {}
        self.source_dir = source_dir
        self.filesdb = api.FilesDB()
        self.prepare_files_and_links()
        self.orphans = []
        self.collisions = []
        self.name = name
        self.category = category
        self.slot = slot
        self.version = version
        self.symlinks = []

    def is_parent_symlink(self, target):
        for symlink in self.symlinks:
            if target.startswith(symlink):
                return True

    def catch_file(self, mypath):
        if mypath in self.files_and_links:
            for package in self.files_and_links[mypath]:
                c_category, c_name, c_slot, c_version = package
                if (self.category, self.name, self.slot) != (c_category, \
                        c_name, c_slot):
                    if not ((c_category, c_name, c_slot, c_version), mypath) \
                            in self.collisions:
                        self.collisions.append(((c_category, c_name, c_slot, \
                                c_version), mypath))
        else:
            if os.path.exists(mypath):
                self.orphans.append(mypath)

    def prepare_files_and_links(self):
        root_path = cst.root
        if self.real_root != cst.root:
            root_path = self.real_root
        for item in self.filesdb.get_files_and_links():
            mypath = os.path.join(root_path, item[-1][1:])
            if item[-1] in self.files_and_links:
                self.files_and_links[mypath].append(item[:-1])
                continue
            self.files_and_links.update({mypath: [item[:-1]]})

    def handle_collisions(self):
        if self.source_dir:
            for root_path, dirs, files in os.walk(self.source_dir, \
                    followlinks=True):
                for __dir in dirs:
                    target_dir = os.path.join(root_path, __dir)
                    if os.path.islink(target_dir):
                        target_dir = "".join(target_dir.split(self.source_dir))
                        self.symlinks.append(target_dir+"/")

                root_path = "".join(root_path.split(self.source_dir))
                if not files: continue
                for item in files:
                    if self.real_root != cst.root:
                        root_path = os.path.join(self.real_root, root_path[1:])
                    mypath = os.path.join(root_path, item)
                    if self.is_parent_symlink(mypath): break
                    self.catch_file(mypath)
        else:
            for path in self.filesdb.get_files_and_links_by_package(self.category, \
                    self.name, self.version):
                mypath = path[0]
                if self.real_root != cst.root:
                    mypath = os.path.join(self.real_root, mypath[1:])
                self.catch_file(mypath)
        del self.files_and_links
