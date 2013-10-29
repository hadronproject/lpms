# Copyright 2009 - 2013 Burak Sezer <purak@hadronproject.org>
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

from lpms import out
from lpms.db.api import RepositoryDB, InstallDB
from lpms import constants as cst

help_output = (
        ('--only-installed', 'Shows installed packages for given keyword.'),
        ('--in-summary', 'Searchs given keyword in package summaries.'),
)

def classify_packages(results):
    packages = {}
    for result in results:
        if result.pk in packages:
            packages[result.pk].append(result)
        else:
            packages[result.pk] = [result]


def _pretty_print(results):
    for result in classify_packages(results):
        # TODO: get_package_metadata should select a particular field. 
        metadata = db.get_package_metadata(package_id=result.id)
        out.write("%s/%s\n" % (
            out.color(metadata.category, "brightwhite"),
            out.color(metadata.name, "brightgreen")
            )
        )
        out.write("  %s\n" % metadata.summary)


def run_search(names, subparameters):
    global db
    if not "--only-installed" in subparameters:
        db = RepositoryDB()
    else:
        db = InstallDB()

    for name in names:
        results = db.find_package(package_name=name)
        _pretty_print(results)

    sys.exit(0)
