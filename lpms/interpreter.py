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
import re
import sys
import time
import inspect
import traceback
import cPickle as pickle

import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import internals
from lpms import exceptions
from lpms import shelltools

from lpms.shelltools import touch
from lpms.operations import remove
from lpms import constants as cst

class ScriptEngine(internals.InternalFunctions):
    '''Runs lpms package scripts in a proper and safest way'''
    def __init__(self):
    #    super(Interpreter, self).__init__()
    #    self.environment = environment
    #    self.environment.get = self.get
    #    if self.environment.real_root is None:
    #        self.environment.real_root = cst.root
    #    self.script = script
        self.config = conf.LPMSConfig()
    #    self.get_build_libraries()
    #    self.function_collisions()

    def function_collisions(self):
        '''Checks the build environment to deal with function collisions if primary_library is not defined'''
        if self.environment.primary_library: return
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
        for library in self.environment.libraries:
            for preserved_name in preserved_names:
                if preserved_name in self.environment.raw:
                    continue
                if library+"_"+preserved_name in self.environment.raw:
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
        current_length = first_length = len(self.environment.libraries)

        for lib in self.environment.libraries:
            if len(lib.split("/")) == 2:
                lib_source, lib_name = lib.split("/")
                libfile = os.path.join(cst.repos, lib_source, "libraries", lib_name+".py")
                result.add(lib_name)
            else: 
                if len(self.environment.libraries) > first_length:
                    parent = self.environment.libraries[lib_index]
                    if len(parent.split("/")) == 2:
                        parents_repo = parent.split("/")[0]
                        result.add(lib)
                        libfile = os.path.join(cst.repos, parents_repo, "libraries", lib+".py")
                    else:
                        result.add(lib)
                        libfile = os.path.join(cst.repos, self.environment.repo, "libraries", lib+".py")
                else:
                    result.add(lib)
                    libfile = os.path.join(cst.repos, self.environment.repo, "libraries", lib+".py")

            if not os.path.isfile(libfile):
                out.error("build library not found: %s" % out.color(libfile, "red"))
                lpms.terminate()

            # import the script
            if not self.import_script(libfile):
                out.error("an error occured while processing the library: %s" \
                        % out.color(libfile, "red"))
                out.error("please report the above error messages to the library maintainer.")
                lpms.terminate()

            if len(self.environment.libraries) > current_length:
                lib_index = self.environment.libraries.index(lib)
                current_length = len(self.environment.libraries)

        self.environment.libraries = list(result)
    def run_func(self, func_name):
        getattr(self.environment, func_name)()

    def run_extract(self):
        # if the environment has no extract_plan variable, doesn't run extract function
        if not hasattr(self.environment, "extract_nevertheless") or not self.environment.extract_nevertheless:
            if not hasattr(self.environment, "extract_plan"): return
        target = os.path.dirname(self.environment.build_dir)
        extracted_file = os.path.join(os.path.dirname(target), ".extracted")
        if os.path.isfile(extracted_file):
            if self.environment.force_extract:
                shelltools.remove_file(extracted_file)
            else:
                out.write("%s %s/%s-%s had been already extracted.\n" % (out.color(">>", "brightyellow"), \
                    self.environment.category, self.environment.name, self.environment.version))
                return True

        utils.xterm_title("lpms: extracting %s/%s/%s-%s" % (self.environment.repo, self.environment.category, \
                self.environment.name, self.environment.version))
        out.notify("extracting archive(s) to %s" % os.path.dirname(self.environment.build_dir))
        
        # now, extract the archives
        self.run_stage("extract")
        out.notify("%s has been extracted." % self.environment.fullname)
        shelltools.touch(extracted_file)
        if self.environment.stage == "extract":
            lpms.terminate()

    def run_prepare(self):
        out.normal("preparing source...")
        prepared_file = os.path.join(os.path.dirname(os.path.dirname(self.environment.build_dir)), ".prepared")
        if os.path.isfile(prepared_file):
            out.warn_notify("%s had been already prepared." % self.environment.fullname)
            return True
        self.run_stage("prepare")
        out.notify("%s has been prepared." % self.environment.fullname)
        if not os.path.isfile(prepared_file):
            touch(prepared_file)
        if self.environment.stage == "prepare":
            lpms.terminate()

    def run_configure(self):
        utils.xterm_title("(%s/%s) lpms: configuring %s/%s-%s from %s" % (self.environment.index, self.environment.count, 
            self.environment.category, self.environment.name, self.environment.version, self.environment.repo))

        out.normal("configuring source in %s" % self.environment.build_dir)
        
        configured_file = os.path.join(os.path.dirname(os.path.dirname(
            self.environment.build_dir)), ".configured")
        
        if os.path.isfile(configured_file) and self.environment.resume_build:
            out.warn_notify("%s had been already configured." % self.environment.fullname)
            return True

        lpms.logger.info("configuring in %s" % self.environment.build_dir)
        
        self.run_stage("configure")
        out.notify("%s has been configured." % self.environment.fullname)

        if not os.path.isfile(configured_file):
            touch(configured_file)
        if self.environment.stage == "configure":
            lpms.terminate()

    def run_build(self):
        utils.xterm_title("(%s/%s) lpms: building %s/%s-%s from %s" % (self.environment.index, self.environment.count, 
            self.environment.category, self.environment.name, self.environment.version, self.environment.repo))
        out.normal("compiling source in %s" % self.environment.build_dir)
        built_file = os.path.join(os.path.dirname(os.path.dirname(
            self.environment.build_dir)), ".built")
        if os.path.isfile(built_file) and self.environment.resume_build:
            out.warn_notify("%s had been already built." % self.environment.fullname)
            return True
        
        lpms.logger.info("building in %s" % self.environment.build_dir)

        self.run_stage("build")
        out.notify("%s has been built." % self.environment.fullname)
        if not os.path.isfile(built_file):
            touch(built_file)
        if self.environment.stage == "build":
            lpms.terminate()
    
    def run_install(self):
        utils.xterm_title("(%s/%s) lpms: installing %s/%s-%s from %s" % (self.environment.index, self.environment.count, 
            self.environment.category, self.environment.name, self.environment.version, self.environment.repo))
        out.normal("installing %s to %s" % (self.environment.fullname, self.environment.install_dir))
        installed_file = os.path.join(os.path.dirname(os.path.dirname(
            self.environment.build_dir)), ".installed")

        if os.path.isfile(installed_file) and self.environment.resume_build:
            out.warn_notify("%s had been already installed." % self.environment.fullname)
            return True
        
        lpms.logger.info("installing to %s" % self.environment.build_dir)

        self.run_stage("install")
        if self.environment.docs is not None:
            for doc in self.environment.docs:
                if isinstance(doc, list) or isinstance(doc, tuple):
                    source_file, target_file = doc
                    namestr = self.environment.fullname if self.environment.slot != "0" else self.environment.name
                    target = self.environment.fix_target_path("/usr/share/doc/%s/%s" % (namestr, target_file))
                    source = os.path.join(self.environment.build_dir, source_file)
                #    self.environment.index, insfile(source, target)
                #else:
                #    self.environment.index, insdoc(doc)
        out.notify("%s has been installed." % self.environment.fullname)
        if not os.path.isfile(installed_file):
            touch(installed_file)
        if self.environment.stage == "install":
            lpms.terminate()

    def run_remove(self):
        utils.xterm_title("(%s/%s) lpms: removing %s/%s-%s from %s" % (self.environment.index, self.environment.count, 
            self.environment.category, self.environment.name, self.environment.version, self.environment.repo))
        remove.main((self.environment.repo, self.environment.category, self.environment.name, 
            self.environment.version), self.environment.real_root)

    def run_post_remove(self):
        # sandbox must be disabled
        self.environment.sandbox = False
        self.run_stage("post_remove")

    def run_pre_merge(self):
        out.normal("preparing system for the package...")
        pre_merge_file = os.path.join(os.path.dirname(os.path.dirname(self.environment.build_dir)), ".pre_merge")
        if os.path.isfile(pre_merge_file): 
            return True
        lpms.logger.info("running pre_merge function")
        # sandbox must be disabled
        self.environment.sandbox = False
        self.run_stage("pre_merge")
        if not os.path.isfile(pre_merge_file):
            touch(pre_merge_file)

    def run_pre_remove(self):
        # sandbox must be disabled
        self.environment.sandbox = False
        self.run_stage("pre_remove")

    def run_post_install(self):
        if self.environment.no_configure or self.environment.real_root != cst.root:
            out.warn_notify("skipping post_install function...")
            pkg_data = (self.environment.repo, self.environment.category, \
                    self.environment.name, self.environment.version)
            pending_file = os.path.join(self.environment.real_root, cst.configure_pending_file)
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
        self.environment.sandbox = False
        self.run_stage("post_install")

    def run_post_remove(self):
        # TODO: post_remove is the same thing with post_install, no-configure is valid?
        #if lpms.getopt("--no-configure"):
        #    out.warn_notify("post_remove function skipping...")
        #    return 
        
        # sandbox must be disabled
        self.environment.sandbox = False
        self.run_stage("post_remove")

    def run_stage(self, stage):
        self.environment.current_stage = stage
        standard_procedure_fixed = False
        exceptions = ('prepare', 'post_install', 'post_remove', 'pre_merge', 'pre_remove') 
        standard_procedure_exceptions = ('extract')
        
        if stage in standard_procedure_exceptions:
            if not self.environment.standard_procedure:
                self.environment.standard_procedure = True
                standard_procedure_fixed = True
        
        if stage in self.environment.raw:
            # run the packages's stage function
            self.run_func(stage)
            if standard_procedure_fixed:
                self.environment.standard_procedure = False
        else:
            if not self.environment.libraries and self.environment.standard_procedure \
                    and not stage in exceptions:
                        # run the standard stage function 
                        self.run_func("standard_"+stage)
                        if standard_procedure_fixed:
                            self.environment.standard_procedure = False
                        return True
            # if the stage is not defined in the spec, find it in the build helpers.
            for lib in self.environment.libraries:
                if self.environment.standard_procedure and lib+"_"+stage in self.environment.raw:
                    if self.environment.primary_library:
                        if self.environment.primary_library == lib:
                            self.run_func(lib+"_"+stage)
                            if standard_procedure_fixed:
                                self.environment.standard_procedure = False
                            return True
                    else:
                        self.run_func(lib+"_"+stage)
                        if standard_procedure_fixed:
                            self.environment.standard_procedure = False
                        return True
            # if the build helpers don't include the stage, run the standard function if it is possible.
            if self.environment.standard_procedure and not stage in exceptions:
                self.run_func("standard_"+stage)
                if standard_procedure_fixed:
                    self.environment.standard_procedure = False
                    return True

    def initialize(self, environment, operation_order=None, remove=False):
        '''Initializes interpreter and drives script interpreting matter'''
        self.environment = environment
        self.environment.get = self.get
        if self.environment.real_root is None:
            self.environment.real_root = cst.root
        self.get_build_libraries()
        self.function_collisions()

        if not remove and not operation_order:
            operation_order = [
                    'extract',
                    'configure', 
                    'build', 
                    'install',
            ]
            
            if 'prepare' in self.environment.raw:
                index = 0
                if len(operation_order) == 4: 
                    index = 1
                operation_order.insert(index, 'prepare')
            else:
                index = 0
                if len(operation_order) == 4: index = 1
                for library in self.environment.libraries:
                    if library+"_prepare" in self.environment.raw:
                        operation_order.insert(index, 'prepare')
                        break

            #if 'pre_merge' in self.environment.raw:
            #    index = operation_order.index('merge')
            #    operation_order.insert(index, 'pre_merge')
            #else:
            #    index = operation_order.index('merge')
            #    for library in self.environment.libraries:
            #        if library+"_pre_merge" in self.environment.raw:
            #            operation_order.insert(index, 'pre_merge')
            #            break

            if 'post_install' in self.environment.raw:
                operation_order.insert(len(operation_order), 'post_install')
            else:
                for library in self.environment.libraries:
                    if library+"_post_install" in self.environment.raw:
                        operation_order.insert(len(operation_order), 'post_install')
                        break

        if remove and 'pre_remove' in self.environment.raw and not 'pre_remove' in operation_order:
            operation_order.insert(0, 'pre_remove')

        if remove and 'post_remove' in self.environment.raw and not 'post_remove' in operation_order:
            operation_order.insert(len(operation_order), 'post_remove')

        def parse_traceback(exception_type=None):
            '''Parse exceptions and show nice and more readable error messages'''
            out.write(out.color(">>", "brightred")+" %s/%s/%s-%s\n" % (self.environment.repo, self.environment.category, 
                self.environment.name, self.environment.version))
            exc_type, exc_value, exc_traceback = sys.exc_info()
            formatted_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            if not self.environment.debug:
                for item in formatted_lines:
                    item = item.strip()
                    if item.startswith("File"):
                        regex = re.compile(r'(\w+)\S*$')
                        regex = regex.search(item)
                        if regex is None:
                            continue
                        if regex.group() in operation_order:
                            line = re.compile(r'[^\d.]+')
                            line = line.sub('', item)
                            out.write("%s %s " % (out.color("on line %s:" % line, "red"), formatted_lines[-1]))
                            break
            else:
                traceback.print_exc()
            out.error("an error occurred when running the %s function." % out.color(operation, "red"))
            return False

        for operation in operation_order:
            """if operation in ("merge", "remove"):
                if shelltools.is_exists(cst.lock_file):
                    with open(cst.lock_file) as _file:
                        if not _file.readline() in utils.get_pid_list():
                            shelltools.remove_file(cst.lock_file)
                        else:
                            out.warn("Ehmm.. Seems like another lpms process is still going on. Waiting 3 seconds for it to finish.")
                            while True:
                                if shelltools.is_exists(cst.lock_file):
                                    time.sleep(3)
                                else: break
                shelltools.echo(os.getpid(), cst.lock_file)
            """
            method = getattr(self, "run_"+operation)
            try:
                if self.environment.build_dir is not None and os.getcwd() != self.environment.build_dir:
                    os.chdir(self.environment.build_dir)
                method()
            except KeyboardInterrupt:
                # Return None as retval because this is neither an error nor successfully completed operation. 
                # This is an user interrupt.
                return None, self.environment
            except SystemExit:
                # FIXME: Which conditions have raised SystemExit exception?
                return False, self.environment
            except exceptions.BuildError:
                return parse_traceback("BuildError"), self.environment
            except exceptions.BuiltinError:
                return parse_traceback("BuiltinError"), self.environment
            except:
                return parse_traceback(), self.environment
        return True, self.environment
