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
import time
import shutil
import xml.etree.cElementTree as iks

from lpms import out
from lpms import utils
from lpms import internals
from lpms import shelltools
from lpms import constants as cst

from lpms.db import dbapi
from lpms.db import filesdb

class Merge(internals.InternalFuncs):
    '''Main class for package installation'''
    def __init__(self, environment):
        # Do I need this?
        super(Merge, self).__init__()
        self.total = 0
        self.myfile = None
        self.filesdb_path = None
        self.versions = []
        self.env = environment
        self.instdb = dbapi.InstallDB()

    # FIXME: Do I need is_X methodes? i will move it 
    def is_fresh(self):
        status = self.instdb.find_pkg(self.env.name, 
            self.env.repo, self.env.category)
        
        if isinstance(status, bool):
            return True
        
        map(lambda x: self.versions.extend(x), status[-1].values())
        if not status or not self.env.version in self.versions:
            return True
        
        return False

    def is_reinstall(self):
        result = self.instdb.find_pkg(self.env.name, self.env.repo, self.env.category)
        version = result[-1]
        if len(self.versions) == 1 and version == self.env.version:
            return True
        elif len(self.versions) != 1 and self.env.version in self.versions:
            return True
        return False

    def is_different(self):
        result = self.instdb.find_pkg(self.env.name, self.env.repo, self.env.category)
        version = result[-1]
        if len(self.versions) == 1 and version != self.env.version:
            return True
        elif len(self.versions) != 1 and not self.env.version in self.versions:
            return True
        return False

    def merge_pkg(self):
        '''Merge package to the system'''
        
        def get_perms(path):
            '''Get permissions of given path, it may be file or directory'''
            return {"uid": utils.get_uid(path),
                    "gid": utils.get_gid(path),
                    "mod": utils.get_mod(path)
            }

        # set installation target
        if self.env.real_root is None:
            self.env.real_root = cst.root

        out.notify("merging the package to %s and creating %s.xml" % (self.env.real_root, self.env.fullname))
        
        # create an xml object
        xml_root = iks.Element("content")

        # find content of the package
        for root_path, dirs, files in os.walk(self.env.install_dir, followlinks=True):
            root_path = root_path.split(self.env.install_dir)[1]

            # write directories
            root = iks.SubElement(xml_root, "node")
            root.set("path", root_path)

            # create directories
            for d in dirs:
                source = os.path.join(self.env.install_dir, root_path[1:], d)
                target = os.path.join(self.env.real_root, root_path[1:], d)

                if os.path.islink(source):
                    realpath = os.readlink(source)
                    if os.path.islink(target):
                        shelltools.remove_file(target)
                    # create real directory
                    shelltools.makedirs(realpath)
                    # make symlink
                    shelltools.make_symlink(realpath, target)
                else:
                    shelltools.makedirs(target)

                perms = get_perms(source)

                # if path is a symlink, pass permission mumbo-jumbos
                if not os.path.islink(source):
                    shelltools.set_id(target, perms["uid"], perms["gid"])
                    shelltools.set_mod(target, perms["mod"])

                dir_tag = iks.SubElement(root, "dir")
                for key in perms.keys():
                    dir_tag.set(key, str(perms[key]))
                dir_tag.text = d

            # write regular files
            for f in files:
                source = os.path.join(self.env.install_dir, root_path[1:], f)
                target = os.path.join(self.env.real_root, root_path[1:], f)

                if os.path.islink(source):
                    realpath = os.readlink(source)
                    if os.path.islink(target):
                        shelltools.remove_file(target)
                    shelltools.make_symlink(realpath, target)
                else:
                    shelltools.copy(source, target)

                perms = get_perms(source)

                if not os.path.islink(source):
                    shelltools.set_id(target, perms["uid"], perms["gid"])
                    shelltools.set_mod(target, perms["mod"])

                file_tag = iks.SubElement(root, "file")
                sha1sum = utils.sha1sum(source)
                for key in perms.keys():
                    file_tag.set(key, str(perms[key]))

                if sha1sum is not False:
                    file_tag.set("sha1sum", sha1sum)
                size = utils.get_size(source)
                self.total += size
                file_tag.set("size", str(size))
                file_tag.text = f

        # set installed size
        xml_root.set("size", str(self.total))

        # fix indentation
        utils.indent(xml_root)

        # write the xml file to filesdb
        self.filesdb_path = os.path.join(self.env.real_root, cst.db_path[1:], 
                cst.filesdb, self.env.category, self.env.name)
        shelltools.makedirs(self.filesdb_path)
        self.myfile = self.filesdb_path+"/"+self.env.fullname+".xml"
        if os.path.isfile(self.myfile):
            shelltools.remove_file(self.myfile)
        shelltools.echo(self.myfile, iks.tostring(xml_root))
        
        # it may be too big
        del xml_root

    def write_db(self):
        # write metadata
        # FIXME: do we need a function called update_db or like this?
        self.instdb.remove_pkg(self.env.repo, self.env.category,
                self.env.name, self.env.version)
        
        data =(self.env.repo, self.env.category, 
            self.env.name, self.env.version, 
            self.env.summary, self.env.homepage, 
            self.env.license, self.env.src_url, 
            " ".join(self.env.options), self.env.slot)

        self.instdb.add_pkg(data, commit=True)

        # write build info. flags, build time and etc.
        #self.instdb.drop_buildinfo(self.env.repo, self.env.category, self.env.name, self.env.version)
        data = (self.env.repo, self.env.category, self.env.name, self.env.version, time.time(), 
                os.environ["HOST"], os.environ["CFLAGS"], os.environ["CXXFLAGS"], 
                os.environ["LDFLAGS"], " ".join(self.env.applied), self.total)
        self.instdb.add_buildinfo(data)

    def clean_previous(self):
        def obsolete_content():
            versions = self.instdb.get_version(self.env.name, 
                    self.env.repo, self.env.category)[0].split(" ")
            current_slot = self.instdb.get_slot(self.env.repo, self.env.category, 
                    self.env.name, self.env.version)
            
            for ver in versions:
                slot = self.instdb.get_slot(self.env.repo, self.env.category, self.env.name, ver)
                if slot == current_slot:
                    return self.comparison(self.env.version, ver)

        if not self.is_fresh():
            if self.is_different() or self.is_reinstall():
                obsolete_dirs, obsolete_files = obsolete_content()

                if len(obsolete_dirs) != 0 or len(obsolete_files) !=0:
                    out.normal("cleaning obsolete content...")
                
                for _file in obsolete_files:
                    target = os.path.join(self.env.real_root, _file[1:])
                    if os.path.islink(target):
                        os.unlink(target)
                    else:
                        shelltools.remove_file(target)

                dirs = obsolete_dirs
                dirs.reverse()
                for _dir in dirs:
                    target = os.path.join(self.env.real_root, _dir[1:])
                    if len(os.listdir(target)) == 0:
                        shelltools.remove_dir(target)

    def comparison(self, new_ver, old_ver):
        obsolete_dirs = []; obsolete_files = []
        new = filesdb.FilesDB(self.env.repo, self.env.category, 
                self.env.name, new_ver, self.env.real_root)
        new.import_xml()

        old = filesdb.FilesDB(self.env.repo, self.env.category,
                self.env.name, old_ver, self.env.real_root)
        old.import_xml()

        # for directories
        for _dir in old.content['dirs']:
            if not _dir in new.content['dirs']:
                obsolete_dirs.append(_dir)

        # for regular files
        for _file in old.content['file']:
            if not _file in new.content['file']:
                obsolete_files.append(_file)

        return obsolete_dirs, obsolete_files


def main(environment):
    opr = Merge(environment)

    # merge
    opr.merge_pkg()

    # clean previous version if it is exists
    opr.clean_previous()

    # write to database
    opr.write_db()
