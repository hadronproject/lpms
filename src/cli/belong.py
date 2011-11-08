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

class Belong:
    def __init__(self, keyword):
        self.keyword = keyword
        self.filesdb = dbapi.FilesDB()
        self.installdb = dbapi.InstallDB()

    def usage(self):
        out.normal("Searchs given keyword in files database")
        out.write("no extra command found\n")
        lpms.terminate()

    def search(self):
        self.filesdb.cursor.execute('''SELECT repo, category, name, version, path \
                FROM files WHERE path LIKE (?)''', ('%'+self.keyword+'%',))
        return self.filesdb.cursor.fetchall()

    def main(self):
        if lpms.getopt("--help"):
            self.usage()

        out.normal("searching for %s\n" % self.keyword)

        for (repo, category, name, version, path) in self.search():
            replace = re.compile("(%s)" % '|'.join([self.keyword]), re.I)  
            out.write("%s/%s/%s-%s -- %s\n" % 
                    (out.color(repo, "green"), 
                        out.color(category, "green"),
                        out.color(name, "green"), 
                        out.color(version, "green"), 
                        replace.sub(out.color(r"\1", "brightred"), path)))
