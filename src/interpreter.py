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
import time
import traceback
import cPickle as pickle

import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import internals
from lpms import exceptions
from lpms import shelltools
from lpms import file_collisions

from lpms.shelltools import touch
from lpms.operations import merge
from lpms.operations import remove
from lpms import constants as cst

class Interpreter(internals.InternalFuncs):
    def __init__(self, script, env):
        super(Interpreter, self).__init__()
        self.env = env
        self.env.__setattr__("get", self.get)
        if self.env.real_root is None:
            self.env.real_root = cst.root
        self.script = script
        self.config = conf.LPMSConfig()
        self.get_build_libraries()
        self.function_collisions()
        self.startup_funcs()

    def function_collisions(self):
        '''Checks the build environment to deal with function collisions if primary_library is not defined'''
        if self.env.primary_library: return
        preserved_names = [
                'extract', 
                'prepare', 
                'configure', 
                'build', 
                'install',
                'collision_check', 
                'pre_merge', 
                'post_install'
                'remove'
        ]

        race_list = {}
        for library in self.env.libraries:
            for preserved_name in preserved_names:
                if preserved_name in self.env.__dict__:
                    continue
                if library+"_"+preserved_name in self.env.__dict__:
                    if preserved_name in race_list:
                        if not library in race_list[preserved_name]:
                            race_list[preserved_name].append(library)
                    else:
                        race_list.update({preserved_name: [library]})
                        
        result = [(key, race_list[key]) for key in race_list if len(race_list[key]) > 1]
        if result:
            out.warn("function collision detected in these stages. you should use primary_library keyword.")
            for item in result:
                stage, libraries = item
                out.notify(stage+": "+", ".join(libraries))
            lpms.terminate("please contact the package maintainer.")

    def get_build_libraries(self):
        result = set()
        lib_index = None
        current_length = first_length = len(self.env.libraries)

        for lib in self.env.libraries:
            if len(lib.split("/")) == 2:
                lib_source, lib_name = lib.split("/")
                libfile = os.path.join(cst.repos, lib_source, "libraries", lib_name+".py")
                result.add(lib_name)
            else: 
                if len(self.env.libraries) > first_length:
                    parent = self.env.libraries[lib_index]
                    if len(parent.split("/")) == 2:
                        parents_repo = parent.split("/")[0]
                        result.add(lib)
                        libfile = os.path.join(cst.repos, parents_repo, "libraries", lib+".py")
                    else:
                        result.add(lib)
                        libfile = os.path.join(cst.repos, self.env.repo, "libraries", lib+".py")
                else:
                    result.add(lib)
                    libfile = os.path.join(cst.repos, self.env.repo, "libraries", lib+".py")

            if not os.path.isfile(libfile):
                out.error("build library not found: %s" % out.color(libfile, "red"))
                lpms.terminate()

            # import the script
            if not self.import_script(libfile):
                out.error("an error occured while processing the library: %s" \
                        % out.color(libfile, "red"))
                out.error("please report the above error messages to the library maintainer.")
                lpms.terminate()

            if len(self.env.libraries) > current_length:
                lib_index = self.env.libraries.index(lib)
                current_length = len(self.env.libraries)

        self.env.libraries = list(result)

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
        getattr(self.env, func_name)()

    def run_extract(self):
        # if the environment has no extract_plan variable, doesn't run extract function
        if not hasattr(self.env, "extract_plan"): return
        target = os.path.dirname(self.env.build_dir)
        extracted_file = os.path.join(os.path.dirname(target), ".extracted")
        if os.path.isfile(extracted_file):
            if lpms.getopt("--force-unpack"):
                shelltools.remove_file(extracted_file)
            else:
                out.warn("%s/%s-%s seems already unpacked." % (self.env.category, self.env.name, self.env.version))
                return True

        utils.xterm_title("lpms: extracting %s/%s/%s-%s" % (self.env.repo, self.env.category, \
                self.env.name, self.env.version))
        out.notify("extracting archive(s) to %s" % os.path.dirname(self.env.build_dir))
        # now, extract the archives
        self.run_stage("extract")
        out.notify("source extracted")
        shelltools.touch(extracted_file)
        if self.env.stage == "extract":
            lpms.terminate()

    def run_prepare(self):
        out.normal("preparing source...")
        prepared_file = os.path.join(self.env.build_dir.split("source")[0],
                ".prepared")
        if os.path.isfile(prepared_file): 
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

    def run_remove(self):
        utils.xterm_title("(%s/%s) lpms: removing %s/%s-%s from %s" % (self.env.i, self.env.count, 
            self.env.category, self.env.pkgname, self.env.version, self.env.repo))

        remove.main((self.env.repo, self.env.category, self.env.pkgname, 
            self.env.version), self.env.real_root)

    def run_post_remove(self):
        # sandbox must be disabled
        self.env.sandbox = False
        self.run_stage("post_remove")

    def run_collision_check(self):
        out.normal("checking file collisions...")
        lpms.logger.info("checking file collisions")
        collision_object = file_collisions.CollisionProtect(self.env.category, self.env.name, \
                self.env.slot, real_root=self.env.real_root, source_dir=self.env.install_dir)
        collision_object.handle_collisions()
        
        if collision_object.orphans:
            out.write(out.color(" > ", "brightyellow")+"these files are orphan. the package will adopt the files:\n")
            index = 0
            for orphan in collision_object.orphans:
                out.notify(orphan)
                index += 1
                if index > 100:
                    # FIXME: the files must be logged
                    out.write(out.color(" > ", "brightyellow")+"...and many others.")
                    break

        if collision_object.collisions:
            out.write(out.color(" > ", "brightyellow")+"file collisions detected:\n")
        for item in collision_object.collisions:
            (category, name, slot, version), path = item
            out.write(out.color(" -- ", "red")+category+"/"+name+"-"\
                    +version+":"+slot+" -> "+path+"\n")
        if collision_object.collisions and self.config.collision_protect and not \
                lpms.getopt('--force-file-collision'):
                    out.write("quitting...\n")
                    lpms.terminate()

    def run_pre_merge(self):
        out.normal("preparing system for the package...")
        pre_merge_file = os.path.join(os.path.dirname(os.path.dirname(self.env.build_dir)), ".pre_merge")

        if os.path.isfile(pre_merge_file): return True
        
        lpms.logger.info("running pre_merge function")

        # sandbox must be disabled
        self.env.sandbox = False
        self.run_stage("pre_merge")

        if not os.path.isfile(pre_merge_file):
            touch(pre_merge_file)

    def run_pre_remove(self):
        # sandbox must be disabled
        self.env.sandbox = False
        self.run_stage("pre_remove")

    def run_post_install(self):
        if lpms.getopt("--no-configure") or self.env.real_root != cst.root:
            out.warn_notify("post_install function skipping...")
            pkg_data = (self.env.repo, self.env.category, \
                    self.env.name, self.env.version)

            pending_file = os.path.join(self.env.real_root, cst.configure_pending_file)
            shelltools.makedirs(os.path.dirname(pending_file))
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
        self.env.current_stage = stage
        standard_procedure_fixed = False
        exceptions = ('prepare', 'post_install', 'post_remove', 'pre_merge', 'pre_remove') 
        standard_procedure_exceptions = ('extract')
        
        if stage in standard_procedure_exceptions:
            if not self.env.standard_procedure:
                self.env.standard_procedure = True
                standard_procedure_fixed = True
        
        if stage in self.env.__dict__:
            # run the packages's stage function
            self.run_func(stage)
            if standard_procedure_fixed:
                self.env.standard_procedure = False
        else:
            if not self.env.libraries and self.env.standard_procedure \
                    and not stage in exceptions:
                        # run the standard stage function 
                        self.run_func("standard_"+stage)
                        if standard_procedure_fixed:
                            self.env.standard_procedure = False
                        return True
            # if the stage is not defined in the spec, find it in the build helpers.
            for lib in self.env.libraries:
                if self.env.standard_procedure and lib+"_"+stage in self.env.__dict__:
                    if self.env.primary_library:
                        if self.env.primary_library == lib:
                            self.run_func(lib+"_"+stage)
                            if standard_procedure_fixed:
                                self.env.standard_procedure = False
                            return True
                    else:
                        self.run_func(lib+"_"+stage)
                        if standard_procedure_fixed:
                            self.env.standard_procedure = False
                        return True
            # if the build helpers don't include the stage, run the standard function if it is possible.
            if self.env.standard_procedure and not stage in exceptions:
                self.run_func("standard_"+stage)
                if standard_procedure_fixed:
                    self.env.standard_procedure = False
                    return True

def run(script, env, operation_order=None, remove=False):
    ipr = Interpreter(script, env)
    #firstly, prepare operation_order
    if not remove and not operation_order:
        operation_order = [
                'extract',
                'configure', 
                'build', 
                'install',
                'collision_check', 
                'merge', 
        ]
        
        if 'prepare' in ipr.env.__dict__:
            index = 0
            if len(operation_order) == 6: index = 1
            operation_order.insert(index, 'prepare')
        else:
            index = 0
            if len(operation_order) == 6: index = 1
            for library in ipr.env.libraries:
                if library+"_prepare" in ipr.env.__dict__:
                    operation_order.insert(index, 'prepare')
                    break

        if 'pre_merge' in ipr.env.__dict__:
            index = operation_order.index('merge')
            operation_order.insert(index, 'pre_merge')
        else:
            index = operation_order.index('merge')
            for library in ipr.env.libraries:
                if library+"_pre_merge" in ipr.env.__dict__:
                    operation_order.insert(index, 'pre_merge')
                    break
        
        if 'post_install' in ipr.env.__dict__:
            operation_order.insert(len(operation_order), 'post_install')
        else:
            index = operation_order.index('merge')
            for library in ipr.env.libraries:
                if library+"_post_install" in ipr.env.__dict__:
                    operation_order.insert(len(operation_order), 'post_install')
                    break

    if remove and 'pre_remove' in env.__dict__ and not 'pre_remove' in operation_order:
        operation_order.insert(0, 'pre_remove')

    if remove and 'post_remove' in env.__dict__ and not 'post_remove' in operation_order:
        operation_order.insert(len(operation_order), 'post_remove')
        
    def parse_error(exception=True):
        '''Parse Python related errors'''
        out.write(out.color(">>", "brightred")+" %s/%s/%s-%s\n" % (ipr.env.repo, ipr.env.category, 
            ipr.env.pkgname, ipr.env.version))
        if exception: traceback.print_exc(err)
        out.error("an error occurred when running the %s function." % out.color(opr, "red"))
        return False

    # FIXME: we need more flow control
    for opr in operation_order:
        if opr in ("merge", "remove"):
            if shelltools.is_exists(cst.lock_file):
                with open(cst.lock_file) as _file:
                    if not _file.readline() in utils.get_pid_list():
                        shelltools.remove_file(cst.lock_file)
                    else:
                        out.warn("Ehmm.. Seems like another lpms process is still going on. Waiting for it to finish.")
                        while True:
                            if shelltools.is_exists(cst.lock_file):
                                time.sleep(3)
                            else: break
            shelltools.echo(os.getpid(), cst.lock_file)

        method = getattr(ipr, "run_"+opr)
        try:
            method()
        except SyntaxError as err:
            return parse_error()
        except AttributeError as err:
            return parse_error()
        except NameError as err:
            return parse_error()
        except exceptions.NotExecutable as err:
            return parse_error()
        except exceptions.CommandFailed as err: 
            return parse_error()
    return True
