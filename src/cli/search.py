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

help_output = (('--mark', '-m', 'use markers to highlight the matching strings'),)

class Search(object):
    def __init__(self, patterns):
        self.patterns = patterns
        self.repo_db = dbapi.RepositoryDB()

    def usage(self):
        out.normal("Search given keywords in database")
        out.green("General Usage:\n")
        out.write(" $ lpms -s <keyword>\n")
        out.write("\nOther options:\n")
        for h in help_output:
            if len(h) == 3:
                out.write("%s, %-10s: %s\n" % (out.color(h[0],"green"), 
                    out.color(h[1], "green"), h[2]))
        lpms.terminate()

    def search(self):
        if lpms.getopt("--help") or len(self.patterns) == 0:
            self.usage()

        replace = re.compile("(%s)" % "|".join(self.patterns), re.I)
        for repo, category, name in self.repo_db.get_all_names():
            summary = self.repo_db.get_summary(name, repo, category)[0]
            if replace.search(name) is not None or replace.match(name) is not None or \
                replace.search(summary) is not None:
                
                versions = []
                map(lambda x: versions.extend(x), self.repo_db.get_version(name, repo, category).values())
                if lpms.getopt("--mark"):
                    out.write("%s/%s (%s)\n    %s" %(category, 
                        replace.sub(out.color(r"\1", "red"), name),
                        " ".join(versions),
                        replace.sub(out.color(r"\1", "red"), summary))+'\n')
                else:
                    out.write("%s/%s (%s)\n    %s" % (out.color(category, "green"),
                        out.color(name, "green"),
                        " ".join(versions),
                        summary+'\n'))
