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
import traceback

from lpms import constants as cst 

class Environment(object):
    '''Main object container for lpms operations'''
    pass

class InternalFuncs(object):
    '''The starting point of an lpms operation'''
    def __init__(self):
        self.env = Environment()
        self.env.libraries = []
        self.env.reserve_files = []
        self.env.current_stage = None
        self.env.config = ""
        self.env.sandbox_valid_dirs = []
        self.env.backup = []

        setattr(self.env, "standard_procedure", True)
        setattr(self.env, "primary_library", None)

        # FIXME: use a better method for environment functions.
        builtin_funcs = {"get": self.get}
        for key in builtin_funcs:
            setattr(self.env, key, builtin_funcs[key])

        for builtin_file in cst.builtin_files:
            if not self.import_script(os.path.join(cst.lpms_path, builtin_file)):
                print("there are some problems in lpms' builtin libraries.")
                print("this may be a serious bug. you should report it.")
                raise SystemExit(0)

    def import_script(self, script_path):
        try:
            exec compile(open(script_path).read(), "error", "exec") in self.env.__dict__
        except:
            traceback.print_exc()
            return False
        return True

    def get(self, *libs):
        self.env.libraries.extend(libs)

