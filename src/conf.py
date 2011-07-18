# Copyright 2009 - 2011 Burak Sezer <burak.sezer@linux.org.tr>
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

from lpms import exceptions

from lpms import constants as cst

class ReadConfig(object):
    def __init__(self, data):
        for line in data:
            if not line.strip() or line.startswith("#"):
                continue

            parsed_line = line.split("=", 1)
            if len(parsed_line) == 1:
                i = 1
                while True:
                    prev_key = data[data.index(line) - i].split("=", 1)[0].strip()
                    if prev_key in self.__dict__:
                        self.__dict__[prev_key] += " "+parsed_line[0].strip()
                        break
                    i += 1
            else:
                key, val = parsed_line
                setattr(self, key.strip(), self.convert_booleans(val.strip()))

    def convert_booleans(self, line):
        booleans = {'True': True, 'False': False, 'None': None}
        if line not in booleans:
            return line
        return booleans[line]

    def __getattr__(self, attr):
        if attr not in self.__dict__:
            raise exceptions.ConfKeyError("the configuration file has no keyword: '%s'" % attr)

class LPMSConfig(ReadConfig):
    def __init__(self):
        config_file = os.path.join(cst.config_dir, cst.config_file)
        if not os.path.isfile(config_file):
            out.error("%s not found.")
            lpms.terminate()

        with open(config_file) as data:
            super(LPMSConfig, self).__init__(data.read().splitlines())
