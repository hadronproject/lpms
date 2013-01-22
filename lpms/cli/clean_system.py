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

import cPickle as pickle

from lpms import api
from lpms import out
from lpms.db import api as dbapi

class CleanSystem(object):
    def __init__(self):
        self.instdb = dbapi.InstallDB()
        self.removable_packages = set()
        self.instdb.database.cursor.execute('''SELECT * FROM package;''')
        self.packages = self.instdb.database.cursor.fetchall()

    def process_packages(self, category, name, version, slot):
        parent = self.instdb.get_parent_package(package_name=name, \
                package_category=category, package_version=version)
        break_package = False
        if parent is not None:
            parent_package = self.instdb.find_package(package_name=parent.name, \
                    package_category=parent.category, package_slot=parent.slot)
            if not parent_package:
                for package in self.packages:
                    for dependency_bundle in package[14:-1]:
                        dependencies = pickle.loads(str(dependency_bundle))
                        for dependency in dependencies:
                            if (package[2], package[3], package[5]) in self.removable_packages:
                                continue
                            if category == dependency[0] and name == dependency[1] and slot == dependency[3]:
                                break_package = True
                return break_package

    def run(self, instruct):
        all_packages = self.instdb.get_all_packages()
        for installed_item in all_packages:
            category, name, version, slot = installed_item[1:]
            if self.process_packages(category, name, version, slot) is False:
                self.removable_packages.add((category, name, slot))
        packages = []
        for installed_item in all_packages:
            category, name, version, slot = installed_item[1:]
            if self.process_packages(category, name, version, slot) is False:
                packages.append((category+"/"+name+"-"+version))
        if packages:
            out.normal("these package(s) is/are no longer required.")
            # FIXME: This is no good
            # I must find a new method to manage built-in variables and general purpose instructions 
            instruct["ask"] = True
            api.remove_package(packages, instruct)
        else:
            out.warn("no package found.")
