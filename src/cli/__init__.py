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

import sys

import lpms

from lpms import api
from lpms import out
from lpms import conf
from lpms import utils

from lpms.operations import remove
from lpms.operations import update

# TODO:
# Command line interface is bad
# it will be rewritten in the next milestone

commands = sys.argv[1:]

lpms_version = '1.1_alpha2'

help_output = (
        ('--help', '-h', 'Shows this message.'),
        ('--version', '-v', 'Shows version.'),
        ('--no-color', '-n', 'Disables color output.'),
        ('--remove', '-r', 'Removes given package.'),
        ('--update', '-u', 'Updates all repositories or given repository.'),
        ('--search', '-s', 'Searches given package in database.'),
        ('--belong', '-b', 'Queries the package that owns given keyword.'),
        ('--content', '-c', 'Lists files of given package.'),
        ('--list-repos', 'Lists all repositories.'),
        ('--clean-tmp', 'Cleans source code extraction directory.'),
        ('--autoremove', 'Removes unneeded packages.'),
        ('--force-upgrade', 'Forces lpms to use latest versions.'),
        ('--show-reverse-depends', 'Shows reverse dependencies of given package. It is a sub command of remove.'),
        ('--configure-pending', 'Configures pending packages if they were not configured at installation time.'),
        ('--reload-previous-repodb', 'Reloads previous repository database backup.'),
        ('--verbose', 'Prints more output if possible.'),
        ('--quiet', 'Hides outputs if possible.'),
        ('--debug', 'Enables debug mode.')
)

build_help_output = (
        ('--pretend', '-p', 'Shows operation steps.'),
        ('--ask', '-a', 'Asks to the user before operation.'),
        ('--fetch-only', '-F', 'Only fetches packages, do not install.(not yet)'),
        ('--search', '-s', 'Searches given keyword in database.'),
        ('--category-install', '-C', 'Installs packages that\'s in given repo/category'),
        ('--use-new-opts', '-N', 'Applies new global options for installed packages.'),
        ('--resume', "Resumes previous installation operation. Use '--skip-first' to skip the first package."),
        ('--add-repo', 'Adds new repository(not yet).'),
        ('--ignore-reinstall', 'Ignores installed packages.'),
        ('--ignore-depends', 'Ignores dependencies.'),
        ('--ignore-conflicts', 'Ignore file conflicts if conflict protect is enabled.'),
        ('--disable-sandbox', 'Disables sandbox facility if it is possible.'),
        ('--enable-sandbox', 'Enables sandbox facilitiy if it is possible.'),
        ('--sandbox-log-level', 'Sandbox logging verbosity'),
        ('--ignore-reserve-files', 'Ignores local files.'),
        ('--no-configure', 'Does not run configuration functions.'),
        ('--resume-build', 'Resumes the most recent build operation.'),
        ('--change-root', 'Changes installation target.'),
        ('--force-file-collision', 'Disables collision protect.'),
        ('--no-strip', 'No strip files.'),
        ('--no-merge', 'Does not merge the package.'),
        ('--unset-env-variables', 'Unsets environment variables that are defined in lpms.conf.'),
        ('--opts', 'Determines options of the package.')
)

def version():
    out.write(('lpms %s\n' % lpms_version))
    lpms.terminate()

def usage():
    out.normal('lpms -- %s Package Management System %s' % (out.color('L', 'red'), \
            out.color("v"+lpms_version, "brightgreen")))
    out.write('\nIn order to build a package:\n')
    out.write(' # lpms <package-name> <extra-command>\n\n')
    out.write('To see extra commands use --help parameter.\n\n')
    out.write('Build related commands:\n')

    for item in build_help_output:
        if len(item) == 3:
            long_command, short_command, description = item
            if lpms.getopt("--no-color") or lpms.getopt("-n"):
                out.write(('%-24s %-10s : %s\n' % (out.color(long_command, 'green'),
                out.color(short_command, 'green'),
                description)))
            else:
                out.write(('%-32s %-10s : %s\n' % (out.color(long_command, 'green'),
                out.color(short_command, 'green'),
                description)))
        else:
            long_command, description = item
            out.write(('%-35s : %s\n' % (out.color(long_command, 'green'), description)))

    out.write('\nOther Commands:\n')
    for item in help_output:
        if len(item) == 3:
            long_command, short_command, description = item
            if lpms.getopt("--no-color") or lpms.getopt("-n"):
                out.write(('%-24s %-10s : %s\n' % (out.color(long_command, 'green'),
                out.color(short_command, 'green'),
                description)))
            else:
                out.write(('%-32s %-10s : %s\n' % (out.color(long_command, 'green'),
                out.color(short_command, 'green'),
                description)))
        else:
            long_command, description = item
            out.write(('%-35s : %s\n' % (out.color(long_command, 'green'), description)))
    lpms.terminate()


exceptional_commands = (
        '--ignore-depends', 
        '--quiet', 
        '--verbose', 
        '--force-upgrade', 
        '--reset',
        '--disable-sandbox', 
        '--force-unpack', 
        '--enable-sandbox', 
        '--ignore-conflicts', 
        '--no-configure', 
        '--ignore-reserve-files', 
        '--reload-previous-repodb',
        '--list-repos', 
        '--no-strip', 
        '--unset-env-variables', 
        '--use-file-relations', 
        '--in-name', 
        '--in-summary', 
        '--only-installed', 
        '--force-file-collision',
        '--clean-tmp', 
        '--ignore-reinstall'
)

exceptions = (
        'change-root', 
        'opts', 
        'stage'
)

to_instruct = (
        'ask', 'a', 
        'resume-build', 
        'resume', 
        'pretend', 'p', 
        'fetch-only', 'F',
        'no-merge', 
        'remove', 'r', 
        'upgrade', 'U',  
        'skip-first', 
        'sync', 'S', 
        'update', 'u',
        'configure-pending', 
        'category-install', 'C', 
        'use-new-opts', 'N', \
        'show-reverse-depends', 
        'debug'
)

regular = (
        'help', 'h', 
        'version', 'v', 
        'belong', 'b', 
        'content', 'c', 
        'remove', 'r',
        'no-color', 'n', 
        'update', 'u', 
        'search', 's', 
        'upgrade', 'U', 
        'show-deps'
)

instruct = {
        'ask': False, 
        'pretend': False, 
        'resume-build': False, 
        'resume': False,
        'pretend': False, 
        'no-merge': False, 
        'fetch-only': False, 
        'real_root': None,
        'cmd_options': [], 
        'specials': {}, 
        'ignore-deps': False, 
        'sandbox': None,
        'stage': None,
        'force': None, 
        'upgrade': None, 
        'remove': None, 
        'skip-first': False, 
        'sync': False,
        'update': False, 
        'configure-pending': False, 
        'category-install': False,
        "use-new-opts": False, 
        'like': set(), 
        'show-reverse-depends': False, 
        'debug': False
}

def main():
    packages = []; invalid = []
    for command in commands:
        if command.startswith('-') and not command.startswith('--'):
            for cli_element in command[1:]:
                if (cli_element == 'h'):
                    usage()
                elif (cli_element == 'v'):
                    version()
                elif (cli_element == 'b'):
                    from lpms.cli import belong
                    results = [command for command in commands if not \
                            command.startswith("-")]
                    belong.Belong(results[0]).main()
                    return
                elif (cli_element == 'i'):
                    from lpms.cli import info
                    results = [command for command in commands if not \
                            command.startswith("-")]
                    info.Info(results).run()
                    return
                elif (cli_element == 'c'):
                    from lpms.cli import list_files
                    results = [command for command in commands if not \
                            command.startswith("-")]
                    if not results:
                        out.error('please give a package name.')
                        lpms.terminate()
                    for name in results:
                        list_files.ListFiles(name).main()
                    return
                elif (cli_element == 's'):
                    from lpms.cli import search
                    results = [command for command in commands if not \
                            command.startswith("-")]
                    search.Search(results, instruct).search()
                    return
                else:
                    if cli_element not in regular and cli_element not in to_instruct:
                        invalid.append(('-' + cli_element))

        elif command.startswith('--'):
            cli_element = command[2:]
            if cli_element.startswith('sandbox-log-level'):
                continue
            if command in exceptional_commands:
                continue

            if cli_element == 'help':
                usage()
            elif cli_element == 'version':
                version()
            elif cli_element == 'list-repos':
                from lpms.cli import list_repos
                list_repos.main()
                return
            elif cli_element == 'info':
                from lpms.cli import info
                results = [command for command in commands if not \
                            command.startswith("-")]
                info.Info(results).run()
                return
            elif cli_element == 'belong':
                from lpms.cli import belong
                results = [command for command in commands if not \
                            command.startswith("-")]
                belong.Belong(results[0]).main()
                return
            elif cli_element == 'content':
                from lpms.cli import list_files
                commands.remove(command)
                results = [command for command in commands if not \
                            command.startswith("-")]
                if not results:
                    out.error('please give a package name.')
                    lpms.terminate()
                for name in results:
                    list_files.ListFiles(name).main()
                return
            elif cli_element == 'search':
                from lpms.cli import search
                results = [command for command in commands if not \
                            command.startswith("-")]
                search.Search(results).search()
                return
            elif cli_element == "autoremove":
                from lpms.cli import autoremove
                autoremove.Autoremove().select()
                return
            else:
                if cli_element not in regular and cli_element not in to_instruct and \
                        cli_element.split('=')[0] not in exceptions and \
                        not cli_element.startswith("opts"):
                    invalid.append(command)
        else:
            if "%" in cli_element:
                instruct['like'].add(command); continue
            packages.append(unicode(command))

    for command in commands:
        cli_element = command[2:]
        if command.startswith('-') and not command.startswith('--'):
            for cli_element in command[1:]:
                if cli_element in to_instruct:
                    instruct[to_instruct[(to_instruct.index(cli_element) - 1)]] = True

        else:
            if cli_element in to_instruct or cli_element.split('=')[0] in exceptions or \
                    cli_element.split("=")[0].split("-")[0] in exceptions:
                if cli_element.startswith('change-root'):
                    instruct['real_root'] = cli_element.split('=')[1]
                if cli_element.startswith('opts-'):
                    data = cli_element.split("opts-", 1)[1]
                    name, opts = data.split("=", 1)
                    instruct["specials"].update({name: opts.split(" ")})
                if cli_element.startswith('opts='):
                    instruct['cmd_options'] = cli_element.split('=')[1].split(' ')
                if cli_element.startswith('stage'):
                    instruct['stage'] = cli_element.split('=')[1].strip()
                instruct[cli_element] = True

    if invalid:
        out.warn("invalid: "+", ".join(invalid))

    if lpms.getopt("--reload-previous-repodb"):
        utils.reload_previous_repodb()
        lpms.terminate()

    if instruct['resume']:
        pkgnames = []

    if instruct['sync']:
        api.syncronize(packages, instruct)
        if instruct['update']:
            api.update_repository(packages)
            if instruct['upgrade']:
                api.upgrade_system(instruct)
        return

    if instruct['update']:
        api.update_repository(packages)
        if instruct['upgrade']:
            api.upgrade_system(instruct)
        return
 
    if instruct['upgrade']:
        api.upgrade_system(instruct)
        return
        
    if instruct['remove']:
        api.remove_package(packages, instruct)
        return

    if instruct['configure-pending']:
        api.configure_pending(packages, instruct)
        return

    for tag in ('upgrade', 'remove', 'sync', 'update'):
        del instruct[tag]

    if not packages and not instruct["resume"] and not instruct['like']:
        out.error('no given package name.')
        lpms.terminate()

    if instruct["resume"]:
        packages = []

    utils.check_root()

    set_remove = []

    for package in packages:
        if package.startswith("@"):
            set_packages = utils.set_parser(package[1:])
            if set_packages:
                packages.extend(set_packages)
            set_remove.append(package)

    if instruct["category-install"]:
        category_pkgs = [pkg for pkg in packages if \
                len(pkg.split("/")) == 2]

        for data in category_pkgs:
            repo, category = data.split("/")
            packages.extend(utils.list_disk_pkgs(repo, category))
            set_remove.append(data)

    if set_remove:
        for pkg in set_remove:
            packages.remove(pkg)

    # start building operation
    if packages or instruct['like']:
        api.pkgbuild(packages, instruct)

