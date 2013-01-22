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
import gzip
import tarfile
import zipfile
import subprocess
from collections import OrderedDict

import lpms

from lpms import out

class Archive:
    def __init__(self, location, partial):
        self.location = location
        self.partial = partial
        
    def extract_tar(self, path):
        if not tarfile.is_tarfile(path):
            out.error("%s is not a valid tar file." % path)
            lpms.terminate()

        archive = tarfile.open(path, 'r')
        if isinstance(self.partial, list):
            for name in archive.getnames():
                if name in self.partial:
                    archive.extract(name, path=self.location)
                else:
                    for partial in self.partial:
                        if len(name.split(partial, 1)) == 2:
                            archive.extract(name, path=self.location)
        else:
            archive.extractall(self.location)
        archive.close()

    def extract_zip(self, path):
        f = zipfile.ZipFile(path, "r")
        f.extractall(path=self.location)
        f.close()

    def extract_lzma(self, path):
        if not os.access("/bin/tar", os.X_OK) or not os.access("/bin/tar", os.F_OK):
            lpms.terminate("please check app-arch/tar package")

        current = os.getcwd()
        os.chdir(self.location)
        cmd = "/bin/tar --lzma xvf %s" % path
        if path.endswith(".xz"):
            cmd = "/bin/tar Jxvf %s" % path

        stdout = subprocess.PIPE; stderr=subprocess.PIPE
        result = subprocess.Popen(cmd, shell=True, stdout=stdout, stderr=stderr)
        output, err = result.communicate()
        if result.returncode != 0:
            out.error("could not extract: %s" % out.color(path, "red"))
            print(output+err)
            os.chdir(current)
            lpms.terminate()

        os.chdir(current)

    def extract_gz(self, path):
        '''Extracts GZIP archives. It generally ships single files like
        a patch.
        '''
        with gzip.open(path, "rb") as archive:
            out.notify("extracting %s to %s" % (os.path.basename(path), self.location))
            file_content = archive.read()
            with open(os.path.join(self.location, 
                "".join(os.path.basename(path).split(".gz"))), 
                "w+") as myfile:
                myfile.write(file_content)

def extract(file_path, location, partial=False):
    if not os.path.isfile(file_path):
        lpms.terminate("%s could not found!" % file_path)
    valid_types = OrderedDict([
            ('tar.bz2', 'extract_tar'),
            ('tgz',  'extract_tar'),
            ('zip', 'extract_zip'), 
            ('lzma', 'extract_lzma'),
            ('xz', 'extract_lzma'),
            ('tar.gz', 'extract_tar'),
            ('gz', 'extract_gz')
    ])

    churchkey = Archive(location, partial)
    for file_type in valid_types:
        if file_path.endswith(file_type):
            getattr(churchkey, valid_types[file_type])(file_path)
            return
