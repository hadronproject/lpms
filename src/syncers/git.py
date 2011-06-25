#!/usr/bin/env python
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

from lpms import shelltools
from lpms import constants as cst

class GITSync(object):
    def __init__(self, repo, remote):
        self.repo = repo
        self.remote = remote
        self.repo_path = os.path.join(cst.repos, repo)

    def git_repo(self):
        if os.path.isdir(self.repo_path) and os.listdir(self.repo_path):
            if os.path.isdir(self.repo_path+"/"+".git"):
                return True
        return False

    def sync(self):
        if self.git_repo():
            os.chdir(self.repo_path)
            if lpms.getopt("--reset"):
                shelltools.system("git reset --hard HEAD")
            shelltools.system("git pull -f -u origin")
        else:
            os.chdir(os.path.dirname(self.repo_path))
            shelltools.system("git clone %s %s" % (self.remote, self.repo))


def run(repo, remote):
    obj = GITSync(repo, remote)
    obj.sync()
