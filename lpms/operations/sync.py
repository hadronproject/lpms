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

import lpms

from lpms import out
from lpms import constants as cst

# FIXME: This module must be rewritten. Object Oriended is nice.

class SyncronizeRepo(object):
    def __init__(self):
        self.data = None
        self.remote = None
        self._type = None

    def read_conf_file(self):
        with open(cst.repo_conf) as data:
            self.data = data.read().split("\n")

    def run(self, repo):
        keyword = "["+repo+"]"

        # import repo.conf
        self.read_conf_file()
        
        if keyword in self.data:
            first = self.data.index(keyword)
            for line in self.data[first+1:]:
                if line.startswith("["):
                    continue
                if self._type is None and line.startswith("type"):
                    self._type = line.split("@")[1].strip()
                    if self._type == 'local':
                        return
                elif self.remote is None and line.startswith("remote"):
                    self.remote = line.split("@")[1].strip()

        if self._type == "git":
            from lpms.syncers import git as syncer


        lpms.logger.info("synchronizing %s from %s" % (repo, self.remote))
        
        out.notify("synchronizing %s from %s" % (out.color(repo, "green"), self.remote))

        syncer.run(repo, self.remote)
