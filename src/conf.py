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
import ConfigParser

from lpms import constants as cst

class ReadConfig(object):
    def __init__(self, conf_path):
        for atr in file(conf_path).read().strip().split('\n'):
            if not atr.startswith("[") and not atr.startswith("#"):
                if len(atr.split("=")) > 1:
                    data = atr.split("=")
                    self.__dict__[data[0].strip()] = "=".join(data[1:]).strip()

class LPMSConfig(ReadConfig):
    def __init__(self):
        super(LPMSConfig, self).__init__(os.path.join(cst.config_dir, cst.config_file))

class RepoConfig(ReadConfig):
    def __init__(self, repo_path):
        #repo_config = os.path.join(cst.repos, repo_name, "info/repo.conf")
        super(RepoConfig, self).__init__(repo_path)


