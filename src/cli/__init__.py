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
from lpms.operations import update
from lpms import utils
from lpms import conf
from lpms import out

lpms_version = "0.9_alpha1"

help_output = (
        ('--help', '-h', 'Shows this message.'),
        ('--version', '-v', 'Shows version.'),
        ('--update', '-u', 'Updates all repositories or given repository.'),
        ('--search', '-s', 'Searches given package in database.'),
        ('--no-color', '-n', 'Disables color output.')
        )

build_help = (
        ('--pretend', '-p', 'Shows operation steps'),
        ('--ask', '-a', 'Asks to the user before operation.(not yet)'),
        ('--fetch-only', '-F', 'Only fetches packages, do not install.(not yet)'),
        ('--search', '-s', 'Searches given keyword in database'),
        ('--add-repo', 'Adds new repository(not yet)'),
        ('--ignore-sandbox', 'Disables sandbox facility'),
        ('--enable-sandbox', 'Enables sandbox facilitiy'),
        ('--resume-build', 'Resumes the most recent build operation.'),
        ('--show-opts', 'Shows available options for given packages'),
        ('--opts', 'Determines the package\'s options.'))

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
    instruct = {"cmd_options": [], "sandbox": None, "show_opts": None, "ask": False,
            "pretend": False, "stage": None, "force": None}
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
                update.main(repo_name=options[options.index(opt)+1])
            except IndexError:
                update.main()
                return
        elif opt == "--force" or opt == "-f":
            instruct["force"] = True
        elif opt == "--show-opts":
            instruct["show_opts"] = True
        elif opt.startswith("--opts"):
            instruct["cmd_options"] = opt.split("=")[1].split(" ")
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
        elif opt == "--info" or opt == "-i":
            from lpms.cli import info
            info.Info(options[options.index(opt)+1:]).run()
            return 
        else:
            pkgnames.append(opt)

    # abort lpms if the user do not give package name
    if len(pkgnames) == 0:
        lpms.catch_error("please give a package name!")
    # build given packages
    utils.check_root()
    build.main(pkgnames, instruct)
