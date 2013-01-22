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

import os
import sys
import sqlite3

import lpms

from lpms import constants as cst

from lpms.db import schemas

class LpmsDatabase(object):
    def __init__(self):
        root = cst.root
        for option in sys.argv:
            if option.startswith("--change-root"):
                root = option.replace("--change-root=", "")
                break
        if self.__class__.__module__.endswith(cst.repositorydb):
            self.dbpath = os.path.join(root, cst.db_path, cst.repositorydb)+cst.db_prefix
        elif self.__class__.__module__.endswith(cst.installdb):
            self.dbpath = os.path.join(root, cst.db_path, cst.installdb)+cst.db_prefix
        elif self.__class__.__module__.endswith(cst.filesdb):
            self.dbpath = os.path.join(root, cst.db_path, cst.filesdb)+cst.db_prefix
        elif self.__class__.__module__.endswith(cst.file_relationsdb):
            self.dbpath = os.path.join(root, cst.db_path, cst.file_relationsdb)+cst.db_prefix
        elif self.__class__.__module__.endswith(cst.reverse_dependsdb):
            self.dbpath = os.path.join(root, cst.db_path, cst.reverse_dependsdb)+cst.db_prefix
        else:
            raise Exception("%s seems an invalid child class." % self.__class__.__module__)

        if not os.path.exists(os.path.dirname(self.dbpath)):
            os.makedirs(os.path.dirname(self.dbpath))

        try:
            self.connection = sqlite3.connect(self.dbpath)
        except sqlite3.OperationalError:
            # TODO: Use an exception for this.
            lpms.terminate("lpms could not connected to the database (%s)" % self.dbpath)

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

        database = self.__class__.__module__.split(".")[-1]
        if not content:
            print("Creating %s on %s" % (database, self.dbpath))
            self.cursor.executescript(getattr(schemas, database)())
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
        try:
            return self.connection.commit()
        except sqlite3.OperationalError as err:
            # TODO: Parse the exception and show it to the user in a suitable form
            print(err)
            self.cursor.close()
            lpms.terminate()

