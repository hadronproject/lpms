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
            options text,
            arch blob
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
            version text,
            build blob,
            runtime blob,
            postmerge blob,
            conflict blob
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
            options blob,
            arch blob
        );

        create table depends(
            repo text,
            category text,
            name text,
            version text,
            build blob,
            runtime blob,
            postmerge blob,
            conflict blob
        );
    """

def file_relations_schema():
    return """
        create table file_relations (
            repo text,
            category text,
            name text,
            version text,
            file_path text,
            depend text
        );
    """

def schema(db_path):
    if len(db_path.split(const.repositorydb_path)) == 2:
        return repo_schema()
    
    if len(db_path.split(const.installdb_path)) == 2:
        return installed_schema()
    
    if len(db_path.split(const.file_relationsdb_path)) == 2:
        return file_relations_schema()

