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

from  __future__ import division
import datetime

import lpms

from lpms import out
from lpms.db import api

class BuildInfo(object):
    def __init__(self, package):
        if len(package) > 1:
            out.warn("this command takes only one package name.")
        self.package = package[0]
        self.instdb = api.InstallDB()

    def show_info(self, package):
        items = self.instdb.database.get_package_build_info(package.id)   
        template = (
                'Start_Time',
                'End Time',
                'Requestor',
                'Requestor ID',
                'HOST',
                'CFLAGS',
                'CXXFLAGS',
                'LDFLAGS',
                'JOBS',
                'CC',
                'CXX'
        )
        out.normal("Build information for %s/%s/%s-%s {%s:%s}" % (package.repo, \
                package.category, package.name, package.version, package.slot, package.arch))
        for index, item in enumerate(template, 1):
            if index in (1, 2):
                out.write("%s: %s\n" % (out.color(item, "green"), \
                        datetime.datetime.fromtimestamp(items[index]).strftime('%Y-%m-%d %H:%M:%S')))
                if index == 2:
                    delta = datetime.datetime.fromtimestamp(items[2])-\
                            datetime.datetime.fromtimestamp(items[1])
                    operation_time = str(float(delta.seconds)/60)+" minutes" if delta.seconds >= 60 \
                            else str(delta.seconds)+" seconds"
                    out.write("%s: %s\n" % (out.color("Operation Time", "green"), operation_time))
                continue
            out.write("%s: %s\n" % (out.color(item, "green"), items[index]))
    
    def run(self):
        package = self.package.split("/")
        if len(package) == 3:
            myrepo, mycategory, myname = package
            packages = self.instdb.find_package(package_name=myname, \
                    package_repo=myrepo, package_category=mycategory)
        elif len(package) == 2:
            mycategory, myname = package
            packages = self.instdb.find_package(package_name=myname, \
                    package_category=mycategory)
        elif len(package) == 1:
            packages = self.instdb.find_package(package_name=package[0])
        else:
            out.error("%s seems invalid." % out.color("/".join(package), "brightred"))
            lpms.terminate()

        if not packages:
            out.error("%s not found!" % out.color("/".join(package), "brightred"))
            lpms.terminate()

        for package in packages:
            self.show_info(package)

