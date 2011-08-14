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

# Useless API imlementation for lpms

import os
import cPickle as pickle

import lpms

from lpms import out
from lpms import utils
from lpms import resolver
from lpms import internals
from lpms import shelltools
from lpms import interpreter
from lpms import constants as cst

from lpms.db import dbapi

from lpms.operations import sync
from lpms.operations import build
from lpms.operations import update
from lpms.operations import remove
from lpms.operations import upgrade


class InitializeInterpreter(internals.InternalFuncs):
    '''Base class for initialize the lpms spec interpreter
    It can be used for any purpose'''
    def __init__(self, script, instruct, operations):
        super(InitializeInterpreter, self).__init__()
        self.script = script
        self.env.__dict__.update(instruct)
        self.operations = operations
        self.env.__dict__["get"] = self.get

    def initialize(self):
        '''Registers some basic environmet variables and runs the interpreter'''
        repo, category, name, version = self.script
        out.normal("configuring %s/%s/%s-%s" % (repo, category, name, version))

        for key, data in {"repo": repo, "name": name, "version": version, \
                "category": category, "pkgname": name}.items():
            setattr(self.env, key, data)

        spec_file = os.path.join(cst.repos, repo, category, \
                name, name)+"-"+version+cst.spec_suffix

        # compile the script
        self.import_script(spec_file)

        # remove irrelevant functions for environment.
        # because, the following functions must be run by Build class
        # that is defined in operations/build.py
        for func in ('prepare', 'install', 'build', 'configure'):
            if func in self.env.__dict__:
                delattr(self.env, func)

        return interpreter.run(spec_file, self.env, self.operations)


def configure_pending(packages, instruct):
    '''Configure packages that do not configured after merge operation'''
    root = instruct["real_root"]
    if not root:
        root = cst.root
        instruct["real_root"] = root

    pending_file = os.path.join(root, cst.configure_pending_file)

    failed = []

    if not os.access(pending_file, os.F_OK):
        lpms.terminate("there are no pending packages.")

    with open(pending_file, 'rb') as data:
        pending_packages = pickle.load(data)
        for package in pending_packages:
            if not InitializeInterpreter(package, instruct, ['post_install']).initialize():
                repo, category, name, version = package 
                out.warn("%s/%s/%s-%s could not configured." % (repo, category, name, version))
                failed.append(package)

    shelltools.remove_file(pending_file)
    if failed:
        with open(pending_file, 'wb') as data:
            pickle.dump(failed, data)

def update_repository(cmdline):
    '''Runs repository update operation'''
    update.main(cmdline)

def syncronize(cmdline, instruct):
    '''Syncronizes package repositories via any SCM
    and run update and upgrade operations if wanted'''
    query = cmdline
    if not cmdline:
        query = utils.valid_repos()

    for repo in query:
        sync.SyncronizeRepo().run(repo)

    if instruct["update"]:
        update_repository(cmdline)

    if instruct["upgrade"]:
        upgrade_system(instruct)

def get_pkg(pkgname, repositorydb=True):
    '''Parses given pkgnames and selects suitable versions and 
    repositories:

        main/sys-devel/binutils
        sys-devel/binutils
        binutils

    If the user wants to determine the package version, it should use
    the following notation:
        
        =main/sys-devel/binutils-2.13
        =binutils-2.13
        =sys-devel/binutils-2.14
    '''

    def select_version(data):
        versions = []
        map(lambda ver: versions.extend(ver), data.values())
        return utils.best_version(versions)
    
    def get_name(data):
        return utils.parse_pkgname(data)

    db = dbapi.RepositoryDB()
    if not repositorydb:
        db = dbapi.InstallDB()

    repo = None; category = None; version = None
    # FIXME: '=' unnecessary?
    if pkgname.startswith("="):
        pkgname = pkgname[1:]

    #if pkgname.endswith(".py"):
    #    name, version = get_name(pkgname.split(".py")[0])
    #    return None, None, name, version
        #print name, version
        #utils.import_script(pkgname)

    parsed = pkgname.split("/")
    if len(parsed) == 1:
        name = parsed[0]
    elif len(parsed) == 2:
        category, name = parsed
    elif len(parsed) == 3:
        repo, category, name = parsed

    if len(name.split("-")) > 1:
        result = get_name(name)
        if result is not None:
            name, version = result

    if version:
        # check repository priority for given version
        data = db.find_pkg(name, repo_name = repo, pkg_category = category)
        if data:
            repos = [r[0] for r in data]
            found = False
            for valid_repo in utils.valid_repos():
                if valid_repo in repos:
                    result = data[repos.index(valid_repo)]
                    versions = []
                    map(lambda ver: versions.extend(ver), result[-1].values())
                    if version in versions:
                        found = True
                        break
            if not found:
                result = None
        else:
            result = None
    else:
        result = db.find_pkg(name, repo_name = repo, pkg_category = category, 
            selection = True)

    if not result:
        out.error("%s not found in repository database." % out.color(pkgname, "brightred"))
        lpms.terminate()

    length = len(result)
    if length == 1:
        repo, category, name, version_data = result[0]
        if version is None:
            version = select_version(version_data)
        return repo, category, name, version

    elif length == 4:
        repo, category, name, version_data = result
        if version is None:
            version = select_version(version_data)
        return repo, category, name, version

def upgrade_system(instruct):
    '''Runs UpgradeSystem class and triggers API's build function
    if there are {upgrade, downgrade}able package'''
    out.normal("scanning database for package upgrades...\n")
    up = upgrade.UpgradeSystem()
    # prepares lists that include package names which 
    # are effected by upgrade operation.
    up.select_pkgs()

    if not up.packages:
        out.write("no package found to upgrade.\n")
        lpms.terminate()

    pkgbuild(up.packages, instruct)

def remove_package(pkgnames, instruct):
    '''Triggers remove operation for given packages'''
    remove.main([get_pkg(pkgname, repositorydb=False) for pkgname \
            in pkgnames], instruct)

def resolve_dependencies(data, cmd_options, use_new_opts, specials=None):
    '''Resolve dependencies using fixit object. This function
    prepares a full operation plan for the next stages'''
    out.normal("resolving dependencies")
    fixit = resolver.DependencyResolver()
    return fixit.resolve_depends(data, cmd_options, use_new_opts, specials)

def pkgbuild(pkgnames, instruct):
    '''Starting point of build operation'''
    plan = resolve_dependencies([get_pkg(pkgname) for pkgname in pkgnames],
            instruct['cmd_options'], instruct['use-new-opts'],
            instruct['specials'])
    build.main(plan, instruct)
