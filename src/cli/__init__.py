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

cli = sys.argv[1:]

lpms_version = '0.9_alpha2'

help_output = (('--help', '-h', 'Shows this message.'),
        ('--version', '-v', 'Shows version.'),
        ('--no-color', '-n', 'Disables color output.'),
        ('--remove', '-r', 'Removes given package.'),
        ('--update', '-u', 'Updates all repositories or given repository.'),
        ('--search', '-s', 'Searches given package in database.'),
        ('--belong', '-b', 'Queries the package that owns given keyword.'),
        ('--content', '-c', 'Lists files of given package.'),
        ('--sync', '-S', 'Synchronizes package repositories.'),
        ('--force-upgrade', 'Forces lpms to use latest versions.'),
        ('--configure-pending', 'Configures pending packages if they were not configured at installation time.'),
        ('--verbose', 'Prints more output if possible.'),
        ('--quiet', 'Hides outputs if possible.'))

build_help = (('--pretend', '-p', 'Shows operation steps'),
        ('--ask', '-a', 'Asks to the user before operation.'),
        ('--fetch-only', '-F', 'Only fetches packages, do not install.(not yet)'),
        ('--search', '-s', 'Searches given keyword in database.'),
        ('--resume', "Resumes previous installation operation. Use '--skip-first' to skip the first package."),
        ('--add-repo', 'Adds new repository(not yet).'),
        ('--ignore-depends', 'Ignores dependencies.'),
        ('--ignore-conflicts', 'Ignore file conflicts if conflict protect is enabled.'),
        ('--ignore-sandbox', 'Disables sandbox facility.'),
        ('--enable-sandbox', 'Enables sandbox facilitiy.'),
        ('--no-configure', 'Does not run configuration functions.'),
        ('--resume-build', 'Resumes the most recent build operation.'),
        ('--change-root', 'Changes installation target.'),
        ('--no-merge', 'Does not merge the package.'),
        ('--ask-repo', 'Shows repo selection dialog if necessary.'),
        ('--show-opts', 'Shows available options for given packages.'),
        ('--opts', 'Determines options of the package.'))

def version():
    out.write(('lpms %s\n' % lpms_version))
    lpms.terminate()



def usage():
    out.normal(('lpms -- %s Package Management System on %s' % (out.color('L', 'red'), conf.LPMSConfig().distribution)))
    out.write('\nIn order to build a package:\n')
    out.write(' # lpms <package-name> <extra-command>\n\n')
    out.write('Build related commands:\n')

    for cmd in build_help:
        if len(cmd) == 3:
            if lpms.getopt("--no-color") or lpms.getopt("-n"):
                out.write(('%-19s %-10s : %s\n' % (out.color(cmd[0], 'green'),
                out.color(cmd[1], 'green'),
                cmd[2])))
            else:
                out.write(('%-27s %-10s : %s\n' % (out.color(cmd[0], 'green'),
                out.color(cmd[1], 'green'),
                cmd[2])))
        else:
            out.write(('%-30s : %s\n' % (out.color(cmd[0], 'green'), cmd[1])))

    out.write('\nOther Commands:\n')
    for cmd in help_output:
        if len(cmd) == 3:
            if lpms.getopt("--no-color") or lpms.getopt("-n"):
                out.write(('%-19s %-10s : %s\n' % (out.color(cmd[0], 'green'),
                out.color(cmd[1], 'green'),
                cmd[2])))
            else:
                out.write(('%-27s %-10s : %s\n' % (out.color(cmd[0], 'green'),
                out.color(cmd[1], 'green'),
                cmd[2])))
    lpms.terminate()


nevermind = ('--ignore-depends', '--quiet', '--verbose', '--force-upgrade', '--reset', \
        '--ignore-sandbox', '--enable-sandbox', '--ignore-conflicts', '--no-configure')

exceptions = ('change-root', 'opts', 'stage')

toinstruct = ('ask', 'a', 'resume-build', 'resume', 'pretend', 'p', 'fetch-only', 'F', \
        'no-merge', 'remove', 'r', 'upgrade', 'U',  'skip-first', 'sync', 'S', 'update', 'u', \
        'configure-pending')

regular = ('help', 'h', 'version', 'v', 'belong', 'b', 'content', 'c', 'remove', 'r', \
        'no-color', 'n', 'update', 'u', 'search', 's', 'upgrade', 'U', 'ask-repo', 'show-deps')

instruct = {'ask': False, 'pretend': False, 'resume-build': False, 'resume': False, \
        'pretend': False, 'no-merge': False, 'fetch-only': False, 'real_root': None, \
        'cmd_options': [], 'specials': {}, 'ignore-deps': False, 'sandbox': None,'stage': None, \
        'force': None, 'upgrade': None, 'remove': None, 'skip-first': False, 'sync': False, \
        'update': False, 'configure-pending': False}

def main():
    packages = []; invalid = []
    for l in cli:
        if (l.startswith('-') and (not l.startswith('--'))):
            for h in l[1:]:
                if (h == 'h'):
                    usage()
                elif (h == 'v'):
                    version()
                elif (h == 'b'):
                    from lpms.cli import belong
                    belong.main(cli[(cli.index(l) + 1):])
                    return
                elif (h == 'i'):
                    from lpms.cli import info
                    info.Info(cli[(cli.index(l) + 1):]).run()
                    return
                elif (h == 'c'):
                    from lpms.cli import list_files
                    try:
                        list_files.main(cli[(cli.index(l) + 1)])
                        return
                    except IndexError:
                        out.error('please give a package name.')
                        lpms.terminate()
                elif (h == 's'):
                    from lpms.cli import search
                    search.Search(cli[(cli.index(l) + 1):]).search()
                    return
                #elif (h == 'u'):
                #    utils.check_root()
                #    api.update_database()
                #    try:
                #        update.main(cli[(cli.index(l) + 1):])
                #    except IndexError:
                #        update.main()
                #    return
                else:
                    if ((h not in regular) and (h not in toinstruct)):
                        invalid.append(('-' + h))

        elif l.startswith('--'):
            if (l[2:] == 'help'):
                usage()
            elif (l[2:] == 'version'):
                version()
            #elif (l[2:] == 'update'):
            #    utils.check_root()
            #    try:
            #        update.main(cli[(cli.index(l) + 1):])
            #    except IndexError:
            #        update.main()
            #    return
            elif (l[2:] == 'info'):
                from lpms.cli import info
                info.Info(cli[(cli.index(l) + 1):]).run()
                return
            elif (l[2:] == 'belong'):
                from lpms.cli import belong
                belong.main(cli[(cli.index(l) + 1):])
                return
            elif (l[2:] == 'content'):
                from lpms.cli import list_files
                try:
                    list_files.main(cli[(cli.index(l) + 1)])
                    return
                except IndexError:
                    out.error('please give a package name.')
                    lpms.terminate()
            elif (l[2:] == 'search'):
                from lpms.cli import search
                search.Search(cli[(cli.index(l) + 1):]).search()
                return
            elif l in nevermind:
                pass
            else:
                if l[2:] not in regular and l[2:] not in toinstruct and \
                        l[2:].split('=')[0] not in exceptions and \
                        not l[2:].startswith("opts"):
                    invalid.append(l)
        else:
            packages.append(unicode(l))

    for c in cli:
        if c.startswith('-') and not c.startswith('--'):
            for x in c[1:]:
                if x in toinstruct:
                    instruct[toinstruct[(toinstruct.index(x) - 1)]] = True

        else:
            if c[2:] in toinstruct or c[2:].split('=')[0] in exceptions or \
                    c[2:].split("=")[0].split("-")[0] in exceptions:
                if c[2:].startswith('change-root'):
                    instruct['real_root'] = c[2:].split('=')[1]
                if c[2:].startswith('opts-'):
                    data = c[2:].split("opts-", 1)[1]
                    name, opts = data.split("=", 1)
                    instruct["specials"].update({name: opts.split(" ")})
                if c[2:].startswith('opts='):
                    instruct['cmd_options'] = c[2:].split('=')[1].split(' ')
                if c[2:].startswith('stage'):
                    instruct['stage'] = c[2:].split('=')[1].strip()
                instruct[c[2:]] = True

    if invalid:
        out.warn("invalid: "+", ".join(invalid))

    if instruct['resume']:
        pkgnames = []

    if instruct['sync']:
        api.syncronize(packages, instruct)
        return

    if instruct['update']:
        api.update_repository(packages)
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

    if not packages and not instruct["resume"]:
        out.error('no given package name.')
        lpms.terminate()

    if instruct["resume"]:
        packages = []

    utils.check_root()
    #lpms.logger.info(('=== command: %s ===' % ' '.join(sys.argv)))

    set_remove = []

    for package in packages:
        if package.startswith("@"):
            packages.extend(utils.set_parser(package[1:]))
            set_remove.append(package)

    if set_remove:
        for pkg in set_remove:
            packages.remove(pkg)

    # start building operation
    api.pkgbuild(packages, instruct)

