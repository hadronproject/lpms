
from lpms.db import api as dbapi

class Autoremove(object):
    def __init__(self):
        self.instdb = dbapi.InstallDB()

    def select(self):
        for (repo, category, name, version, slot) in \
                self.instdb.get_all_packages():
                    parent = self.instdb.get_parent_package(package_name=name, \
                            package_category=category, package_version=version)
                    if parent is not None:
                        for package in self.instdb.find_package(package_name=parent.name, \
                                package_category=parent.category):
                            if package.slot != slot: 
                                continue
