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

def reverse_depends_schema():
    return """
        create table reverse_depends (
            repo text,
            category text,
            name text,
            version text,
            reverse_repo text,
            reverse_category text,
            reverse_name text,
            reverse_version text,
            build_dep integer
        );
    """

def files_schema():
    return """
        create table files (
            repo text,
            category text,
            name text,
            version text,
            path text,
            type text,
            size blob,
            gid text,
            mod text,
            uid text,
            sha1sum text,
            realpath text,
            slot text
        );
    """

def schema(db_path):
    if len(db_path.split(const.repositorydb_path)) == 2:
        return repo_schema()
    
    if len(db_path.split(const.installdb_path)) == 2:
        return installed_schema()
    
    if len(db_path.split(const.file_relationsdb_path)) == 2:
        return file_relations_schema()
    
    if len(db_path.split(const.reverse_dependsdb_path)) == 2:
        return reverse_depends_schema()

    if len(db_path.split(const.filesdb_path)) == 2:
        return files_schema()

