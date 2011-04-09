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

import lpms
from lpms import constants as cst
from lpms import internals
from lpms.db import dbapi
from lpms import utils
from lpms import syncer
from lpms import out

class Update(internals.InternalFuncs):
    def __init__(self):
        super(Update, self).__init__()
        self.repo_db = dbapi.RepositoryDB()

    def update_repository(self, repo_name):
        exceptions = ['info', 'libraries', '.git', '.svn']
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
            out.notify("%s" % out.color(category, "brightwhite"))
            for my_pkg in packages:
                os.chdir(os.path.join(repo_path, category, my_pkg))
                for pkg in glob.glob("*"+cst.spec_suffix):
                    script_path = os.path.join(repo_path, category, my_pkg, pkg)
                    self.env.name, self.env.version = utils.parse_pkgname(pkg.split(cst.spec_suffix)[0])
                    self.import_script(script_path)
                    metadata = utils.metadata_parser(self.env.metadata)
                    name, version = utils.parse_pkgname(pkg.split(cst.spec_suffix)[0])
                    metadata.update({"name": name, "version": version})
                    if not "options" in metadata:
                        metadata.update({"options": None})
                    if not "slot" in metadata:
                        metadata.update({"slot": "0"})
                    if not "arch" in metadata:
                        metadata.update({"arch": None})

                    out.write("    %s-%s\n" % (name, version))
                    data = (repo_name, category, metadata["name"], metadata["version"], 
                            metadata["summary"], metadata["homepage"], metadata["license"], 
                            metadata["src_url"], metadata["options"], 
                            metadata['slot'], metadata['arch'])
                    repo, category, name, version, summary, homepage, _license, src_url, options, slot, arch = data
                    self.repo_db.add_pkg(data, commit=False)
                    # add dependency mumbo-jumbo
                    runtime = []; build = []
                    if 'depends' in self.env.__dict__.keys():
                            deps = utils.depends_parser(self.env.depends)
                            if 'runtime' in deps.keys():
                                runtime = deps['runtime']
                            if 'build' in deps.keys():
                                build = deps['build']
                    dependencies = (repo, category, name, version, build, runtime)
                    self.repo_db.add_depends(dependencies)
                    # remove optional keys
                    for key in ('depends', 'options'):
                        try:
                            del self.env.__dict__[key]
                        except KeyError:
                            pass
        self.repo_db.commit()

def main(repo_name=None):
    operation = Update()
    if repo_name is None:
        out.normal("synchronizing repositories...")
        for repo_name in os.listdir(cst.repos):
            if os.path.isfile(os.path.join(cst.repos, repo_name, "info/repo.conf")):
                print(out.color(" "+repo_name, "brightgreen"))
                operation.update_repository(repo_name)
    else:
        repo_dir = os.path.join(cst.repos, repo_name)
        if os.path.isdir(repo_dir):
            repo_path = os.path.join(repo_dir, cst.repo_file)
            if os.path.isfile(repo_path):
                out.normal("synchronizing %s" % out.color(repo_name, "brightgreen"))
                syncer.run(repo_path)
                operation.update_repository(repo_name)
            else:
                lpms.terminate("repo.conf file could not found in %s" % repo_dir+"/info")
        else:
            lpms.terminate("repo.conf not found in %s" % os.path.join(cst.repos, repo_name))
