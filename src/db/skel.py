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

from lpms import constants as const

def installed_schema():
    return """
        create table metadata(
            repo text,
            category text,
            name text,
            version blob,
            summary text,
            homepage text,
            license text,
            src_url text,
            options text
        );

        create table build_info(
            repo text,
            category text,
            name text,
            version text,
            build_time text,
            host text,
            cflags text,
            cxxflags text,
            ldflags text,
            applied text,
            size integer
        );

        create table depends(
            repo text,
            category text,
            name text,
            build blob,
            runtime blob
        );
        """

def repo_schema():
    return """
        create table metadata(
            repo text,
            category text,
            name text,
            version blob,
            summary text,
            homepage text,
            license text,
            src_url text,
            options text
        );

        create table depends(
            repo text,
            category text,
            name text,
            version text,
            build blob,
            runtime blob
        );
    """

def schema(db_path):
    if db_path == const.repositorydb_path:
        return repo_schema()
    elif db_path == const.installdb_path:
        return installed_schema()
