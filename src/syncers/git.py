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

from lpms import out
from lpms import shelltools
from lpms import constants as cst

from lpms.exceptions import InvalidURI

class GITSync(object):
    def __init__(self, repo, remote):
        self.repo = repo
        self.remote = remote
        self.git_binary = "/usr/bin/git"
        self.repo_path = os.path.join(cst.repos, repo)

    def git_repo(self):
        if os.path.isdir(self.repo_path) and os.listdir(self.repo_path):
            if os.path.isdir(self.repo_path+"/"+".git"):
                return True
        return False
    
    # parse_uri method is borrowed from pkgcore: sync/git.py
    def parse_uri(self):                                                                                                                                                                 
        if not self.remote.startswith("git+") and not self.remote.startswith("git://"):
            raise InvalidURI(self.remote, "doesn't start with git+ nor git://")
        if self.remote.startswith("git+"):
            if self.remote.startswith("git+:"):
                raise InvalidURI(self.remote, "need to specify the sub protocol if using git+")
            self.remote = self.remote[4:]

    def sync(self):
        if self.git_repo():
            os.chdir(self.repo_path)
            if lpms.getopt("--reset"):
                out.warn("forcing git to overwrite local files")
                shelltools.system("%s reset --hard HEAD" % self.git_binary)
                shelltools.system("%s clean -f -d" % self.git_binary)
            shelltools.system("%s pull -f -u origin" % self.git_binary)
        else:
            os.chdir(os.path.dirname(self.repo_path))
            shelltools.system("%s clone %s %s" % (self.git_binary, self.remote, self.repo))


def run(repo, remote):
    obj = GITSync(repo, remote)
    if not os.access("%s" % obj.git_binary, os.X_OK):
        lpms.terminate("%s seems not executable or not exist. Please check dev-vcs/git." % obj.git_binary)

    obj.parse_uri()
    obj.sync()
