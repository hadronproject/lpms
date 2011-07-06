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
                if os.path.exists(target):
                    shelltools.remove_file(target)


    def remove_dirs(self):
        dirs = self.fdb.content['dirs']
        dirs.reverse()
        for _dir in dirs:
            target = os.path.join(self.real_root, _dir[1:])
            if os.path.isdir(target) and len(os.listdir(target)) == 0:
                shelltools.remove_dir(target)

def main(pkgnames, instruct):
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

    # start remove operation
    for pkgname in pkgnames:
        repo, category, name, version = pkgname
        # initialize remove class
        rmpkg = Remove(repo, category, name, version, instruct)
        
        lpms.logger.info("removing %s/%s/%s-%s from %s" % \
                (repo, category, name, version, rmpkg.real_root))
        out.normal("removing %s/%s/%s-%s from %s" % \
                (repo, category, name, version, rmpkg.real_root))
        
        # remove files
        rmpkg.remove_files()
        # remove empty dirs
        rmpkg.remove_dirs()
        # remove entries from metadata table
        instdb.remove_pkg(repo, category, name, version)
        xmlfile = os.path.join(rmpkg.real_root, cst.db_path[1:], 
                cst.filesdb, category, name, name)+"-"+version+cst.xmlfile_suffix
        if os.path.isfile(xmlfile):
            shelltools.remove_file(xmlfile)
            if not os.listdir(os.path.dirname(xmlfile)):
                # remove package dir, if it is empty
                shelltools.remove_dir(os.path.dirname(xmlfile))
                if not os.listdir(os.path.dirname(os.path.dirname(xmlfile))):
                    # remove category dir, if it is empty
                    shelltools.remove_dir(os.path.dirname(os.path.dirname(xmlfile)))
