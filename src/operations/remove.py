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
import lpms

from lpms import out
from lpms import utils
from lpms import shelltools
from lpms import constants as cst

from lpms.db import dbapi

# TODO:
# (-) config protect
# (-) directory symlinks
# (-) warning messages

class Remove:
    def __init__(self, repo, category, name, version, real_root):
        self.repo = repo
        self.category = category
        self.name = name
        self.version = version
        self.real_root = real_root
        if self.real_root is None:
            self.real_root = cst.root
        self.filesdb = dbapi.FilesDB()

    def remove_content(self):
        dirs = []
        for _file in self.filesdb.get_paths_by_package(self.name, category=self.category, version=self.version):
            _file = _file[0]
            target = os.path.join(self.real_root, _file[1:])
            if os.path.dirname(_file[1:]) == cst.info:
                utils.update_info_index(target, dir_path=os.path.join(self.real_root, cst.info, "dir"), delete=True)

            if os.path.islink(target):
                os.unlink(target)
            elif os.path.isfile(target):
                if os.path.exists(target):
                    shelltools.remove_file(target)
            else:
                dirs.append(target)

        dirs.reverse()
        for _dir in dirs:
            target = os.path.join(self.real_root, _dir[1:])
            if os.path.isdir(target) and len(os.listdir(target)) == 0:
                shelltools.remove_dir(target)

def main(pkgname, real_root):
    # FIXME: Do we need the 'select' function?
    def select(pkgname):
        """ Select the package version and return spec's path """
        result = []
        if pkgname.startswith("="):
            name, version = utils.parse_pkgname(pkgname[1:])
            # FIXME: if there are the same packages in different categories, 
            # warn user.
            for pkg in instdb.find_pkg(name):
                instvers = []
                map(lambda ver: instvers.extend(ver), pkg[3].values())
                if version in instvers:
                    repo, category, name = pkg[:-1]
                    result = (repo, category, name, version)
            if len(result) == 0:
                lpms.catch_error("%s not found!" % out.color(pkgname[1:], "brightred"))
        else:
            data = instdb.find_pkg(pkgname)
            versions = data[-1]
            if len(versions) > 1:
                out.warn("%s versions installed for %s:" % (len(versions), pkgname))
                def ask():
                    for count, ver in enumerate(versions):
                        out.write("\t%s) %s: %s\n" % (out.color(str(count+1), "green"), ver, versions[ver][0]))
                    out.write("\n")
                    out.normal("select one of them: ")
                    out.write("\nto exit, press 'Q' or 'q'\n")

                while True:
                    # run the dialog, show packages from different repositories
                    ask()
                    answer = sys.stdin.readline().strip()
                    if answer == "Q" or answer == "q":
                        lpms.terminate()
                    elif answer.isalpha():
                        out.warn("you must give a number.\n")
                        continue

                    try:
                        # FIXME: we need more control
                        version = versions.values()[int(answer)-1][0]
                        break
                    except:
                        out.warn("%s seems invalid.\n" % out.color(answer, "red"))
                        continue
            else:
                version = versions.values()[0][0]

            if not data:
                lpms.catch_error("%s not found!" % out.color(pkgname, "brightred"))

            result = list(data); result.remove(data[-1])
            result.insert(3, version)

        return result

    instdb = dbapi.InstallDB()
    filesdb = dbapi.FilesDB()

    # start remove operation
    repo, category, name, version = pkgname
    # initialize remove class
    rmpkg = Remove(repo, category, name, version, real_root)
    
    lpms.logger.info("removing %s/%s/%s-%s from %s" % \
            (repo, category, name, version, rmpkg.real_root))
    out.normal("removing %s/%s/%s-%s from %s" % \
            (repo, category, name, version, rmpkg.real_root))
    
    # remove the package content
    rmpkg.remove_content()
    # remove entries from metadata table
    instdb.remove_pkg(repo, category, name, version)
    # remove paths from files table
    filesdb.delete_item_by_pkgdata(category, name, version, commit=True)
    # unlock
    if shelltools.is_exists(cst.lock_file):
        shelltools.remove_file(cst.lock_file)
