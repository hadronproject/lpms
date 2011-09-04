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

from lpms import out
from lpms import conf
from lpms import utils
from lpms import constants as cst

def main():
    valid_repos = utils.valid_repos()
    for item in os.listdir(cst.repos):
        repo_conf = os.path.join(cst.repos, item, cst.repo_file)
        if os.access(repo_conf, os.F_OK):
            with open(repo_conf) as data:
                data = conf.ReadConfig(data.read().splitlines(), delimiter="@")
            if item in valid_repos:
                out.normal("%s [%s]" % (item, out.color("enabled", "brightgreen")))
            else:
                out.normal("%s [%s]" % (item, out.color("disabled", "brightred")))
            out.notify("system name: %s" % item)
            if hasattr(data, "name"):
                out.notify("development name: %s" % data.name)
            else:
                out.warn("development name is not defined!")
            if hasattr(data, "summary"):
                out.notify("summary: %s" % data.summary)
            else:
                out.warn("summary is not defined!")
            if hasattr(data, "maintainer"):
                out.notify("maintainer: %s" % data.maintainer)
            else:
                out.warn("maintainer is not defined!")
            out.write("\n")
