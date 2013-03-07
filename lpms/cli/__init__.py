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

# Get standard libraries
import sys

# Get lpms toolkit
from lpms import api
from lpms import out
from lpms.sorter import topsort

# Object oriented command line interpreter

# Here, define some variables
APP_NAME = "lpms"
VERSION = "1.1_beta1"

class Instruction(object):
    def __getattr__(self, key):
        if key in self.__dict__:
            return self.__dict__[key]

    def get_raw_dict(self):
        return self.__dict__

class AvailableArgument(object):
    def __init__(self, **kwargs):
        for kwarg in kwargs:
            setattr(self, kwarg, kwargs[kwarg])

    def get_items(self):
        return self.__dict__


class Actions(object):
    def about(self):
        '''Shows application name and version and exits'''
        out.write("%s %s\n" % (APP_NAME, VERSION))
        # Do nothing after after showing version information
        sys.exit(0)

    def change_root(self):
        '''Parses change-root argument'''
        self.instruction.new_root = [option for option in \
                self.argument_values["change_root"].split(" ") if option.strip()]

    def parse_options(self):
        '''Parses opts argument'''
        self.instruction.command_line_options = [option for option in \
                self.argument_values["parse_options"].split(" ") if option.strip()]

class CommandLineParser(Actions):
    '''Handles user actions and drives lpms' api'''
    def __init__(self, arguments):
        self.router = []
        self.invalid = []
        self.instruction = Instruction()
        self.arguments = arguments
        self.build_arguments = [
                AvailableArgument(arg='--pretend', short='-p', \
                        env_key='pretend', description='Shows steps, instead of actually performing the operation.'),
                AvailableArgument(arg="--ask", short='-a', \
                        env_key='ask', description='Asks the user before starting the process.'),
                AvailableArgument(arg='--category-install', short="-C", \
                        env_key="category_install", description='Installs packages that\'s in given repo/category.'),
                AvailableArgument(arg='--use-new-opts', short='-N', env_key="use_new_opts", \
                        description='Applies new global options for installed packages.'),
                AvailableArgument(arg='--resume', env_key="resume",
                    description="Resumes previous installation operation."),
                AvailableArgument(arg='--ignore-deps', env_key="ignore_deps", \
                        description='Ignores dependencies.'),
                AvailableArgument(arg='--ignore-conflicts', env_key='ignore_conflicts', \
                        description='Ignore file conflicts if conflict protect is enabled.'),
                AvailableArgument(arg='--no-configure', env_key='no_configure', \
                        description='Does not run configuration functions.'),
                AvailableArgument(arg='--enable-sandbox', \
                        env_key='enable_sandbox', description='Enables sandbox mechanism.'),
                AvailableArgument(arg='--disable-sandbox', \
                        env_key='disable_sandbox', description='Disables sandbox mechanism.'),
                AvailableArgument(arg='--sandbox-log-level', action="sandbox_log_level", \
                        description='Configures sandbox logging verbosity.'),
                AvailableArgument(arg='--ignore-reserve-files', env_key='ignore_reserve_files', \
                        description='Uses fresh files instead of local configuration files'),
                AvailableArgument(arg='--change-root', action='change_root', \
                        description='Changes installation target'),
                AvailableArgument(arg='--resume-build', env_key='resume_build', \
                        description='Resumes the most recent build operation.'),
                AvailableArgument(arg='--force-file-collision', env_key='force_file_collision', \
                        description='Disables collision protect.'),
                AvailableArgument(arg='--not-strip', env_key='not_strip', \
                        description='No strip libraries and executable files.'),
                AvailableArgument(arg='--not-merge', env_key='not_merge', \
                        description='Not merge the package after building.'),
                AvailableArgument(arg='--unset-env-vars', env_key='unset_env_variables', \
                        description='Unsets environment variables that were defined in configuration files'),
                AvailableArgument(arg='--opts', action='parse_options', \
                        description='Gets options of the package from command line.'),

        ]
        self.other_arguments = [
                    AvailableArgument(arg="--help", short="-h", \
                            action="usage", description="Shows this message."),
                    AvailableArgument(arg="--version", short="-v", \
                            action="about", description="Shows version information."),
                    AvailableArgument(arg="--sync", short='-S', \
                            action='sync', description='Sync..s enabled remote repositories.'),
                    AvailableArgument(arg="--update", short='-u', \
                            action='update', description='Updates all of the repositories or particular one.'),
                    AvailableArgument(arg="--upgrade", short='-U', \
                            action='upgrade', description='Scans the system for upgradeable packages.'),
                    AvailableArgument(arg='--search', short='-s', action='search', \
                            description='Searches given keyword in databases.'),
                    AvailableArgument(arg='--remove', short='-r', action='remove', \
                            description='Removes given package from the system.'),
                    AvailableArgument(arg='--belong', short='-b', action='belong', \
                            description='Queries the package that owns given keyword.'),
                    AvailableArgument(arg='--content', short='-c', action='content', \
                            description='Lists files of the given package.'),
                    AvailableArgument(arg='--list-repos', action='list_repositories', \
                            description='Lists all of the repositories.'),
                    AvailableArgument(arg='--clean-tmp', env_key='clean_tmp', \
                            description='Cleans lpms\' working directory.'),
                    AvailableArgument(arg='--build-info', env_key='build_info', \
                            description='Shows package\'s build information.'),
                    AvailableArgument(arg='--clean-system', action='clean_system', \
                            description='Removes unneeded packages from the system.'),
                    AvailableArgument(arg='--force-upgrade', env_key='clean_system', \
                            description='Forces lpms for using latest versions of the packages.'),
                    AvailableArgument(arg='--configure-pending', env_key='configure_pending', \
                            description='Configures pending packages if they were not configured at installation time.'),
                    AvailableArgument(arg='--reload-repodb', env_key='reload_repodb', \
                            description='Reloads previous repository database from backup.'),
                    AvailableArgument(arg='--verbose', env_key='verbose', description='Prints more output if it is possible.'),
                    AvailableArgument(arg='--quiet', env_key='quiet', description='Hides output if it is possible.'),
                    AvailableArgument(arg='--debug', env_key='debug', description='Enables debug mode.'),
        ]
        self.available_arguments = []
        self.available_arguments.extend(self.other_arguments)
        self.available_arguments.extend(self.build_arguments)
        self.packages = []
        self.argument_values = {}
        self.invalid_arguments = []

        self.action_rules = {
                'sync': ('update', 'upgrade', 'usage', 'about'),
                'update': ('upgrade'),
                'upgrade': [],
                'change_root': None,
                'parse_options': None,
        }

    def usage(self):
        '''Prints available commands with their descriptions.'''
        out.normal("lpms -- %s Package Management System %s\n" % \
                (out.color("L", "red"), out.color("v"+VERSION, "green")))
        out.write("In order to build a package:\n\n")
        out.write(" # lpms <package-name> <extra-command>\n\n")
        out.write("To see extra commands use --help parameter.\n\n")
        out.write("Build related arguments:\n")
        for build_argument in self.build_arguments:
            if hasattr(build_argument, "short"):
                out.write(('%-29s %-10s : %s\n' % (out.color(build_argument.arg, 'green'), \
                        out.color(build_argument.short, 'green'), build_argument.description)))
            else:
                out.write(('%-32s : %s\n' % (out.color(build_argument.arg, 'green'), build_argument.description)))

        out.write("\nOther arguments:\n")
        for other_argument in self.other_arguments:
            if hasattr(other_argument, "short"):
                out.write(('%-29s %-10s : %s\n' % (out.color(other_argument.arg, 'green'), \
                        out.color(other_argument.short, 'green'), other_argument.description)))
            else:
                out.write(('%-32s : %s\n' % (out.color(other_argument.arg, 'green'), \
                        other_argument.description)))

        # Do nothing after showing help message
        sys.exit(0)

    def handle_arguments(self):
        '''Parses arguments and sets some variables'''
        def append_argument():
            if hasattr(available_argument, "action"):
                if not available_argument.action in self.router:
                    self.router.append(available_argument.action)
            else:
                setattr(self.instruction, available_argument.env_key, True)
        self.invalid = []
        for argument in self.arguments:
            if not argument.startswith("-"):
                self.packages.append(argument)
                continue
            elif argument.startswith("--"):
                valid = False
                for available_argument in self.available_arguments:
                    if "=" in argument:
                        argument, value = argument.split("=")
                        self.argument_values[available_argument.action] = value
                    if argument == available_argument.arg:
                        append_argument()
                        valid = True
                        break
                if not valid:
                    self.invalid.append(argument)
            elif argument.startswith("-") and argument[1].isalpha():
                for item in argument[1:]:
                    valid = False
                    for available_argument in self.available_arguments:
                        if hasattr(available_argument, "short") and available_argument.short[1:] == item:
                            append_argument()
                            valid = True
                            break
                    if not valid:
                        self.invalid.append("-"+item)
        if self.invalid:
            out.warn("these commands seem invalid: %s" % ", ".join(self.invalid))

    def initialize(self):
        '''Runs methods to perform user requests considering the rules'''
        self.handle_arguments()
        action_plan = []
        instruction_modifier = []
        for action in self.router:
            if not action in self.action_rules:
                continue
            if self.action_rules[action] is None:
                if not action in instruction_modifier:
                    instruction_modifier.append(action)
                    continue
            for item in self.action_rules:
                if not item in self.router:
                    continue
                if self.action_rules[item]:
                    if action in self.action_rules[item]:
                        action_plan.append((action, item))

        # Run instruction modifiers to drive lpms properly
        if instruction_modifier:
            for action in instruction_modifier:
                getattr(self, action)()
        # Sort actions
        result = topsort(action_plan)
        result.reverse()

        # If an action hasn't added to result list 
        # while it's a real action, add it.
        for action in self.router:
            if not action in result and not action in instruction_modifier:
                result.append(action)

        # Run actions, respectively
        if result:
            for action in result:
                # TODO: We should use signals to determine behavior of lpms 
                # when the process has finished.
                getattr(self, action)()

        if self.packages:
            # Now, we can start building packages.
            api.package_build(self.packages, self.instruction)
        else:
            out.error("nothing given.")
            sys.exit(0)
