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

from lpms.db import dbapi

class CollisionProtect:
    def __init__(self, real_root, source_dir):
        self.real_root = real_root
        self.files_and_links = {}
        self.source_dir = source_dir
        self.filesdb = dbapi.FilesDB()
        self.prepare_files_and_links()
        self.collisions = []

    def prepare_files_and_links(self):
        for item in self.filesdb.get_files_and_links():
            if item[-1] in self.files_and_links:
                self.files_and_links[item[-1]].append(item[:-1])
                continue
            self.files_and_links.update({item[-1]: [item[:-1]]})

    def handle_collisions(self):
        for root_path, dirs, files in os.walk(self.source_dir, \
                followlinks=True):
            root_path = "".join(root_path.split(self.source_dir))
            if files:
                for item in files:
                    mypath = os.path.join(root_path, item)
                    if mypath in self.files_and_links:
                        if len(self.files_and_links[mypath]) != 1:
                            self.collisions.append((self.files_and_links[mypath], mypath))
        del self.files_and_links
