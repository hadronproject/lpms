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
import subprocess

import lpms
from lpms import out
from lpms import utils
from lpms.exceptions import FileNotFound

ldd_path = "/usr/bin/ldd"

def get_depends(file_path):
    '''Parses ldd's output and returns depends of shared lib or executable file'''
    depends = []
    if not os.access(ldd_path, os.X_OK):
        out.error("%s seems problematic. please check it." % ldd_path)
        lpms.terminate()

    if not os.path.exists(file_path):
        raise FileNotFound("%s not found." % file_path)
    
    if not utils.get_mimetype(file_path) in ('application/x-executable', \
            'application/x-archive', 'application/x-sharedlib'):
        out.error("%s is invalid for me." % file_path)
        return

    for line in subprocess.Popen([ldd_path, file_path], \
            stdout=subprocess.PIPE).stdout:
        data = line.strip().split("=>")
        if len(data) == 2:
            parsed = data[1].split(" ")
            if parsed[1] != "":
                depends.append(parsed[1])
    
    return depends
