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
from lpms.db import filesdb


def main(keywords):
    length = len(keywords)
    if length == 0:
        out.error("no keyword given")

        lpms.terminate()

    if length > 1:
        keywords = keywords[0:1]

    idb = dbapi.InstallDB()

    out.normal("searching for %s\n" % keywords[0])

    for i in idb.get_all_names():
        repo, category, name = i
        versions = []
        map(lambda x: versions.extend(x), idb.get_version(name, repo ,category).values())
        for version in versions:
            fdb = filesdb.FilesDB(category, name, version, "/")
            fdb.import_xml()
            
            for tag in ('dirs', 'file'):
                for text in fdb.content[tag]:
                    if keywords[0]  in text:
                        replace = re.compile("(%s)" % '|'.join(keywords), re.I)  
                        out.write("%s/%s/%s-%s -- %s\n" % 
                                (out.color(repo, "green"), 
                                    out.color(category, "green"),
                                    out.color(name, "green"), 
                                    out.color(version, "green"), 
                                    replace.sub(out.color(r"\1", "red"), text)))		

