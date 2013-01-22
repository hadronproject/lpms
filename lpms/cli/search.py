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
import re
import sys
import sqlite3
import cPickle as pickle

import lpms

from lpms import api
from lpms import out
from lpms.db import api as dbapi
from lpms import constants as cst

help_output = (('--only-installed', 'Shows installed packages for given keyword.'),
        ('--in-name', 'Searchs given keyword in package names.'),
        ('--in-summary', 'Searchs given keyword in package summaries.'),
        ('--interactive', 'Shows package index and allows installation via index numbers.'))

# TODO:
# * search command must use instruct variable properly

class Search(object):
    def __init__(self, keyword, instruct):
        self.instruct = instruct
        self.instruct["ask"] = True
        self.keyword = ""
        for key in keyword:
            if not key in ('--only-installed', '--in-name', '--in-summary', '--interactive'):
                self.keyword += key+" "
        self.keyword = self.keyword.strip()
        root = cst.root if instruct["real_root"] is None \
                else instruct['real_root']
        self.connection = sqlite3.connect(os.path.join(root, cst.db_path, \
                cst.repositorydb)+cst.db_prefix)
        self.cursor = self.connection.cursor()
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()

    def usage(self):
        out.normal("Search given keywords in database")
        out.green("General Usage:\n")
        out.write(" $ lpms -s <keyword>\n")
        out.write("\nOther options:\n")
        for item in help_output:
            if len(item) == 2:
                out.write("%-28s: %s\n" % (out.color(item[0],"green"), item[1]))
        lpms.terminate()

    def classificate_packages(self, packages):
        items = {}
        for package in packages:
            key = package[1], package[2]
            if key not in items:
                items[key] = [package]
            else:
                items[key].append(package)
        return items

    def search(self):
        if not list(self.keyword) and lpms.getopt("--only-installed"):
            total = 0
            for package in self.instdb.get_all_names():
                repo, category, name = package
                version_data = self.instdb.get_version(name, repo_name=repo, \
                        pkg_category=category)
                total += 1
                for slot in version_data:
                    out.notify("%s/%s/%s [slot:%s] -> %s" % (repo, category, name, \
                            slot, ", ".join(version_data[slot])))
            out.write("\npackage count: %d\n" % total)
            lpms.terminate()

        if lpms.getopt("--help") or len(self.keyword) == 0:
            self.usage()

        available = True
        results = []
        if not lpms.getopt("--in-summary") and not lpms.getopt("--in-name"):
            self.cursor.execute('''SELECT repo, category, name, version, summary, slot FROM \
                    package WHERE name LIKE (?) OR summary LIKE (?)''', ("%"+self.keyword+"%", "%"+self.keyword+"%"))
            results.extend(self.cursor.fetchall())
        elif lpms.getopt("--in-summary"):
            self.cursor.execute('''SELECT repo, category, name, version, summary, slot FROM \
                    package WHERE summary LIKE (?)''', ("%"+self.keyword+"%",))
            results.extend(self.cursor.fetchall())
        else:
            self.cursor.execute('''SELECT repo, category, name, version, summary, slot FROM \
                    package WHERE name LIKE (?)''', ("%"+self.keyword+"%",))
            results.extend(self.cursor.fetchall())

        if not results:
            # if no result, search given keyword in installed packages database
            connection = sqlite3.connect(cst.installdb_path)
            cursor = connection.cursor()
            cursor.execute('''SELECT repo, category, name, version, summary, slot FROM \
                    package WHERE name LIKE (?) OR summary LIKE (?)''', ("%"+self.keyword+"%", "%"+self.keyword+"%"))
            results.extend(cursor.fetchall())
            if results: 
                out.notify("these packages are installed but no longer available.")
                available = False

        packages = self.classificate_packages(results)

        for index, package in enumerate(packages, 1):
            category, name = package
            if lpms.getopt("--interactive"):
                out.write("["+str(index)+"] "+out.color(category, "green")+"/"+out.color(name, "green")+" - ")
            else:
                out.write(out.color(category, "green")+"/"+out.color(name, "green")+" - ")
            items = {}
            for item in packages[package]:
                if item[0] in items:
                    items[item[0]].append(item[3])
                else:
                    items[item[0]] = [item[3]]
            for item in items:
                out.write(out.color(item, "yellow")+"("+", ".join(items[item])+") ")
            out.write("\n")
            out.write("    "+packages[package][0][4]+"\n")

        # shows a dialogue, selects the packages and triggers api's build function
        if results and lpms.getopt("--interactive"):
            my_packages = []
            def ask():
                out.write("\ngive number(s):\n")
                out.write("in order to select more than one package, use space between numbers:\n")
                out.write("to exit, press Q or q.\n")
            while True:
                ask()
                answers = sys.stdin.readline().strip()
                if answers == "Q" or answers == "q":
                    lpms.terminate()
                else:
                    targets = set()
                    for answer in answers.split(" "):
                        if not answer.isdigit():
                            out.warn("%s is invalid. please give a number!" % out.color(answer, "red"))
                            continue
                        else:
                            targets.add(answer)
                try:
                    my_items = packages.keys()
                    for target in targets:
                        my_packages.append("/".join(my_items[int(target)-1]))
                    break
                except (IndexError, ValueError):
                    out.warn("invalid command.")
                    continue

            if my_packages: 
                api.pkgbuild(my_packages, self.instruct)
