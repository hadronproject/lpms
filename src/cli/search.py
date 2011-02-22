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

class Search(object):
    def __init__(self, patterns):
        self.patterns = patterns
        self.repo_db = dbapi.RepositoryDB()

    def usage(self):
        out.normal("Search given keywords in database")
        out.green("General Usage:\n")
        out.write(" $ lpms -s <keyword>\n")
        lpms.terminate()

    def search(self):
        if lpms.getopt("--help") or len(self.patterns) == 0:
            self.usage()

        replace = re.compile("(%s)" % "|".join(self.patterns), re.I)
        for repo, category, name in self.repo_db.get_all_names():
            summary = self.repo_db.get_summary(name, repo, category)[0]
            if replace.match(name) is not None or replace.search(summary) is not None:
                out.write("%s/%s -- %s" % (category,
                    replace.sub(out.color(r"\1", "red"), name),
                    replace.sub(out.color(r"\1", "red"), summary))+"\n")
