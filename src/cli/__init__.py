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

from lpms.operations import build
from lpms.operations import remove
from lpms.operations import update
from lpms import utils
from lpms import conf
from lpms import out
from lpms import api

lpms_version = "0.9_alpha1"

help_output = (
        ('--help', '-h', 'Shows this message.'),
        ('--version', '-v', 'Shows version.'),
        ('--no-color', '-n', 'Disables color output.'),
        ('--remove', '-r', 'Removes given package.'),
        ('--update', '-u', 'Updates all repositories or given repository.'),
        ('--search', '-s', 'Searches given package in database.'),
        ('--belong', '-b', 'Queries the package that owns given keyword.'),
        ('--list-files', '-lf', 'Lists files of given package.')
        )

build_help = (
        ('--pretend', '-p', 'Shows operation steps'),
        ('--ask', '-a', 'Asks to the user before operation.'),
        ('--fetch-only', '-F', 'Only fetches packages, do not install.(not yet)'),
        ('--search', '-s', 'Searches given keyword in database.'),
        ('--resume', "Resumes previous installation operation. Use '--skip-first' to skip the first package."),
        ('--add-repo', 'Adds new repository(not yet).'),
        ('--ignore-deps', 'Ignores dependencies'),
        ('--ignore-sandbox', 'Disables sandbox facility.'),
        ('--enable-sandbox', 'Enables sandbox facilitiy.'),
        ('--no-configure', 'Does not run configuration functions.'),
        ('--resume-build', 'Resumes the most recent build operation.'),
        ('--change-root', 'Changes installation target.'),
        ('--no-merge', 'Does not merge the package'),
        ('--show-opts', 'Shows available options for given packages'),
        ('--opts', 'Determines options of the package.'))

def version():
    out.write("lpms %s\n" % lpms_version)
    lpms.terminate()

def help():
    out.normal("lpms -- %s Package Management System on %s" % (out.color("L", "red"), conf.LPMSConfig().distribution))
    out.write("\nIn order to build a package:\n")
    out.write(" # lpms <package-name> <extra-command>\n\n")
    out.write("Build related commands:\n")
    for cmd in build_help:
        if len(cmd) == 3:
            out.write("%-27s %-10s : %s\n" % (out.color(cmd[0], "green"), out.color(cmd[1], "green"), cmd[2]))
        else:
            out.write("%-30s : %s\n" % (out.color(cmd[0], "green"), cmd[1]))

    out.write("\nOther Commands:\n")
    for cmd in help_output:
        out.write("%-27s %-10s : %s\n" % (out.color(cmd[0], "green"), out.color(cmd[1], "green"), cmd[2]))
    lpms.terminate()

def main():
    command_line = sys.argv
    options = command_line[1:]
    pkgnames = []; ecoms = ('--resume-build')
    instruct = {"cmd_options": [], "sandbox": None, "show_opts": None, "ask": False, "resume": False,
            "skip_first": False, "pretend": False, "stage": None, "force": None, "real_root": None, 
            "ignore-deps": False}

    for opt in options:
        if opt in ecoms:
            continue
        elif opt == "-h" or opt == "--help":
            help()
        elif opt == "-v" or opt == "--version":
            version()
        elif opt == "--update" or  opt == "-u":
            utils.check_root()
            try:
                update.main(options[options.index(opt)+1:])
            except IndexError:
                update.main()
            return
        elif opt == "--remove" or opt == "-r":
            continue
        elif opt == "--force" or opt == "-f":
            instruct["force"] = True
        elif opt == "--show-opts":
            instruct["show_opts"] = True
        elif opt.startswith("--opts"):
            instruct["cmd_options"] = opt.split("=")[1].strip().split(" ")
        elif opt == "--ignore-deps":
            instruct["ignore-deps"] = True
        elif opt.startswith("--stage"):
            instruct["stage"] = opt.split("=")[1]
        elif opt == "--disable-sandbox":
            instruct["sandbox"] = False
        elif opt == "--enable-sandbox":
            instruct["sandbox"] = True
        elif opt == "--pretend" or opt == "-p":
            instruct["pretend"] = True
        elif opt == "--ask" or opt == "-a":
            instruct["ask"] = True
        elif opt == "--search" or opt == "-s":
            from lpms.cli import search
            search.Search(options[options.index(opt)+1:]).search()
            return
        elif opt == "--list-files" or opt == "-lf":
            from lpms.cli import list_files
            try: list_files.main(options[options.index(opt)+1])
            except IndexError:
                out.error("please give a package name.")
                lpms.terminate()
            return
        elif opt == "--belong" or opt == "-b":
            from lpms.cli import belong
            belong.main(options[options.index(opt)+1])
            return
        elif opt == "--remove_repo" or opt == "-rr":
            from lpms.cli import remove_repo
            try: remove_repo.main(options[options.index(opt)+1:])
            except IndexError:
                out.error("please give a repo name.")
                lpms.terminate()
            return
        elif opt == "--no-merge":
            pass
        elif opt.startswith("--change-root"):
            instruct["real_root"] = opt.split("=")[1].strip()
        elif opt == "--info" or opt == "-i":
            from lpms.cli import info
            info.Info(options[options.index(opt)+1:]).run()
            return
        elif opt == "--skip-first":
            instruct["skip_first"] = True
        else:
            pkgnames.append(opt)

    if "--upgrade" in options or "-U" in options:
        api.upgrade_system(instruct)
        return

    # abort lpms if the user do not give package name
    if not "--resume" in options and not pkgnames:
        lpms.catch_error("please give a package name!")

    if "--remove" in options or "-r" in options:
        remove.main(pkgnames, instruct)
        return
    
    if "--resume" in options:
        instruct["resume"] = True
        pkgnames = []
    # build given packages
    utils.check_root()
    api.pkgbuild(pkgnames, instruct)
