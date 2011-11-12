
import os
import xml.etree.cElementTree as iks

import lpms
from lpms import utils
from lpms import shelltools
from lpms import constants as cst

from lpms.db import dbapi
from lpms.exceptions import NotInstalled, FileNotFound

# XML based database implementation
class FilesDB:
    def __init__(self, category, name, version, real_root=None, suffix=None):
        self.content = {"dirs":[], "file": []}
        self.category = category
        self.name = name
        self.version = version
        if real_root is None:
            real_root = cst.root

        if suffix is None:
            suffix = cst.xmlfile_suffix

        self.xml_file = os.path.join(real_root, cst.db_path[1:], cst.filesdb,
                self.category, self.name, self.name)+"-"+self.version+suffix

    def import_xml(self):
        if not os.path.isfile(self.xml_file):
            print("%s could not found." % self.xml_file)
            return False

        raw_data = iks.parse(self.xml_file)
        for node in raw_data.findall("node"):
            self.content["dirs"].append(node.attrib['path'])
            for files in node.findall("file"):
                self.content["file"].append(os.path.join(
                    node.attrib['path'], files.text))

    def has_path(self, path):
        if not os.path.exists(path):
            return False
        
        if os.path.isdir(path):
            for _dir in self.content['dirs']:
                if _dir == path:
                    return True
            return False
        
        elif os.path.isfile(path):
            for _dir in self.content['file']:
                if _dir == path:
                    return True
            return False

    def get_attributes(self, path):
        data = iks.parse(self.xml_file)
        for node in data.findall("node"):
            for _file in node.findall("file"):
                if path == node.attrib["path"]+"/"+_file.text:
                    return _file.attrib


class FilesAPI(object):
    '''This class defines a simple abstraction layer for files database'''
    def __init__(self, real_root=None, suffix=None):
        self.real_root = real_root 
        self.suffix = suffix

    def cursor(self, category, name, version):
        '''Connects files database'''
        self.category = category
        self.name = name; self.version = version
        filesdb_obj = FilesDB(category, name, \
                version, self.real_root, self.suffix)
        filesdb_obj.import_xml()
        return filesdb_obj

    def get_versions(self, category, name):
        versions = []
        if not os.path.isdir(os.path.join(cst.db_path, cst.filesdb, category, name)):
            raise NotInstalled

        for pkg in os.listdir(os.path.join(cst.db_path, cst.filesdb, category, name)):
            versions.append(utils.parse_pkgname(pkg[:-4])[1])

        if not versions:
            raise NotInstalled
        return versions

    def get_all_names(self):
        packages = []
        for category in os.listdir(os.path.join(cst.db_path, cst.filesdb)):
            for pkg in os.listdir(os.path.join(cst.db_path, cst.filesdb, category)):
                packages.append((category, pkg))
        return packages

    def is_installed(self, category, name, version):
        '''Checks package status'''
        return version in self.get_versions(category, name)

    def get_package(self, path):
        '''Returns package name or package names for the given path'''
        result = []
        for package in self.get_all_names():
            category, name = package
            versions = self.get_versions(category, name)
            for version in versions:
                filesdb_cursor = self.cursor(category, \
                        name, version)
                if filesdb_cursor.has_path(path):
                    del filesdb_cursor
                    if not (category, name, version) in result:
                        result.append((category, name, version))
        if result:
            return result
        return False

    def get_permissions(self, category, name, version, path):
        '''Returns permissons of given package'''
        # TODO: category, name and version will be optional
        cursor = self.cursor(category, name, version)
        attributes = cursor.get_attributes(path)
        if not attributes:
            raise FileNotFound("%s/%s-%s: %s" % (category, name, version, path))
        perms = {}
        for key in attributes:
            if key in ('gid', 'mod', 'uid'):
                perms[key] = attributes[key]
        return perms

    def list_files(self, category, name, version):
        '''Returns content for the given package'''
        if not self.is_installed(category, name, version):
            raise NotInstalled("%s/%s-%s is not installed." % (category, name, version))
        filesdb_cursor = self.cursor(category, name, version)
        return filesdb_cursor.content

    def has_path(self, category, name, version, path):
        '''Checks given package for given path'''
        if not self.is_installed(category, name, version):
            raise NotInstalled("%s/%s-%s is not installed." % (category, name, version))
        filesdb_cursor = self.cursor(category, name, version)
        return filesdb_cursor.has_path(path)

if lpms.getopt("--help"):
    print("A script that to migrate old xml based files database to new sql based one")
    lpms.terminate()

installdb = dbapi.InstallDB()
fapi = FilesAPI()
shelltools.remove_file("/var/db/lpms/filesdb.db")
_filesdb = dbapi.FilesDB()

i = 0
for pkg in installdb.get_all_names():
    repo, category, name = pkg
    versions = installdb.get_version(name, repo_name=repo, pkg_category=category)
    for slot in versions:
        for version in versions[slot]:
            i += 1
            print("%d - %s/%s/%s-%s" % (i, repo, category, name, version))
            content = fapi.list_files(category, name, version)
            for path in content["dirs"]:
                if path == "" or not os.path.exists(path): 
                    if path != "": print("\t%s not found" % path)
                    continue
                uid = utils.get_uid(path)
                gid = utils.get_gid(path)
                mod = utils.get_mod(path)
                if not os.path.islink(path):
                    _filesdb.append_query((repo, category, name, version, path, \
                            "dir", None, gid, mod, uid, None, None))
                else:
                    _filesdb.append_query((repo, category, name, version, path, \
                            "link", None, gid, mod, uid, None, os.path.realpath(path)))
            for path in content["file"]:
                if path == "" or not os.path.exists(path):
                    if path != "": print("\t%s not found" % path)
                    continue
                uid = utils.get_uid(path)
                gid = utils.get_gid(path)
                mod = utils.get_mod(path)
                if not os.path.islink(path):
                    size = utils.get_size(path, dec=True)
                    sha1sum = utils.sha1sum(path)
                    _filesdb.append_query((repo, category, name, version, path, \
                        "file", size, gid, mod, uid, sha1sum, None))
                else:
                    _filesdb.append_query((repo, category, name, version, path, \
                        "link", None, gid, mod, uid, None, None))

_filesdb.insert_query(commit=True)
