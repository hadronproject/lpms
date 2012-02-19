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

from lpms import out
from lpms import utils
from lpms import internals
from lpms import constants as cst

from lpms.db import dbapi

class Update(internals.InternalFuncs):
    def __init__(self):
        super(Update, self).__init__()
        self.repo_db = dbapi.RepositoryDB()
        self.packages_num = 0

    def update_repository(self, repo_name):
        exceptions = ['scripts', 'licenses', 'news', 'info', 'libraries', '.git', '.svn']
        # fistly, drop the repo
        self.repo_db.drop_repo(repo_name)
        repo_path = os.path.join(cst.repos, repo_name)
        for category in os.listdir(repo_path):
            if category in exceptions:
                continue
            packages = os.listdir(os.path.join(repo_path, category))
            try:
                packages.remove("info.xml")
            except ValueError:
                pass
            if lpms.getopt("--verbose"):
                out.notify("%s" % out.color(category, "brightwhite"))
            for my_pkg in packages:
                self.update_package(repo_path, category, my_pkg)
        self.repo_db.commit()

    def update_package(self, repo_path, category, my_pkg, my_version = None, update = False):
        repo_name = os.path.basename(repo_path)
        os.chdir(os.path.join(repo_path, category, my_pkg))
        for pkg in glob.glob("*"+cst.spec_suffix):
            script_path = os.path.join(repo_path, category, my_pkg, pkg)

            self.env.name, self.env.version = utils.parse_pkgname(pkg.split(cst.spec_suffix)[0])
            self.env.__dict__["fullname"] = self.env.name+"-"+self.env.version

            try:
                self.import_script(script_path)
            except:
                traceback.print_exc()
                out.error("an error occured while processing %s" % out.color(script_path, "red"))
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

            #sys.write.stdin("    %s-%s\r" % (self.env.name, self.env.version))
            if lpms.getopt("--verbose"):
                out.write("    %s-%s\n" % (self.env.name, self.env.version))
            try:
                data = (repo_name, category, metadata["name"], metadata["version"], 
                        metadata["summary"], metadata["homepage"], metadata["license"], 
                        metadata["src_url"], metadata["options"], 
                        metadata['slot'], metadata['arch'])
            except KeyError as err:
                out.error("%s/%s/%s-%s: invalid metadata" % (repo_name, category, \
                        self.env.name, self.env.version))
                out.warn("repository update was failed and the repository database was removed.")
                out.warn("you can run 'lpms --reload-previous-repodb' command to reload previous db version.")
                lpms.terminate("good luck!")

            (repo, category, self.env.name, self.env.version, 
                    summary, homepage, _license, src_url, options, slot, arch) = data
            
            if update:
                self.repo_db.remove_pkg(repo, category, self.env.name, self.env.version)

            self.repo_db.add_pkg(data, commit=False)
            # add dependency mumbo-jumbo
            runtime = []; build = []; postmerge = []; conflict = []
            if 'depends' in self.env.__dict__.keys():
                deps = utils.depends_parser(self.env.depends)
                if 'runtime' in deps:
                    runtime.extend(deps['runtime'])
                if 'build' in deps:
                    build.extend(deps['build'])
                if 'common' in deps:
                    runtime.extend(deps['common'])
                    build.extend(deps['common'])
                if 'postmerge' in deps:
                    postmerge.extend(deps['postmerge'])
                if 'conflict' in deps:
                    conflict.extend(deps['conflict'])

            for opt in ('opt_common', 'opt_conflict', 'opt_postmerge', 'opt_runtime', 'opt_build'):
                try:
                    deps = utils.parse_opt_deps(getattr(self.env, opt))
                    if opt.split("_")[1] == "runtime":
                        runtime.append(deps)
                    elif opt.split("_")[1] == "build":
                        build.append(deps)
                    elif opt.split("_")[1] == "common":
                        build.append(deps)
                        runtime.append(deps)
                    elif opt.split("_")[1] == "postmerge":
                        postmerge.append(deps)
                    elif opt.split("_")[1] == "conflict":
                        conflict.append(deps)
                    del deps
                except AttributeError:
                    continue

            dependencies = (repo, category, self.env.name, self.env.version, 
                    build, runtime, postmerge, conflict)
            self.repo_db.add_depends(dependencies)
            # remove optional keys
            for key in ('depends', 'options', 'opt_runtime', 
                    'opt_build', 'opt_conflict', 'opt_common', 
                    'opt_postmerge'):
                try:
                    del self.env.__dict__[key]
                except KeyError:
                    pass
            self.packages_num += 1
        #self.repo_db.commit()

def db_backup():
    import time
    from lpms.shelltools import copy, remove_file

    # remove previous database backup
    dirname = os.path.dirname(cst.repositorydb_path)
    for _file in os.listdir(dirname):
        if _file.startswith("repositorydb") and _file.count(".") == 2:
            remove_file(os.path.join(dirname, _file))

    # create a backup with UNIX timestamp
    timestamp = int(time.time())
    copy(cst.repositorydb_path, cst.repositorydb_path+".%s" % timestamp)

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
        for repo_name in os.listdir(cst.repos):
            if not repo_name in utils.valid_repos():
                continue
            if os.path.isfile(os.path.join(cst.repos, repo_name, "info/repo.conf")):
                out.write(out.color(" * ", "red") + repo_name+"\n")
                
                operation.update_repository(repo_name)
                repo_num += 1
                
        out.normal("%s repository(ies) is/are updated." % repo_num)
    else:
        if repo_name == ".":
            current_path = os.getcwd()
            for repo_path in [os.path.join(cst.repos, item) \
                    for item in utils.valid_repos()]:
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
            
            if not repo in utils.valid_repos():
                out.error("%s is not a repository." % out.color(repo, "red"))
                lpms.terminate()

            for pkg in os.listdir(os.path.join(repo_path, category)):
                operation.update_package(repo_path, category, pkg, update=True)
            operation.repo_db.commit()
        
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
            
            if not repo in utils.valid_repos():
                out.error("%s is not a repository." % out.color(repo, "red"))
                lpms.terminate()

            repo_path = os.path.join(cst.repos, repo)
            out.normal("updating %s/%s/%s" % (repo, category, name))
            operation.update_package(repo_path, category, name, my_version = version, update = True)
            operation.repo_db.commit()
        
        else:
            if not repo_name in utils.valid_repos():
                out.error("%s is not a repository." % out.color(repo_name, "red"))
                lpms.terminate()
            
            repo_dir = os.path.join(cst.repos, repo_name)
            if os.path.isdir(repo_dir):
                repo_path = os.path.join(repo_dir, cst.repo_file)
                if os.path.isfile(repo_path):
                    out.normal("updating repository: %s" % out.color(repo_name, "green"))
                    operation.update_repository(repo_name)
                    operation.repo_db.commit()
                else:
                    lpms.terminate("repo.conf file could not found in %s" % repo_dir+"/info")
            else:
                lpms.terminate("repo.conf not found in %s" % os.path.join(cst.repos, repo_name))

    out.normal("Total %s packages have been processed." % operation.packages_num)
    
    for repo in operation.repo_db.get_repos():
        if not repo[0] in utils.valid_repos():
            operation.repo_db.drop_repo(repo[0])
            out.warn("%s dropped." % repo[0])
