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

from lpms import constants as cst 

class Environment(object):
    pass
    #def __init__(self):
    #    pass
        #self.__dict__["pkgname"] = pkgname

class InternalFuncs(object):
    def __init__(self):
        self.env = Environment()
        self.env.libraries = []
        self.env.sandbox_valid_dirs = []
        self.env.backup = []
        self.env.__setattr__("standart_procedure", True)
        self.env.__setattr__("standard_procedure", True)
  
        # FIXME: use a better method for environment functions.
        self.env.__dict__['get'] = self.get
        for f in cst.environmental_files:
            self.import_script(os.path.join(cst.lpms_path, f))

    def import_script(self, script_path):
        exec compile(open(script_path).read(), "error", "exec") in self.env.__dict__
        
    def get(self, *libs):
        self.env.libraries = libs
