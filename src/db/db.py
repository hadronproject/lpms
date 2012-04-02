# Copyright 2009 - 2012 Burak Sezer <purak@hadronproject.org>
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

import sqlite3

import lpms
from lpms.db import schemas

class PackageDatabase(object):
    def __init__(self, db_path):
        self.db_path = db_path
        try:
            self.connection = sqlite3.connect(self.db_path)
        except sqlite3.OperationalError:
            # TODO: Use an exception for this.
            lpms.terminate("lpms could not connected to the database (%s)" % self.db_path)

        self.cursor = self.connection.cursor()
        table = self.cursor.execute('SELECT * FROM sqlite_master WHERE type = "table"')
        if table.fetchone() is None:
            self.initialize_db()

    def initialize_db(self):
        self.cursor.execute('SELECT * FROM sqlite_master WHERE type = "table"')
        tables = self.cursor.fetchall()
        content = []
        for table in tables:
            content.extent(list(table))

        if not content:
            self.cursor.executescript(schemas.schema(self.db_path))
            return True

        for table in content:
            try:
                self.cursor.execute('TRUNCATE TABLE %s' % (table,))
            except sqlite3.OperationalError:
                # skip, can not drop table...
                continue
        return True

    def begin_transaction(self):
        self.cursor.execute('''BEGIN TRANSACTION''')

    def close(self):
        self.cursor.close()

    def commit(self):
        #try:
        return self.connection.commit()
        #except sqlite3.OperationalError as err:
        #    # TODO: Parse the exception and show it to the user in a suitable form
        #    print "burda"
        #    print(err)
        #    self.cursor.close()
        #    lpms.terminate()

