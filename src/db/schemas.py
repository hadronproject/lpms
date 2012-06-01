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

def installdb():
     return """
        CREATE TABLE package(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo TEXT,
            category TEXT,
            name TEXT,
            version TEXT,
            slot TEXT,
            summary TEXT,
            homepage TEXT,
            license TEXT,
            src_uri TEXT,
            applied_options BLOB,
            options BLOB,
            arch TEXT,
            parent TEXT,
            optional_depends_runtime BLOB,
            optional_depends_build BLOB,
            optional_depends_postmerge BLOB,
            optional_depends_conflict BLOB,
            static_depends_runtime BLOB,
            static_depends_build BLOB,
            static_depends_postmerge BLOB,
            static_depends_conflict BLOB
        );

        CREATE TABLE build_info(
            repo TEXT,
            category TEXT,
            name TEXT,
            version TEXT,
            slot TEXT,
            arch TEXT,
            start_time INTEGER,
            end_time INTEGER,
            requestor TEXT,
            requestor_id INTEGER,
            host TEXT,
            cflags TEXT,
            cxxflags TEXT,
            ldflags TEXT,
            makeopts TEXT,
            size FLOAT
        );

        CREATE TABLE inline_options(
            package_id INTEGER,
            target TEXT,
            options BLOB
        );

        CREATE INDEX inline_options_package_id_target_id_idx ON inline_options (package_id, target_id);
        CREATE INDEX inline_options_package_id_options_idx ON inline_options (package_id, options);
        CREATE INDEX inline_options_target_id_options_idx ON inline_options (target_id, options);

        CREATE INDEX package_repo_category_idx ON package (repo, category);
        CREATE INDEX package_repo_name_idx ON package (repo, name);
        CREATE INDEX package_category_name_idx ON package (category, name);
        CREATE INDEX package_category_name_version_idx ON package (category, name, version);
        CREATE INDEX package_repo_category_name_idx ON package (repo, category, name);
        CREATE INDEX package_repo_category_name_version_idx ON package (repo, category, name, version);
        CREATE INDEX package_repo_category_name_version_slot_idx ON package (repo, category, name, version, slot);
        CREATE INDEX package_category_name_version_slot_idx ON package (category, name, version, slot);
        CREATE INDEX package_name_version_slot_idx ON package (name, version, slot);

        CREATE INDEX build_info_repo_category_idx ON build_info (repo, category);
        CREATE INDEX build_info_repo_name_idx ON build_info (repo, name);
        CREATE INDEX build_info_category_name_idx ON build_info (category, name);
        CREATE INDEX build_info_category_name_version_idx ON build_info (category, name, version);
        CREATE INDEX build_info_repo_category_name_idx ON build_info (repo, category, name);
        CREATE INDEX build_info_repo_category_name_version_idx ON build_info (repo, category, name, version);
        CREATE INDEX build_info_repo_category_name_version_slot_idx ON build_info (repo, category, name, version, slot);
        CREATE INDEX build_info_category_name_version_slot_idx ON build_info (category, name, version, slot);
        CREATE INDEX build_info_name_version_slot_idx ON build_info (name, version, slot);
    """

def repositorydb():
    return """
        CREATE TABLE package(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo TEXT,
            category TEXT,
            name TEXT,
            version TEXT,
            slot TEXT,
            summary TEXT,
            homepage TEXT,
            license TEXT,
            src_uri TEXT,
            options BLOB,
            arch TEXT,
            optional_depends_runtime BLOB,
            optional_depends_build BLOB,
            optional_depends_postmerge BLOB,
            optional_depends_conflict BLOB,
            static_depends_runtime BLOB,
            static_depends_build BLOB,
            static_depends_postmerge BLOB,
            static_depends_conflict BLOB
        );
        CREATE INDEX repo_category_idx ON package (repo, category);
        CREATE INDEX repo_name_idx ON package (repo, name);
        CREATE INDEX category_name_idx ON package (category, name);
        CREATE INDEX category_name_version_idx ON package (category, name, version);
        CREATE INDEX repo_category_name_idx ON package (repo, category, name);
        CREATE INDEX repo_category_name_version_idx ON package (repo, category, name, version);
        CREATE INDEX repo_category_name_version_slot_idx ON package (repo, category, name, version, slot);
        CREATE INDEX category_name_version_slot_idx ON package (category, name, version, slot);
        CREATE INDEX name_version_slot_idx ON package (name, version, slot);
    """

def file_relationsdb():
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

def reverse_dependsdb():
    return """
        CREATE TABLE reverse_depends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER,
            reverse_package_id INTEGER,
            build_dependency INTEGER
        );
    """

def filesdb():
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
