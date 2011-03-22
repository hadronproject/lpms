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
from lpms import utils
from lpms import shelltools
from lpms import constants as cst

from lpms.db import dbapi
from lpms.db import filesdb

# TODO:
# (-) config protect
# (-) directory symlinks
# (-) warning messages

class Remove:
    def __init__(self, repo, category, name, version, instruct):
        self.__dict__.update(instruct)
        self.repo = repo
        self.category = category
        self.name = name
        self.version = version
        if self.real_root is None:
            self.real_root = cst.root
        self.fdb = filesdb.FilesDB(repo, category, 
                name, version, self.real_root)
        self.fdb.import_xml()

    def remove_files(self):
        for _file in self.fdb.content['file']:
            target = os.path.join(self.real_root, _file[1:])
            if os.path.islink(target):
                os.unlink(target)
            else:
                shelltools.remove_file(target)


    def remove_dirs(self):
        dirs = self.fdb.content['dirs']
        dirs.reverse()
        for _dir in dirs:
            target = os.path.join(self.real_root, _dir[1:])
            if len(os.listdir(target)) == 0:
                shelltools.remove_dir(target)

def main(pkgnames, instruct):
    def select(pkgname):
        """ Select the package version and return spec's path """
        result = []
        if pkgname.startswith("="):
            name, version = utils.parse_pkgname(pkgname[1:])
            # FIXME: if there are the same packages in different categories, 
            # warn user.
            for pkg in instdb.find_pkg(name):
                instver = pkg[3].split(' ')
                if version in instver:
                    repo, category, name = pkg[:-1]
                    result = (repo, category, name, version)
            if len(result) == 0:
                lpms.catch_error("%s not found!" % out.color(pkgname[1:], "brightred"))
        else:
            data = instdb.find_pkg(pkgname)
            if not data:
                lpms.catch_error("%s not found!" % out.color(pkgname, "brightred"))
            
            data = data[0]
            instver= data[3].split(' ')
            if len(instver) != 1:
                result = utils.best_version(data)
            else:
                result = data
        return result

    instdb = dbapi.InstallDB()

    # start remove operation
    for pkgname in pkgnames:
        repo, category, name, version = select(pkgname)
        out.normal("removing %s/%s/%s-%s" % (repo, category, name, version))
        # initialize remove class
        rmpkg = Remove(repo, category, name, version, instruct)
        # remove files
        rmpkg.remove_files()
        # remove empty dirs
        rmpkg.remove_dirs()
        # remove entries from metadata table
        instdb.remove_pkg(repo, category, name, version)
        # remove entries from build_info table
        #instdb.drop_buildinfo(repo, category, name, version)
    
