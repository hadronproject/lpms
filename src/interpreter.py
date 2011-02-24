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

# Main interpreter for build scripts.

import os

import lpms
from lpms import out
from lpms import conf
from lpms import utils
from lpms.exceptions import *
from lpms.shelltools import touch
from lpms import constants as cst

class Interpreter(object):
    def __init__(self, script, env):
        self.env = env
        self.env.__setattr__("standart_procedure", True)
        self.script = script
        self.config = conf.LPMSConfig()
        for bi in ('builtins.py', 'buildtools.py'):
            self.import_script(os.path.join(cst.lpms_path, bi))
        try:
            self.env.__setattr__("libraries", self.env.__builtins__["libraries"])
        except KeyError:
            self.env.__setattr__("libraries", [])
        self.import_script(self.script)
        self.get_build_libraries()

    def get_build_libraries(self):
        for lib in self.env.libraries:
            self.import_script(os.path.join(cst.repos, self.env.repo, "libraries", lib+".py"))

    def run_func(self, func_name):
        def run_with_sandbox(func_name):
            import catbox
            valid_dirs = utils.sandbox_dirs()
            valid_dirs.append(self.config.build_dir)
            for i in ('build_dir', 'install_dir'):
                valid_dirs.append(getattr(self.env, i))
            # run in catbox
            ret = catbox.run(getattr(self.env, func_name),
                    valid_dirs,
                    logger=self.sandbox_logger)

            if ret.code != 0:
                raise BuiltinError

            if len(ret.violations) != 0:
                out.brightred("Sandbox Violations!!!\n")
                out.normal("results:")
                for result in ret.violations:
                    out.notify("%s (%s -> %s)" % (result[0], result[1], result[2]))
                lpms.catch_error("please contact package maintainer.")

        def run_without_sandbox(func_name):
            getattr(self.env, func_name)()

        if self.env.sandbox:
            run_with_sandbox(func_name)
        else:
            run_without_sandbox(func_name)

    def sandbox_logger(self, command, path, canonical_path):
        pass

    def run_prepare(self):
        out.normal("preparing source...")
        prepared_file = os.path.join(self.env.build_dir.split("source")[0],
                ".prepared")
        if os.path.isfile(prepared_file): 
            #and lpms.getopt("--resume-build"):
            out.warn_notify("source already prepared.")
            return True
        self.run_stage("prepare")
        out.notify("source prepared.")
        if not os.path.isfile(prepared_file):
            touch(prepared_file)
        if self.env.stage == "prepare":
            lpms.terminate()

    def run_configure(self):
        out.normal("configuring source in %s" % self.env.build_dir)
        configured_file = os.path.join(self.env.build_dir.split("source")[0],
                ".configured")
        if os.path.isfile(configured_file) and lpms.getopt("--resume-build"):
            out.warn_notify("source already configured.")
            return True
        self.run_stage("configure")
        out.notify("source configured")
        if not os.path.isfile(configured_file):
            touch(configured_file)
        if self.env.stage == "configure":
            lpms.terminate()

    def run_build(self):
        out.normal("compiling source in %s" % self.env.build_dir)
        built_file = os.path.join(self.env.build_dir.split("source")[0],
            ".built")
        if os.path.isfile(built_file) and lpms.getopt("--resume-build"):
            out.warn_notify("source already built.")
            return True
        self.run_stage("build")
        out.notify("source compiled")
        if not os.path.isfile(built_file):
            touch(built_file)
        if self.env.stage == "build":
            lpms.terminate()
    
    def run_install(self):
        out.normal("installing %s to %s" % (self.env.full_name, self.env.install_dir))
        installed_file = os.path.join(self.env.build_dir.split("source")[0],
            ".installed")
        if os.path.isfile(installed_file) and lpms.getopt("--resume-build"):
            out.warn_notify("source already installed.")
            return True
        self.run_stage("install")
        out.notify("%s/%s installed." % (self.env.category, self.env.full_name))
        if not os.path.isfile(installed_file):
            touch(installed_file)
        if self.env.stage == "install":
            lpms.terminate()
  
    def run_post_install(self):
        pass
    
    def run_stage(self, stage):
        # firstly, we find a configuration function in environment
        if stage in self.env.__dict__.keys():
            # if it is exists, run it
            self.run_func(stage)
        else:
            if len(self.env.libraries) == 0 and self.env.standart_procedure:
                self.run_func("standard_"+stage)
                # and now, search build libraries' configuration function
            for lib in self.env.libraries:
                if self.env.standart_procedure and lib+"_"+stage in self.env.__dict__.keys():
                    self.run_func(lib+"_"+stage)
                else:
                    if self.env.standart_procedure and (stage != "post_install" or stage != "post_remove"):
                        self.run_func("standard_"+stage)

    def import_script(self, script_path):
        exec compile(open(script_path).read(), "error", "exec") in self.env.__dict__

def run(script, env):
    ipr = Interpreter(script, env)
    operation_order = ['configure', 'build', 'install']
    if 'prepare' in env.__dict__.keys():
        operation_order.insert(0, 'prepare')
    elif 'post_install' in env.__dict__.keys():
        operation_order.insert(-1, 'post_install')

    # FIXME: we need more flow control
    for opr in operation_order:
        method = getattr(ipr, "run_"+opr)
        try:
            method()
        except (BuiltinError, MakeError):
            out.error("an error occurred when running the %s function." % out.color(opr, "red"))
            lpms.terminate()
        except (AttributeError, NameError), err: 
            import traceback
            traceback.print_exc(err)
            out.error("an error occurred when running the %s function." % out.color(opr, "red"))
            lpms.terminate()
