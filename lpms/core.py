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

# TODO: logging
import lpms

from lpms import out
from lpms import api
from lpms.db import api as dbapi
from lpms import conf
from lpms import utils
from lpms import shelltools
from lpms.utils import showplan
from lpms.operations import merge
from lpms import interpreter
from lpms import file_collisions
from lpms.cli import CommandLineParser
from lpms.exceptions import PackageNotFound, LpmsTerminate

class Operations(object):
    '''Drives lpms'''
    def check_root(method):
        def wrapper(*args, **kwargs):
            if os.getuid() != 0 and args[0].request.instruction.pretend is None:
                out.wrire(">> you must be root to perform this operation.")
                sys.exit(0)
            return method(*args, **kwargs)
        return wrapper

    @check_root
    def remove(self):
        try:
            api.remove_package(self.request.names, self.request.instruction)
        except PackageNotFound as err:
            out.write(">> %s could not be found.\n" % out.color(err.message, "red"))
            sys.exit(0)

    @check_root
    def update(self):
        api.update_repository(self.request.names)

    @check_root
    def upgrade(self):
        packages = api.upgrade_packages()
        if not packages:
            out.write(">> no package found to upgrade.\n")
            sys.exit(0)
        self.package_mangler(names=packages)

    @check_root
    def sync(self):
        api.syncronization(self.request.names)

    @check_root
    def package_mangler(self, **kwargs):
        def collision_check():
            # TODO: This is a temporary solution. collision_check function 
            # must be a reusable part for using in remove operation
            out.normal("checking file collisions...")
            lpms.logger.info("checking file collisions")
            collision_object = file_collisions.CollisionProtect(
                    environment.category,
                    environment.name,
                    environment.slot,
                    real_root=environment.real_root,
                    source_dir=environment.install_dir
            )
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
            if collision_object.collisions and self.config.collision_protect:
                if environment.force_file_collision:
                    out.warn("Disregarding these collisions, you have been warned!")
                else:
                    return False
            return True

        names = kwargs.get("names", self.request.names)
        # Prepare build environment
        out.normal("resolving dependencies")
        targets = api.resolve_dependencies(names, self.request.instruction)
        if self.request.instruction.pretend:
            out.write("\n")
            out.normal("these packages will be merged, respectively:\n")
            showplan.show(targets.packages, targets.conflicts, targets.options, installdb=dbapi.InstallDB())
            out.write("\ntotal %s package(s) listed.\n\n" \
                    % out.color(str(len(targets.packages)), "green"))
            raise LpmsTerminate

        if self.request.instruction.ask:
            out.write("\n")
            out.normal("these packages will be merged, respectively:\n")
            showplan.show(targets.packages, targets.conflicts, targets.options, installdb=dbapi.InstallDB())
            utils.xterm_title("lpms: confirmation request")
            out.write("\ntotal %s package(s) will be merged.\n\n" \
                    % out.color(str(len(targets.packages)), "green"))

            if not utils.confirm("Would you like to continue?"):
                # Reset terminal title and terminate lpms.
                utils.xterm_title_reset()
                raise LpmsTerminate

        self.request.instruction.count = len(targets.packages)
        for index, package in enumerate(targets.packages, 1):
            self.request.instruction.index = index
            retval, environment = api.prepare_environment(
                    package,
                    self.request.instruction,
                    dependencies=targets.dependencies[package.id] if package.id in \
                            targets.dependencies[package.id] else None,
                    options=targets.options[package.id] if package.id in \
                            targets.options else None,
                    conditional_versions=targets.conditional_versions[package.id] \
                            if package.id in targets.conditional_versions else None,
                    conflicts=targets.conflicts[package.id] if package.id \
                            in targets.conflicts else None,
                    inline_option_targets=targets.inline_option_targets[package.id] \
                            if package.id in targets.inline_option_targets else None
            )
            if not retval:
                out.error("There are some errors while preparing environment to build FOO.")
                out.error("So you should submit a bug report to fix the issue.")
                raise LpmsTerminate("thanks to flying with lpms.")
            # Now, run package script(spec) for configuring, building and install
            retval, environment = self.interpreter.initialize(environment)
            if not retval:
                out.error("There are some errors while building FOO from source.")
                out.error("Error messages should be seen above.")
                out.error("If you want to submit a bug report, please attatch BAR or send above messages in a proper way.")
                raise LpmsTerminate("thanks to flying with lpms.")
            if not collision_check():
                out.error("File collisions detected. If you want to overwrite these files,")
                out.error("You have to use --force-file-collisions parameter or disable collision_protect in configuration file.")
                raise LpmsTerminate("thanks to flying with lpms.")
            
            # Merge package to livefs
            if environment.not_merge:
                raise LpmsTerminate("not merging...")
            retval, environment = merge.Merge(environment).perform_operation()
            if not retval:
                raise LpmsTerminate("Some errors occured while merging %s" % environment.fullname)
            
            lpms.logger.info("finished %s/%s/%s-%s" % (
                package.repo,
                package.category,
                package.name,
                package.version)
            )

            utils.xterm_title("lpms: %s/%s finished" % (
                package.category,
                package.name)
            )

            out.normal("Cleaning build directory...")
            shelltools.remove_dir(os.path.dirname(environment.install_dir))
            catdir = os.path.dirname(os.path.dirname(environment.install_dir))
            if not os.listdir(catdir):
                shelltools.remove_dir(catdir)

            # There is no error
            out.normal("Completed.")

class LPMSCore(Operations):
    def __init__(self):
        # Get CommandLineParser and initialize it 
        self.request = CommandLineParser()
        self.request.start()
        self.config = conf.LPMSConfig()
        # Get lpms' ScriptEngine class for running stages
        self.interpreter = interpreter.ScriptEngine()

    def initialize(self):
        # Run command line client to drive lpms
        # Run actions, respectively
        if self.request.operations:
            for operation in self.request.operations:
                # TODO: We should use signals to determine behavior of lpms 
                # when the process has finished.
                getattr(self, operation)()
            return

        if self.request.names:
            # Now, we can start building packages.
            self.package_mangler()
        else:
            out.error("nothing given.")
            sys.exit(0)

def initialize():
    LPMSCore().initialize()
