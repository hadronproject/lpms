# Copyright 2009 - 2014 Burak Sezer <purak@hadronproject.org>
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

from lpms import exceptions
from lpms import constants as cst


class Environment(object):
    """
    Main object container for package related operations
    """
    def __getattr__(self, key):
        if key in self.__dict__:
            return self.__dict__[key]
        return None

    @property
    def raw(self):
        return self.__dict__


class InternalFunctions(object):
    """
    An object that stores internal environment
    """
    def __init__(self):
        self.env = Environment()
        self.env.libraries = []
        self.env.reserve_files = []
        self.env.current_stage = None
        self.env.config = ""
        self.env.sandbox_valid_dirs = []
        self.env.backup = []

        primitives = {
                "primary_library": None,
                "standard_procedure": True,
                "get": self.get, 
                "BuiltinError": exceptions.BuiltinError
        }

        for key in primitives:
            setattr(self.env, key, primitives[key])

        for builtin_file in cst.builtin_files:
            if not self.import_script(os.path.join(cst.lpms_path, builtin_file)):
                sys.stdout.write(">> An error occured while importing built-in functions of lpms.\n")
                sys.stdout.write("Please log in to http://bugs.hadronproject.org")
                sys.stdout.write("and report that error to lpms team.")
                sys.stdout.write("Bye ;)\n")
                raise SystemExit(0)

    def import_script(self, script_path):
        """
        Compiles and imports given script
        """
        try:
            if hasattr(self, "env"):
                exec compile(open(script_path).read(), \
                        "error", "exec") in self.env.raw
            else:
                exec compile(open(script_path).read(), \
                        "error", "exec") in self.environment.raw
        except:
            # TODO: We must handle exceptions more cleverly
            traceback.print_exc()
            return False
        return True

    def get(self, *libs):
        """
        Stores given library names to import in the next stages
        """
        self.env.libraries.extend(libs)

