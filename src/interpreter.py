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
import traceback
import cPickle as pickle


import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import internals
from lpms import shelltools
from lpms.exceptions import *
from lpms.shelltools import touch
from lpms.operations import merge
from lpms import constants as cst

class Interpreter(internals.InternalFuncs):
    def __init__(self, script, env):
        super(Interpreter, self).__init__()
        self.env = env
        self.env.__setattr__("get", self.get)
        self.script = script
        self.config = conf.LPMSConfig()
        self.get_build_libraries()
        self.startup_funcs()

    def get_build_libraries(self):
        for lib in self.env.libraries:
            if len(lib.split("/")) == 2:
                lib_source, lib_name = lib.split("/")
                libfile = os.path.join(cst.repos, lib_source, "libraries", lib_name+".py")
                self.env.libraries[self.env.libraries.index(lib)] = lib_name
            else:
                libfile = os.path.join(cst.repos, self.env.repo, "libraries", lib+".py")
            
            if not os.path.isfile(libfile):
                out.error("build library not found: %s" % out.color(libfile, "red"))
                lpms.terminate()

            # import the script
            print libfile
            self.import_script(libfile)

    def startup_funcs(self):
        for library in [m for m in self.env.__dict__ if "_library_start" in m]:
            for func in getattr(self.env, library):
                try:
                    # run given function that's defined in environment
                    func()
                except:
                    traceback.print_exc()
                    out.error("an error occured while running the %s from %s library" % 
                            (out.color(func.__name__, "red"), out.color(library, "red")))
                    lpms.terminate()

    def run_func(self, func_name):
        def run_with_sandbox(func_name):
            try:
                import catbox
            except ImportError as err:
                lpms.catch_error("catbox could not imported, please check it!")

            self.env.sandbox_valid_dirs = utils.sandbox_dirs()
            self.env.sandbox_valid_dirs.append(self.config.build_dir)
            for i in ('build_dir', 'install_dir'):
                self.env.sandbox_valid_dirs.append(getattr(self.env, i))
            # run in catbox
            ret = catbox.run(getattr(self.env, func_name),
                    self.env.sandbox_valid_dirs,
                    logger=self.sandbox_logger)

            if ret.code != 0:
                raise BuiltinError

            if len(ret.violations) != 0:
                out.brightred("sandbox violations in %s/%s/%s-%s!\n" % (self.env.repo, 
                    self.env.category, self.env.pkgname, self.env.version))
                out.normal("results:")
                for result in ret.violations:
                    out.notify("%s (%s -> %s)" % (result[0], result[1], result[2]))
                out.error("sandbox violations detected while running %s" % out.color(func_name, "red"))
                lpms.terminate()

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
        utils.xterm_title("(%s/%s) lpms: configuring %s/%s-%s from %s" % (self.env.i, self.env.count, 
            self.env.category, self.env.pkgname, self.env.version, self.env.repo))

        out.normal("configuring source in %s" % self.env.build_dir)
        
        configured_file = os.path.join(os.path.dirname(os.path.dirname(
            self.env.build_dir)), ".configured")
        
        if os.path.isfile(configured_file) and lpms.getopt("--resume-build"):
            out.warn_notify("source already configured.")
            return True

        lpms.logger.info("configuring in %s" % self.env.build_dir)
        
        self.run_stage("configure")
        out.notify("source configured")

        if not os.path.isfile(configured_file):
            touch(configured_file)
        if self.env.stage == "configure":
            lpms.terminate()

    def run_build(self):
        utils.xterm_title("(%s/%s) lpms: building %s/%s-%s from %s" % (self.env.i, self.env.count, 
            self.env.category, self.env.pkgname, self.env.version, self.env.repo))
        out.normal("compiling source in %s" % self.env.build_dir)
        built_file = os.path.join(os.path.dirname(os.path.dirname(
            self.env.build_dir)), ".built")
        if os.path.isfile(built_file) and lpms.getopt("--resume-build"):
            out.warn_notify("source already built.")
            return True
        
        lpms.logger.info("building in %s" % self.env.build_dir)

        self.run_stage("build")
        out.notify("source compiled")
        if not os.path.isfile(built_file):
            touch(built_file)
        if self.env.stage == "build":
            lpms.terminate()
    
    def run_install(self):
        utils.xterm_title("(%s/%s) lpms: installing %s/%s-%s from %s" % (self.env.i, self.env.count, 
            self.env.category, self.env.pkgname, self.env.version, self.env.repo))
        out.normal("installing %s to %s" % (self.env.fullname, self.env.install_dir))
        installed_file = os.path.join(os.path.dirname(os.path.dirname(
            self.env.build_dir)), ".installed")

        if os.path.isfile(installed_file) and lpms.getopt("--resume-build"):
            out.warn_notify("source already installed.")
            return True
        
        lpms.logger.info("installing to %s" % self.env.build_dir)

        self.run_stage("install")
        out.notify("%s/%s installed." % (self.env.category, self.env.fullname))
        if not os.path.isfile(installed_file):
            touch(installed_file)
        if self.env.stage == "install":
            lpms.terminate()

    def run_merge(self):
        utils.xterm_title("(%s/%s) lpms: merging %s/%s-%s from %s" % (self.env.i, self.env.count, 
            self.env.category, self.env.pkgname, self.env.version, self.env.repo))
        if lpms.getopt("--no-merge"):
            out.write("no merging...\n")
            lpms.terminate()

        merge.main(self.env)

    def run_post_install(self):
        if lpms.getopt("--no-configure") or self.env.real_root != cst.root:
            out.warn_notify("post_install function skipping...")
            pkg_data = (self.env.repo, self.env.category, \
                    self.env.name, self.env.version)

            pending_file = os.path.join(self.env.real_root, cst.configure_pending_file)
            if not os.path.exists(pending_file):
                with open(pending_file, "wb") as _data:
                    pickle.dump([pkg_data], _data)
            else:
                data = []
                with open(pending_file, "rb") as _data:
                    pending_packages = pickle.load(_data)
                    if not pkg_data in pending_packages:
                        data.append(pkg_data)

                    data.extend(pending_packages)
                shelltools.remove_file(pending_file)
                with open(pending_file, "wb") as _data:
                    pickle.dump(data, _data)
            return

        # sandbox must be disabled
        self.env.sandbox = False

        self.run_stage("post_install")

    def run_post_remove(self):
        if lpms.getopt("--no-configure"):
            out.warn_notify("post_remove function skipping...")
            return 
        
        # sandbox must be disabled
        self.env.sandbox = False
        
        self.run_stage("post_remove")

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

def run(script, env, operation_order=None):
    ipr = Interpreter(script, env)
    if not operation_order:
        operation_order = ['configure', 'build', 'install', 'merge']

    if 'prepare' in env.__dict__.keys():
        operation_order.insert(0, 'prepare')
    
    if 'post_install' in env.__dict__.keys() and not 'post_install' in operation_order:
        operation_order.insert(len(operation_order), 'post_install')

    # FIXME: we need more flow control
    for opr in operation_order:
        method = getattr(ipr, "run_"+opr)
        try:
            method()
        except (BuiltinError, MakeError):
            out.write(out.color(">>", "brightred")+" %s/%s/%s-%s\n" % (ipr.env.repo, ipr.env.category, 
                ipr.env.pkgname, ipr.env.version))
            out.error("an error occurred when running the %s function." % out.color(opr, "red"))
            return False
            #lpms.terminate()
        except (AttributeError, NameError), err: 
            out.write(out.color(">>", "brightred")+" %s/%s/%s-%s\n" % (ipr.env.repo, ipr.env.category, 
                ipr.env.pkgname, ipr.env.version))
            traceback.print_exc(err)
            out.error("an error occurred when running the %s function." % out.color(opr, "red"))
            return False
            #lpms.terminate()
    return True
