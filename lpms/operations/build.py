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
# You should have received a copy of the GNU General Public Licens
# along with lpms.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import time
import glob

import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import fetcher
from lpms import internals
from lpms import initpreter
from lpms import shelltools
from lpms import interpreter
from lpms import constants as cst

from lpms.db import api
from lpms.operations import merge
from lpms.exceptions import BuildError

class Build(object):
    '''
    This class reads the specs and prepares the environment for later operations. 
    Finally, it runs interpreter for building.
    '''
    def __init__(self, data_bundle, instructions):
        self.data_bundle = data_bundle
        self.instructions = instructions
        self.repodb = api.RepositoryDB()
        self.instdb = api.InstallDB()
        self.download_plan = []
        self.extract_plan = []
        self.urls = []
        self.internals = internals.InternalFuncs()
        self.internals.env.__dict__.update(
                {
                    "get": self.internals.get,
                    "cmd_options": [],
                    "options": []
                }
        )
        self.spec_file = None
        self.config = conf.LPMSConfig()
        if not self.instructions.unset_env_variables:
            utils.set_environment_variables()
        self.revisioned = False
        self.revision = None

    def set_local_environment_variables(self):
        '''
        Sets environment variables such as CFLAGS, CXXFLAGS and LDFLAGS if the user
        defines a local file which is included them
        '''
        switches = ["ADD", "REMOVE", "GLOBAL"]
        for item in cst.local_env_variable_files:
            if not os.access(item, os.R_OK):
                continue
            variable_type = item.split("/")[-1].upper()
            with open(item) as data:
                for line in data.readlines():
                    add = []; remove = []; global_flags = []
                    if line.startswith("#"):
                        continue
                    myline = [i.strip() for i in line.split(" ")]
                    target = myline[0]
                    if len(target.split("/")) == 2:
                        if target != self.internals.env.category+"/"+self.internals.env.name:
                            continue
                    elif len(target.split("/")) == 1:
                        if target != self.internals.env.category:
                            if len(target.split("-")) == 1:
                                out.warn("warning: invalid line found in %s:" % item)
                                out.red("   "+line)
                            continue
                    else:
                        if len(target.split("-")) == 1:
                            out.warn("warning: invalid line found in %s:" % item)
                            out.red("   "+line)
                            continue

                    if variable_type == "ENV":
                        if myline[1] == "UNSET":
                            variable = myline[2]
                            if variable in os.environ:
                                del os.environ[variable]
                        else:
                            try:
                                variable, value = myline[1:]
                            except ValueError:
                                out.warn("warning: invalid line found in %s:" % item)
                                out.red("   "+line)
                            else:
                                os.environ[variable] = value

                    for switch in switches:
                        if not switch in myline[1:]:
                            continue
                        switch_index = myline.index(switch)
                        for word in myline[switch_index+1:]:
                            if word in switches: 
                                break
                            if switch == "GLOBAL":
                                global_flags.append(word)
                            if switch == "ADD":
                                add.append(word)
                            elif switch == "REMOVE":
                                remove.append(word)
                    
                    if global_flags:
                        if variable_type in os.environ:
                            del os.environ[variable_type]
                            os.environ[variable_type] = " ".join(global_flags)
                    else:
                        if add:
                            if variable_type in os.environ:
                                current = os.environ[variable_type]
                                current += " "+" ".join(add)
                                os.environ[variable_type] = current
                            else:
                                out.warn("%s not defined in your environment" % variable_type)
                        if remove:
                            if variable_type in os.environ:
                                current = os.environ[variable_type]
                                new = [atom for atom in current.split(" ") if not atom in remove]
                                os.environ[variable_type] = " ".join(new)
                            else:
                                out.warn("%s not defined in your environment" % variable_type)

    def prepare_download_plan(self, applied_options):
        '''Prepares download plan. It gets applied options to select optional urls.'''
        for url in self.urls:
            local_file = os.path.join(self.config.src_cache, \
                    os.path.basename(url))
            if not isinstance(url, tuple):
                self.extract_plan.append(url)
                if os.path.isfile(local_file):
                    continue
                self.download_plan.append(url)
            else:
                option, url = url
                if option in applied_options:
                    self.extract_plan.append(url)
                    if os.path.isfile(local_file):
                        continue
                    self.download_plan.append(url)
        # Set extract plan to lpms' internal build environment
        setattr(self.internals.env, "extract_plan", self.extract_plan)

    def parse_src_url_field(self):
        '''Parses src_url field and create a url list for downloading'''
        def parse(data, option=False):
            shortcuts = (
                    '$url_prefix', '$src_url', '$slot', '$my_slot', \
                    '$name', '$version', '$fullname', '$my_fullname', \
                    '$my_name', '$my_version'
            )
            for shortcut in shortcuts:
                try:
                    interphase = re.search(r'-r[0-9][0-9]', self.internals.env.__dict__[shortcut[1:]])
                    if not interphase:
                        interphase = re.search(r'-r[0-9]', self.internals.env.__dict__[shortcut[1:]])
                        if not interphase:
                            data = data.replace(shortcut, self.internals.env.__dict__[shortcut[1:]])
                        else:
                            if shortcut == "$version":
                                self.revisioned = True
                                self.revision = interphase.group()
                            result = "".join(self.internals.env.__dict__[shortcut[1:]].split(interphase.group()))
                            if not shortcut in ("$name", "$my_slot", "$slot"):
                                setattr(self.internals.env, "raw_"+shortcut[1:], result)
                            data = data.replace(shortcut, result)
                    else:
                        if shortcut == "$version":
                            self.revisioned = True
                            self.revision = interphase.group()
                        result = "".join(self.internals.env.__dict__[shortcut[1:]].split(interphase.group()))
                        if not shortcut in ("$name", "$my_slot", "$slot"):
                            setattr(self.internals.env, "raw_"+shortcut[1:], result)
                        data = data.replace(shortcut, result)
                except KeyError:
                    continue
            if option:
                self.urls.append((option, data))
            else:
                self.urls.append(data)

        for url in self.internals.env.src_url.split(" "):
            result = url.split("(")
            if len(result) == 1:
                parse(url)
            elif len(result) == 2:
                myoption, url = result
                url = url.replace(")", "")
                parse(url, opt=myoption)

    def mangle_spec(self):
        # TODO: Use more convenient exceptions for error states.
        '''Compiles the spec file and imports its content to lpms' build environment.'''
        if not os.path.isfile(self.spec_file):
            out.error("%s could not be found!" % self.spec_file)
            raise BuildError
        elif not os.access(self.spec_file, os.R_OK):
            out.error("%s is not readable!" % self.spec_file)
            raise BuildError
        # TODO: Use a more proper name for import_script
        if not self.internals.import_script(self.spec_file):
            out.error("an error occured while processing the spec: %s" \
                    % out.color(self.spec_file, "red"))
            # TODO: Here, show package maintainer and bugs_to 
            out.error("please report the above error messages to the package maintainer.")
            raise BuildError

    def clean_temporary_directory(self):
        '''Cleans temporary directory which contains source code and building environment.'''
        def clean(target):
            for item in shelltools.listdir(target):
                path = os.path.join(target, item)
                if os.path.isdir(path):
                    shelltools.remove_dir(path)
                else:
                    shelltools.remove_file(path)
        # dont remove these directories which are located in work_dir
        exceptions = ('install', 'source')
        if shelltools.listdir(self.internals.env.build_dir):
            clean(self.internals.env.build_dir)
        if shelltools.listdir(self.internals.env.install_dir):
            clean(self.internals.env.install_dir)
        # Now, clean workdir
        for item in shelltools.listdir(self.internals.env.work_dir):
            if not item in exceptions:
                path = os.path.join(self.internals.env.work_dir, item)
                if os.path.isdir(path):
                    shelltools.remove_dir(path)
                else:
                    shelltools.remove_file(path)

    def set_environment_variables(self, package):
        '''Sets environment variables that used interpreter and other parts of lpms'''
        # TODO: This part seems dirty
        if package.id in self.data_bundle.inline_option_targets:
            self.internals.env.inline_option_targets = self.data_bundle.inline_option_targets[package.id]
        if package.id in self.data_bundle.conditional_versions:
            self.internals.env.conditional_versions = self.data_bundle.conditional_versions[package.id]

        self.internals.env.package = package
        self.internals.env.dependencies = self.data_bundle.dependencies.get(package.id, None)
        installed_package = self.instdb.find_package(package_name=package.name, \
                package_category=package.category, package_slot=package.slot)
        self.internals.env.previous_version = installed_package.get(0).version \
                if installed_package else None

        # Handle package conflicts and remove that conflicts if required
        if package.id in self.data_bundle.conflicts:
            conflict_instruct = self.instructions
            conflict_instruct.count = len(conflicts[package.id])
            for index, conflict in enumerate(conflicts[package.id], 1):
                conflict_instruct['index'] = index
                conflict_category, conflict_name, conflict_slot = conflict.split("/")
                conflict_package = self.instdb.find_package(package_name=conflict_name, \
                        package_category=conflict_category, \
                        package_slot=conflict_slot).get(0)
                if not initpreter.InitializeInterpreter(conflict_package, conflict_instruct,
                        ['remove'], remove=True).initialize():
                    out.error("an error occured during remove operation: %s/%s/%s-%s" % \
                            (conflict_package.repo, conflict_package.category, \
                            conflict_package.name, conflict_package.version))

        # FIXME: This is no good, perhaps, we should only import some variables to internal environment
        self.internals.env.__dict__.update(self.instructions.get_raw_dict)

        # Absolute path of the spec file.
        self.spec_file = os.path.join(
                cst.repos,
                package.repo,
                package.category,
                package.name,
                package.name+"-"+package.version+cst.spec_suffix
        )

        # Set metadata fields from the spec file.
        metadata_fields = ('repo', 'name', 'category', 'name', 'version', 'slot', 'options')
        for field in metadata_fields:
            setattr(self.internals.env, field, getattr(package, field))

        # Fullname of the package thats consists of its name and version
        self.internals.env.fullname = self.internals.env.name+"-"+self.internals.env.version

        # applied options is a set that contains options which will be applied to the package
        setattr(self.internals.env, "applied_options", self.data_bundle.options.get(package.id, None))

        # set local environment variables
        #if not lpms.getopt("--unset-env-variables"):
        #   self.set_local_environment_variables()

        interphase = re.search(r'-r[0-9][0-9]', self.internals.env.version)
        if not interphase:
            interphase = re.search(r'-r[0-9]', self.internals.env.version)
        # Before setting raw_version and revision, set their initial values
        self.internals.env.revision = ""
        self.internals.env.raw_version = self.internals.env.version

        # Now, set real values of these variables if package revisioned. 
        if interphase is not None and interphase.group():
            self.internals.env.raw_version = self.internals.env.version.replace(interphase.group(), "")
            self.internals.env.revision = interphase.group()

        # Import the spec
        self.mangle_spec()
        metadata = utils.metadata_parser(self.internals.env.metadata)
        if metadata.has_key("src_url"):
            self.internals.env.src_url = metadata["src_url"]
        else:
            if not hasattr(self.internals.env, "src_url"):
                self.internals.env.src_url = None

        if self.internals.env.srcdir is None:
            # Cut revision number from srcdir prevent unpacking fails
            srcdir = self.internals.env.name+"-"\
                    +self.internals.env.version.replace(self.internals.env.revision, "")
            self.internals.env.srcdir = srcdir

        filesdir = os.path.join(
                cst.repos,
                self.internals.env.repo,
                self.internals.env.category,
                self.internals.env.name,
                cst.files_dir
        )
        setattr(self.internals.env, "filesdir", filesdir)

        # TODO: What is src_cache?
        setattr(self.internals.env, "src_cache", cst.src_cache)

        # Set sandbox variable to switch sandbox
        if not self.config.sandbox and self.instructions.enable_sandbox:
            self.internals.env.sandbox = True
        elif self.config.sandbox and self.instructions.disable_sandbox:
            self.internals.env.sandbox = False
        else:
            self.internals.env.sandbox = self.config.sandbox

        # Set work_dir, build_dir and install_dir variables to lpms' internal build environment.
        self.internals.env.work_dir = os.path.join(
                self.config.build_dir,
                self.internals.env.category,
                self.internals.env.fullname
        )
        self.internals.env.build_dir = os.path.join(
                self.config.build_dir,
                self.internals.env.category,
                self.internals.env.fullname,
                "source",
                self.internals.env.srcdir)
        self.internals.env.install_dir = os.path.join(
                self.config.build_dir,
                self.internals.env.category,
                self.internals.env.fullname,
                "install")

        # Create these directories
        for target in ('build_dir', 'install_dir'):
            if not os.path.isdir(getattr(self.internals.env, target)):
                os.makedirs(getattr(self.internals.env, target))
        if not self.instructions.resume_build and len(os.listdir(self.internals.env.install_dir)):
            shelltools.remove_dir(self.internals.env.install_dir)

    def perform_operation(self):
        '''Handles command line arguments and drive building operation'''
        if self.instructions.pretend:
            out.write("\n")
            out.normal("these packages will be merged, respectively:\n")
            self.pretty_print(packages, conflicts, options)
            out.write("\ntotal %s package(s) listed.\n\n" \
                    % out.color(str(len(packages)), "green"))
            lpms.terminate()

        if self.instructions.ask:
            out.write("\n")
            out.normal("these packages will be merged, respectively:\n")
            self.pretty_print(self.data_bundle.packages, self.data_bundle.conflicts, self.data_bundle.options)
            utils.xterm_title("lpms: confirmation request")
            out.write("\ntotal %s package(s) will be merged.\n\n" \
                    % out.color(str(len(self.data_bundle.packages)), "green"))

            if not utils.check_root(msg=False):
                # Reset terminal title and terminate lpms.
                utils.xterm_title_reset()
                lpms.terminate("you must be root to perform this operation.")

            if not utils.confirm("Would you like to continue?"):
                # Reset terminal title and terminate lpms.
                utils.xterm_title_reset()
                lpms.terminate()

        setattr(self.internals.env, "count", len(self.data_bundle.packages))
        for index, package in enumerate(self.data_bundle.packages, 1):
            setattr(self.internals.env, "index", index)
            self.set_environment_variables(package)
            # Check /proc and /dev. These filesystems must be mounted 
            # to perform operations properly.
            for item in ('/proc', '/dev'):
                if not os.path.ismount(item):
                    out.warn("%s is not mounted. You have been warned." % item)

            # clean source code extraction directory if it is wanted
            # TODO: check the following condition when resume functionality is back
            if self.instructions.clean_tmp:
                if self.instructions.resume_build is not None:
                    out.warn("clean-tmp is disabled because of resume-build is enabled.")
                else:
                    self.clean_temporary_directory()

            # we want to save starting time of the build operation to calculate building time
            # The starting point of logging
            lpms.logger.info("starting build (%s/%s) %s/%s/%s-%s" % (
                index,
                len(self.data_bundle.packages),
                self.internals.env.repo,
                self.internals.env.category,
                self.internals.env.name,
                self.internals.env.version
                )
            )
            out.normal("(%s/%s) building %s/%s from %s" % (
                index,
                len(self.data_bundle.packages),
                out.color(self.internals.env.category, "green"),
                out.color(self.internals.env.name+"-"+self.internals.env.version, "green"),
                self.internals.env.repo
                )
            )
            #out.notify("you are using %s userland and %s kernel" % (self.config.userland, self.config.kernel))

            if self.internals.env.sandbox:
                lpms.logger.info("sandbox enabled build")
                out.notify("sandbox is enabled")
            else:
                lpms.logger.warning("sandbox disabled build")
                out.warn_notify("sandbox is disabled")

            # fetch packages which are in download_plan list
            if self.internals.env.src_url is not None:
                # preprocess url shortcuts such as $name, $version and etc
                self.parse_src_url_field()
                # if the package is revisioned, override build_dir and install_dir. 
                # remove revision number from these variables.
                if self.revisioned:
                    for variable in ("build_dir", "install_dir"):
                        new_variable = "".join(os.path.basename(getattr(self.internals.env, \
                                variable)).split(self.revision))
                        setattr(self.internals.env, variable, \
                                os.path.join(os.path.dirname(getattr(self.internals.env, \
                                variable)), new_variable))

                utils.xterm_title("lpms: downloading %s/%s/%s-%s" % (
                    self.internals.env.repo,
                    self.internals.env.category,
                    self.internals.env.name,
                    self.internals.env.version
                    )
                )

                self.prepare_download_plan(self.internals.env.applied_options)

                if not fetcher.URLFetcher().run(self.download_plan):
                    lpms.terminate("\nplease check the spec")

            if self.internals.env.applied_options is not None and self.internals.env.applied_options:
                out.notify("applied options: %s" %
                        " ".join(self.internals.env.applied_options))

            if self.internals.env.src_url is None and not self.extract_plan \
                    and hasattr(self.internals.env, "extract"):
                # Workaround for #208
                self.internals.env.extract_nevertheless = True

            # Remove previous sandbox log if it is exist.
            if os.path.exists(cst.sandbox_log):
                shelltools.remove_file(cst.sandbox_log)

            # Enter the building directory
            os.chdir(self.internals.env.build_dir)

            # Manage ccache
            if hasattr(self.config, "ccache") and self.config.ccache:
                if utils.drive_ccache(config=self.config):
                    out.notify("ccache is enabled.")
                else:
                    out.warn("ccache could not be enabled. so you should check dev-util/ccache")

            self.internals.env.start_time = time.time()
            if not interpreter.run(self.spec_file, self.internals.env):
                lpms.terminate("thank you for flying with lpms.")

            lpms.logger.info("finished %s/%s/%s-%s" % (
                self.internals.env.repo,
                self.internals.env.category,
                self.internals.env.name,
                self.internals.env.version
                )
            )

            utils.xterm_title("lpms: %s/%s finished" % (
                self.internals.env.category,
                self.internals.env.name)
            )

            out.normal("cleaning build directory.")
            shelltools.remove_dir(os.path.dirname(self.internals.env.install_dir))
            catdir = os.path.dirname(os.path.dirname(self.internals.env.install_dir))
            if not os.listdir(catdir):
                shelltools.remove_dir(catdir)

            if index < len(self.data_bundle.packages):
                # Delete the old internal data container object
                del self.internals
                # And create it again for the new package
                self.internals = internals.InternalFuncs()
                # Clear some variables for the new package
                self.urls = []
                self.extract_plan = []
                self.download_plan = []
            utils.xterm_title_reset()

    def pretty_print(self, packages, conflicts, options):
        '''Shows operation summary to the user'''
        # TODO: This can be splitted as a module
        for package in packages:
            status_bar = [' ', '  ']
            other_version = ""
            installed_packages = self.instdb.find_package(
                    package_name=package.name, \
                    package_category=package.category)
            if not installed_packages:
                installed_package = None
                status_bar[0] = out.color("N", "brightgreen")
            else:
                if not [installed_package for installed_package in installed_packages \
                        if package.slot == installed_package.slot]:
                    status_bar[1] = out.color("NS", "brightgreen")
                else:
                    for installed_package in installed_packages:
                        if installed_package.slot == package.slot:
                            if package.version != installed_package.version:
                                compare = utils.vercmp(package.version, \
                                        installed_package.version)
                                if compare == -1:
                                    status_bar[0] = out.color("D", "brightred")
                                    other_version = "[%s]" % out.color(\
                                            installed_package.version, "brightred")
                                elif compare == 1:
                                    status_bar[0] = out.color("U", "brightgreen")
                                    other_version = "[%s]" % out.color(\
                                            installed_package.version, "green")
                            elif package.version == installed_package.version:
                                status_bar[0] = out.color("R", "brightyellow")

            class FormattedOptions(list):
                def __init__(self, data):
                    super(FormattedOptions, self).extend(data)

                def append(self, item, color=None):
                    self.remove(item)
                    if color is not None:
                        super(FormattedOptions, self).insert(0, out.color("*"+item, color))
                    else:
                        super(FormattedOptions, self).insert(0, item)

            formatted_options = []
            if package.options is not None:
                installed_package = None
                for item in installed_packages:
                    if item.slot == package.slot:
                        installed_package = item
                formatted_options = FormattedOptions(package.options)
                if package.id in options:
                    if not status_bar[0].strip() or not status_bar[1].strip():
                        for applied_option in options[package.id]:
                            if installed_package:
                                if installed_package.applied_options is not None and not \
                                        applied_option in installed_package.applied_options:
                                    formatted_options.append(applied_option, "brightgreen")
                                    continue
                                elif installed_package.applied_options is None:
                                    formatted_options.append(applied_option, "brightgreen")
                                    continue
                            formatted_options.append(applied_option, "red")
                        if installed_package and installed_package.applied_options is not None:
                            for applied_option in installed_package.applied_options:
                                if not applied_option in options[package.id]:
                                    formatted_options.append(applied_option, "brightyellow")
                else:
                    for option in package.options:
                        if installed_package and installed_package.applied_options is not None and \
                                option in installed_package.applied_options:
                            formatted_options.append(option, "brightyellow")
                        else:
                            formatted_options.append(option)
            else:
                if hasattr(installed_package, "applied_options") and installed_package.applied_options is not None:
                    formatted_options = [out.color("%"+applied_option, "brightyellow") \
                            for applied_option in installed_package.applied_options]

            out.write("  [%s] %s/%s/%s {%s:%s} {%s} %s%s\n" % (
                    " ".join(status_bar), \
                    package.repo, \
                    package.category, \
                    package.name, \
                    out.color(package.slot, "yellow"),\
                    out.color(package.version, "green"),\
                    package.arch, \
                    other_version, \
                    " ("+", ".join(formatted_options)+")" if formatted_options else ""
                    )
            )
            
            if package.id in conflicts:
                for conflict in conflicts[package.id]:
                    category, name, slot = conflict.split("/")
                    conflict = self.instdb.find_package(package_name=name, \
                            package_category=category, \
                            package_slot = slot).get(0)
                    out.write("\t %s %s/%s/%s-%s" % (out.color(">> conflict:", "green"), \
                    conflict.repo,\
                            conflict.category, \
                                conflict.name, \
                                conflict.version
                        ))

