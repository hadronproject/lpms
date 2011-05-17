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
import tarfile
import zipfile

import lpms
from lpms import out

class Archive:
    def __init__(self, location):
        self.location = location
        
    def extract_tar(self, path):
        f = tarfile.open(path, 'r')
        out.notify("extracting %s to %s" % (os.path.basename(path), self.location))
        f.extractall(self.location)

    def extract_zip(self, path):
        f = zipfile.ZipFile(path)
        out.notify("extracting %s to %s" % (os.path.basename(path), self.location))
        f.extractall(self.location)
        #current = os.getcwd()
        #os.chdir(self.location)
        #z = zipfile.ZipFile(path, 'r')
        #for __file in z.infolist():
        #    file(__file.filename, 'wb').write(z.read(__file.filename))
        #    t = time.mktime(i.date_time)
        #    os.utime(fn, (t, t))
        #os.chdir(current)

def extract(file_path, location):
    if not os.path.isfile(file_path):
        lpms.terminate("%s could not found!" % file_path)
    valid_types = {
            'tar.bz2': 'extract_tar',
            "tgz": 'extract_tar',
            "zip":'extract_zip', 
            "lzma": 'extract_lzma',
            "xz": 'extractlzma',
            "tar.gz": 'extract_tar'
    }
    churchkey = Archive(location)
    for __type in valid_types.keys():
        if file_path.endswith(__type):
            getattr(churchkey, valid_types[__type])(file_path)
