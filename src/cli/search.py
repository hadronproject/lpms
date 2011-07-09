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

import re

import lpms
from lpms import out
from lpms.db import dbapi

help_output = (('--mark', 'use markers to highlight the matching strings.'),)

class Search(object):
    def __init__(self, patterns):
        self.patterns = patterns
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()

    def usage(self):
        out.normal("Search given keywords in database")
        out.green("General Usage:\n")
        out.write(" $ lpms -s <keyword>\n")
        out.write("\nOther options:\n")
        for h in help_output:
            if len(h) == 2:
                out.write("%-15s: %s\n" % (out.color(h[0],"green"), h[1]))
        lpms.terminate()

    def search(self):
        if lpms.getopt("--help") or len(self.patterns) == 0:
            self.usage()

        replace = re.compile("(%s)" % "|".join(self.patterns), re.I)
        for repo, category, name in self.repodb.get_all_names():
            summary = self.repodb.get_summary(name, repo, category)[0]
            if replace.search(name) is not None or replace.match(name) is not None or \
                replace.search(summary) is not None:
                
                versions = []
                map(lambda x: versions.extend(x), self.repodb.get_version(name, repo, category).values())
                
                pkg_status = ""
                if  self.instdb.get_repo(category, name) == repo:
                    pkg_status = "["+out.color("I", "brightgreen")+"] "
                
                if lpms.getopt("--mark"):
                    out.write("%s%s/%s/%s (%s)\n    %s" %(pkg_status, repo, category, 
                        replace.sub(out.color(r"\1", "red"), name),
                        " ".join(versions),
                        replace.sub(out.color(r"\1", "red"), summary))+'\n')
                else:
                    out.write("%s%s/%s/%s (%s)\n    %s" % (pkg_status, out.color(repo, "green"),  
                        out.color(category, "green"),
                        out.color(name, "green"),
                        " ".join(versions),
                        summary+'\n'))
