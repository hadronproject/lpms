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
    def __init__(self, package, instruction, **kwargs):
        # package and instruction are required.
        # Others can be None 
        self.package = package
        self.instruction = instruction
        self.dependencies=kwargs.get("dependencies", None)
        self.options=kwargs.get("options", None)
        self.conditional_versions=kwargs.get("conditional_versions", None)
        self.conflicts=kwargs.get("conflicts", None)
        self.inline_option_targets=kwargs.get("inline_option_targets", None)
        
        # Internal variables 
        self.repodb = api.RepositoryDB()
        self.instdb = api.InstallDB()
        self.download_plan = []
        self.extract_plan = []
        self.urls = []
        self.internals = internals.InternalFunctions()
        self.internals.env.raw.update(
                {
                    "get": self.internals.get,
                    "cmd_options": [],
                    "options": []
                }
        )
        self.config = conf.LPMSConfig()
        if self.instruction.unset_env_variables is not None:
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
            if not isinstance(url, tuple):
                local_file = os.path.join(self.config.src_cache, os.path.basename(url))
                self.extract_plan.append(url)
                if os.path.isfile(local_file):
                    continue
                self.download_plan.append(url)
            else:
                option, url = url
                local_file = os.path.join(self.config.src_cache, os.path.basename(url))
                if applied_options is None:
                    continue
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
                parse(url, option=myoption)

    def mangle_spec(self):
        # TODO: Use more convenient exceptions for error states.
        '''Compiles the spec file and imports its content to lpms' build environment.'''
        if not os.path.isfile(self.internals.env.spec_file):
            out.error("%s could not be found!" % self.internals.env.spec_file)
            raise BuildError
        elif not os.access(self.internals.env.spec_file, os.R_OK):
            out.error("%s is not readable!" % self.internals.env.spec_file)
            raise BuildError
        # TODO: Use a more proper name for import_script
        if not self.internals.import_script(self.internals.env.spec_file):
            out.error("an error occured while processing the spec: %s" \
                    % out.color(self.internals.env.spec_file, "red"))
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

    def set_environment_variables(self):
        '''Sets environment variables that used interpreter and other parts of lpms'''
        # TODO: This part seems dirty
        if self.inline_option_targets is not None and \
                self.package.id in self.inline_option_targets:
            self.internals.env.inline_option_targets = self.inline_option_targets[self.package.id]
        if self.conditional_versions is not None and \
                self.package.id in self.conditional_versions:
            self.internals.env.conditional_versions = self.conditional_versions[self.package.id]

        self.internals.env.package = self.package
        if self.dependencies is not None:
            self.internals.env.dependencies = self.dependencies.get(self.package.id, None)
        installed_package = self.instdb.find_package(package_name=self.package.name, \
                package_category=self.package.category, package_slot=self.package.slot)
        self.internals.env.previous_version = installed_package.get(0).version \
                if installed_package else None

        # Handle package conflicts and remove that conflicts if required
        # TODO: This mech. is obsolete
        if self.conflicts is not None and self.package.id in self.conflicts:
            conflict_instruct = self.instruction
            conflict_instruct.count = len(self.conflicts[self.package.id])
            for index, conflict in enumerate(self.conflicts[self.package.id], 1):
                conflict_instruct['index'] = index
                conflict_category, conflict_name, conflict_slot = self.conflict.split("/")
                conflict_package = self.instdb.find_package(package_name=conflict_name, \
                        package_category=conflict_category, \
                        package_slot=conflict_slot).get(0)
                if not initpreter.InitializeInterpreter(conflict_package, conflict_instruct,
                        ['remove'], remove=True).initialize():
                    out.error("an error occured during remove operation: %s/%s/%s-%s" % \
                            (conflict_package.repo, conflict_package.category, \
                            conflict_package.name, conflict_package.version))

        # FIXME: This is no good, perhaps, we should only import some variables to internal environment
        self.internals.env.raw.update(self.instruction.raw)

        # Absolute path of the spec file.
        self.internals.env.spec_file = os.path.join(
                cst.repos,
                self.package.repo,
                self.package.category,
                self.package.name,
                self.package.name+"-"+self.package.version+cst.spec_suffix
        )

        # Set metadata fields from the spec file.
        metadata_fields = ('repo', 'name', 'category', 'name', 'version', 'slot', 'options')
        for field in metadata_fields:
            setattr(self.internals.env, field, getattr(self.package, field))

        # Fullname of the package thats consists of its name and version
        self.internals.env.fullname = self.internals.env.name+"-"+self.internals.env.version

        # applied options is a set that contains options which will be applied to the package
        if self.options is not None and self.package.id in self.options:
            self.internals.env.applied_options = self.options[self.package.id]

        # set local environment variable
        if not self.instruction.unset_env_variables:
           self.set_local_environment_variables()

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
        if not self.config.sandbox and self.instruction.enable_sandbox:
            self.internals.env.sandbox = True
        elif self.config.sandbox and self.instruction.disable_sandbox:
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
        if not self.instruction.resume_build and len(os.listdir(self.internals.env.install_dir)):
            shelltools.remove_dir(self.internals.env.install_dir)

    def perform_operation(self):
        '''Handles command line arguments and drive building operation'''
        self.set_environment_variables()
        # Check /proc and /dev. These filesystems must be mounted 
        # to perform operations properly.
        for item in ('/proc', '/dev'):
            if not os.path.ismount(item):
                out.warn("%s is not mounted. You have been warned." % item)

        # clean source code extraction directory if it is wanted
        # TODO: check the following condition when resume functionality is back
        if self.instruction.clean_tmp:
            if self.instruction.resume_build is not None:
                out.warn("clean-tmp is disabled because of resume-build is enabled.")
            else:
                self.clean_temporary_directory()

        # we want to save starting time of the build operation to calculate building time
        # The starting point of logging
        lpms.logger.info("starting build (%s/%s) %s/%s/%s-%s" % (
            self.instruction.index,
            self.instruction.count,
            self.internals.env.repo,
            self.internals.env.category,
            self.internals.env.name,
            self.internals.env.version
            )
        )

        out.normal("(%s/%s) building %s/%s from %s" % (
            self.instruction.index,
            self.instruction.count,
            out.color(self.internals.env.category, "green"),
            out.color(self.internals.env.name+"-"+self.internals.env.version, "green"),
            self.internals.env.repo
            )
        )

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
        return True, self.internals.env
    """
        if index < len(self.packages):
            # Delete the old internal data container object
            del self.internals
            # And create it again for the new package
            self.internals = internals.InternalFunctions()
            # Clear some variables for the new package
            self.urls = []
            self.extract_plan = []
            self.download_plan = []
        utils.xterm_title_reset()
        """
