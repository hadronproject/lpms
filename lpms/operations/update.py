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

import os
import glob
import traceback

import lpms

from lpms.types import LCollect
from lpms.types import PackageItem

from lpms import out
from lpms import utils
from lpms import internals
from lpms import constants as cst

from lpms.db import api

class Update(internals.InternalFuncs):
    def __init__(self):
        super(Update, self).__init__()
        self.repodb = api.RepositoryDB()
        self.packages_num = 0

    def update_repository(self, repo_name):
        exceptions = ['scripts', 'licenses', 'news', 'info', 'libraries', '.git', '.svn']
        # fistly, drop the repo
        self.repodb.database.delete_repository(repo_name, commit=True)
        repo_path = os.path.join(cst.repos, repo_name)
        for category in os.listdir(repo_path):
            target_directory = os.path.join(repo_path, category)
            if category in exceptions or not os.path.isdir(target_directory):
                continue
            packages = os.listdir(target_directory)
            try:
                packages.remove("info.xml")
            except ValueError:
                pass
            if lpms.getopt("--verbose"):
                out.notify("%s" % out.color(category, "brightwhite"))
            for my_pkg in packages:
                self.update_package(repo_path, category, my_pkg)

    def update_package(self, repo_path, category, my_pkg, my_version = None, update = False):
        dataset = LCollect()
        repo_name = os.path.basename(repo_path)
        
        dataset.repo = repo_name
        dataset.category = category
        
        os.chdir(os.path.join(repo_path, category, my_pkg))
        for pkg in glob.glob("*"+cst.spec_suffix):
            script_path = os.path.join(repo_path, category, my_pkg, pkg)

            self.env.name, self.env.version = utils.parse_pkgname(pkg.split(cst.spec_suffix)[0])
            
            dataset.name = self.env.name
            dataset.version = self.env.version
            
            self.env.__dict__["fullname"] = self.env.name+"-"+self.env.version

            if not self.import_script(script_path):
                out.error("an error occured while processing the spec: %s" \
                        % out.color(script_path, "red"))
                out.error("please report the above error messages to the package maintainer.")
                lpms.terminate()

            metadata = utils.metadata_parser(self.env.metadata)
            metadata.update({"name": self.env.name, "version": self.env.version})
            if not "options" in metadata:
                metadata.update({"options": None})
            if not "slot" in metadata:
                metadata.update({"slot": "0"})
            if not "arch" in metadata:
                metadata.update({"arch": None})
            if not "src_url" in metadata:
                metadata.update({"src_url": None})

            if lpms.getopt("--verbose"):
                out.write("    %s-%s\n" % (self.env.name, self.env.version))
            
            try:
                dataset.summary = metadata['summary']
                dataset.homepage = metadata['homepage']
                dataset.license = metadata['license']
                dataset.src_uri = metadata['src_url']
                if metadata['options'] is None:
                    dataset.options = None
                else:
                    dataset.options = metadata['options'].split(" ")
                dataset.slot = metadata['slot']

            except KeyError as err:
                out.error("%s/%s/%s-%s: invalid metadata" % (repo_name, category, \
                        self.env.name, self.env.version))
                out.warn("repository update was failed and the repository database was removed.")
                out.warn("you can run 'lpms --reload-previous-repodb' command to reload previous db version.")
                lpms.terminate("good luck!")

            if update:
                self.repodb.delete_package(package_repo=dataset.repo, package_category=dataset.category, \
                        package_name=self.env.name, package_version=self.env.version)

            static_depends_runtime = []; static_depends_build = []; static_depends_postmerge = []; static_depends_conflict = []
            if 'depends' in self.env.__dict__.keys():
                deps = utils.depends_parser(self.env.depends)
                if 'runtime' in deps:
                    static_depends_runtime.extend(deps['runtime'])
                if 'build' in deps:
                    static_depends_build.extend(deps['build'])
                if 'common' in deps:
                    static_depends_runtime.extend(deps['common'])
                    static_depends_build.extend(deps['common'])
                if 'postmerge' in deps:
                    static_depends_postmerge.extend(deps['postmerge'])
                if 'conflict' in deps:
                    static_depends_conflict.extend(deps['conflict'])

            optional_depends_runtime = []; optional_depends_build = []; optional_depends_postmerge = []; optional_depends_conflict = []
            for opt in ('opt_common', 'opt_conflict', 'opt_postmerge', 'opt_runtime', 'opt_build'):
                try:
                    deps = utils.parse_opt_deps(getattr(self.env, opt))
                    if opt.split("_")[1] == "runtime":
                        optional_depends_runtime.append(deps)
                    elif opt.split("_")[1] == "build":
                        optional_depends_build.append(deps)
                    elif opt.split("_")[1] == "common":
                        optional_depends_build.append(deps)
                        optional_depends_runtime.append(deps)
                    elif opt.split("_")[1] == "postmerge":
                        optional_depends_postmerge.append(deps)
                    elif opt.split("_")[1] == "conflict":
                        optional_depends_conflict.append(deps)
                    del deps
                except AttributeError:
                    continue

            dataset.optional_depends_runtime = optional_depends_runtime
            dataset.optional_depends_build = optional_depends_build
            dataset.optional_depends_postmerge = optional_depends_postmerge
            dataset.optional_depends_conflict = optional_depends_conflict

            dataset.static_depends_runtime = static_depends_runtime
            dataset.static_depends_build = static_depends_build
            dataset.static_depends_postmerge = static_depends_postmerge
            dataset.static_depends_conflict = static_depends_conflict

            if metadata['arch'] is not None:
                arches = metadata['arch'].split(" ")
                for arch in arches:
                    dataset.arch = arch
                    self.repodb.insert_package(dataset)
            else:
                dataset.arch = None
                self.repodb.insert_package(dataset)

            # remove optional keys
            for key in ('depends', 'options', 'opt_runtime', 'opt_build', \
                    'opt_conflict', 'opt_common', 'opt_postmerge'):
                try:
                    del self.env.__dict__[key]
                except KeyError:
                    pass
            self.packages_num += 1

def db_backup():
    import time
    from lpms.shelltools import copy, remove_file

    # remove previous database backup
    dirname = os.path.join(cst.root, cst.db_path)
    for _file in os.listdir(dirname):
        if _file.startswith("repositorydb") and _file.count(".") == 2:
            remove_file(os.path.join(dirname, _file))

    # create a backup with UNIX timestamp
    timestamp = int(time.time())
    repositorydb = os.path.join(cst.root, cst.db_path, cst.repositorydb)+cst.db_prefix
    copy(repositorydb, repositorydb+".%s" % timestamp)

def main(params):
    # determine operation type
    repo_name = None
    if params:
        repo_name = params[0]

    # create operation object
    operation = Update()

    repo_num = 0 
    if repo_name is None:
        # firstly, lpms tries to create a copy of current repository database.
        db_backup()

        out.normal("updating repository database...")
        operation.repodb.database.begin_transaction()
        for repo_name in os.listdir(cst.repos):
            if not repo_name in utils.available_repositories():
                continue
            if os.path.isfile(os.path.join(cst.repos, repo_name, "info/repo.conf")):
                out.write(out.color(" * ", "red") + repo_name+"\n")
                
                operation.update_repository(repo_name)
                repo_num += 1

        operation.repodb.database.commit()
        out.normal("%s repository(ies) is/are updated." % repo_num)
    else:
        if repo_name == ".":
            current_path = os.getcwd()
            for repo_path in [os.path.join(cst.repos, item) \
                    for item in utils.available_repositories()]:
                if current_path == repo_path or len(current_path.split(repo_path)) == 2:
                    # convert it a valid repo_name variable from the path
                    repo_name = current_path.split(cst.repos)[1][1:]
                    break
            if repo_name == ".":
                out.warn("%s does not seem a valid repository path." % \
                        out.color(current_path, "red"))
                lpms.terminate()

        if len(repo_name.split("/")) == 2:
            out.normal("updating %s" % repo_name)
            repo, category = repo_name.split("/")
            repo_path = os.path.join(cst.repos, repo)
            
            if not repo in utils.available_repositories():
                out.error("%s is not a repository." % out.color(repo, "red"))
                lpms.terminate()

            operation.repodb.database.begin_transaction()
            for pkg in os.listdir(os.path.join(repo_path, category)):
                operation.update_package(repo_path, category, pkg, update=True)
            operation.repodb.database.commit()

        elif len(repo_name.split("/")) == 3:
            version = None
            repo, category, name = repo_name.split("/")
            
            if repo.startswith("="):
                repo = repo[1:]
                try:
                    name, version = utils.parse_pkgname(name)
                except TypeError:
                    out.error("you should give a version number")
                    lpms.terminate()
            else:
                if utils.parse_pkgname(name) is not None and len(utils.parse_pkgname(name)) == 2:
                    out.error("you must use %s" % (out.color("="+repo_name, "red")))
                    lpms.terminate()
            
            if not repo in utils.available_repositories():
                out.error("%s is not a repository." % out.color(repo, "red"))
                lpms.terminate()

            repo_path = os.path.join(cst.repos, repo)
            out.normal("updating %s/%s/%s" % (repo, category, name))
            operation.repodb.database.begin_transaction()
            operation.update_package(repo_path, category, name, my_version = version, update = True)
            operation.repodb.database.commit()
        
        else:
            if not repo_name in utils.available_repositories():
                out.error("%s is not a repository." % out.color(repo_name, "red"))
                lpms.terminate()
            
            repo_dir = os.path.join(cst.repos, repo_name)
            if os.path.isdir(repo_dir):
                repo_path = os.path.join(repo_dir, cst.repo_file)
                if os.path.isfile(repo_path):
                    operation.repodb.database.begin_transaction()
                    out.normal("updating repository: %s" % out.color(repo_name, "green"))
                    operation.update_repository(repo_name)
                    operation.repodb.database.commit()
                else:
                    lpms.terminate("repo.conf file could not found in %s" % repo_dir+"/info")
            else:
                lpms.terminate("repo.conf not found in %s" % os.path.join(cst.repos, repo_name))

    out.normal("Total %s packages have been processed." % operation.packages_num)
    
    # Drop inactive repository from the database
    for name in operation.repodb.get_repository_names():
        if not name in utils.available_repositories():
            operation.repodb.delete_repository(name, commit=True)
            out.warn("%s dropped." % name)
    
    # Close the database connection
    operation.repodb.database.close()
