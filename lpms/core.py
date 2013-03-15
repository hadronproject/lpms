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

from lpms import out
from lpms import api
from lpms.cli import CommandLineParser
from lpms.exceptions import PackageNotFound

class Operations(object):
    '''Drives lpms'''
    def check_root(method):
        def wrapper(*args, **kwargs):
            if os.getuid() != 0 and args[0].request.instruction.pretend is None:
                out.wrire(">> you must be root to perform this operation.")
                sys.exit(0)
            return method(*args, **kwargs)
        return wrapper

    @check_root
    def remove(self):
        try:
            api.remove_package(self.request.names, self.request.instruction)
        except PackageNotFound as err:
            out.write(">> %s could not be found.\n" % out.color(err.message, "red"))
            sys.exit(0)

    @check_root
    def update(self):
        api.update_repository(self.request.names)

    @check_root
    def upgrade(self):
        packages = api.upgrade_packages()
        if not packages:
            out.write(">> no package found to upgrade.\n")
            sys.exit(0)
        self.package_mangler(names=packages)

    @check_root
    def sync(self):
        api.syncronization(self.request.names)

    @check_root
    def package_mangler(self, **kwargs):
        names = kwargs.get("names", self.request.names)
        api.package_build(names, self.request.instruction)

class LPMSCore(Operations):
    def __init__(self):
        self.request = CommandLineParser()
        self.request.start()

    def initialize(self):
        # Run command line client to drive lpms
        # Run actions, respectively
        if self.request.operations:
            for operation in self.request.operations:
                # TODO: We should use signals to determine behavior of lpms 
                # when the process has finished.
                getattr(self, operation)()
            return

        if self.request.names:
            # Now, we can start building packages.
            self.package_mangler()
        else:
            out.error("nothing given.")
            sys.exit(0)

def initialize():
    LPMSCore().initialize()
