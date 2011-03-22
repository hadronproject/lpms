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

# XML based database implementation

import os
import xml.etree.cElementTree as iks

from lpms import constants as cst

#from lpms.db import dbapi

class FilesDB:
    def __init__(self, repo, category, name, version, real_root=None):
        self.content = {"dirs":[], "file": []}
        self.repo = repo
        self.category = category
        self.name = name
        self.version = version
        if real_root is None:
            real_root = cst.root
        self.xml_file = os.path.join(real_root, cst.db_path[1:], cst.filesdb, 
                self.category, self.name, self.name)+"-"+self.version+cst.xmlfile_suffix
        
    #def is_installed(self, ):
    #    return (self.repo, self.category, 
    #            self.name) in self.instdb.get_all_names()
        
    def import_xml(self):
        if not os.path.isfile(self.xml_file):
            print("%s could not found." % self.xml_file)
            return False

        raw_data = iks.parse(self.xml_file)
        for node in raw_data.findall("node"):
            self.content["dirs"].append(node.attrib['path'])
            for files in node.findall("file"):
                self.content["file"].append(os.path.join(
                    node.attrib['path'], files.text))

    def has_path(self, path):
        if not os.path.exists(path):
            print("%s could not found." % path)
            return False
        
        if os.path.isdir(path):
            for _dir in self.content['dirs']:
                if _dir == path:
                    return True
            return False
        
        elif os.path.isfile(path):
            for _dir in self.content['file']:
                if _dir == path:
                    return True
            return False
