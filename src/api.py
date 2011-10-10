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
from lpms import initpreter
from lpms import shelltools
from lpms import interpreter
from lpms import constants as cst

from lpms.db import dbapi

from lpms.operations import sync
from lpms.operations import build
from lpms.operations import update
from lpms.operations import remove
from lpms.operations import upgrade

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
            repo, category, name, version = package 
            out.normal("configuring %s/%s/%s-%s" % (repo, category, name, version))
            if not initpreter.InitializeInterpreter(package, instruct, ['post_install']).initialize():
                out.warn("%s/%s/%s-%s could not configured." % (repo, category, name, version))
                failed.append(package)

    shelltools.remove_file(pending_file)
    if failed:
        with open(pending_file, 'wb') as data:
            pickle.dump(failed, data)

def update_repository(cmdline):
    '''Runs repository update operation'''
    print utils.is_lpms_running()
    if utils.is_lpms_running():
        out.warn("Ehmm... Seems like another lpms process is still going on. Please try again later.")
        lpms.terminate()
    update.main(cmdline)

def syncronize(cmdline, instruct):
    '''Syncronizes package repositories via any SCM
    and run update and upgrade operations if wanted'''
    query = cmdline
    valid_repos = utils.valid_repos()

    if not cmdline:
        query = valid_repos

    for repo in query:
        if repo in valid_repos:
            sync.SyncronizeRepo().run(repo)
        else:
            out.error("%s is not a valid repository." % repo)
            lpms.terminate()

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
    
    valid_repos = utils.valid_repos()
    def collect_versions(version_data):
        i = []
        map(lambda x: i.extend(x), version_data.values())
        return  i

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

    if version and repo is None:
        # check repository priority for given version
        data = db.find_pkg(name, repo_name = repo, pkg_category = category)
        if data:
            repos = [r[0] for r in data]
            found = False
            for valid_repo in valid_repos:
                if valid_repo in repos:
                    result = data[repos.index(valid_repo)]
                    versions = []
                    map(lambda ver: versions.extend(ver), result[-1].values())
                    if version in versions:
                        found = True
                        break
            
            if not found:
                result = None
                for invalid_repo in repos:
                    if not invalid_repo in valid_repos:
                        for item in data:
                            if invalid_repo == item[0]:
                                for key in item[-1]:
                                    if version in item[-1][key]:
                                        result = item; break
        else:
            result = None
    else:
        result = db.find_pkg(name, repo_name = repo, pkg_category = category, 
            selection = True)

    if not result:
        out.error("%s not found in database." % out.color(pkgname, "brightred"))
        lpms.terminate()

    length = len(result)
    if length == 1:
        repo, category, name, version_data = result[0]
        if version is None:
            version = select_version(version_data)
        else:
            if not version in collect_versions(version_data):
                out.error("%s/%s/%s-%s is not found in the database." % (repo, category, name, version))
                lpms.terminate()
        return repo, category, name, version

    elif length == 4:
        repo, category, name, version_data = result
        if version is None:
            version = select_version(version_data)
        else:
            if not version in collect_versions(version_data):
                out.error("%s/%s/%s-%s is not found in the database." % (repo, category, name, version))
                lpms.terminate()
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
    packages = [get_pkg(pkgname, repositorydb=False) for pkgname in pkgnames]
    instruct['count'] = len(packages); i = 0;
    if instruct['ask']:
        out.write("\n")
        for package in packages:
            repo, category, name, version = package
            out.write(" %s %s/%s/%s-%s\n" % (out.color(">", "brightgreen"), out.color(repo, "green"), 
                out.color(category, "green"), out.color(name, "green"), 
                out.color(version, "green")))
        utils.xterm_title("lpms: confirmation request")
        out.write("\nTotal %s package will be removed.\n\n" % out.color(str(instruct['count']), "green"))
        if not utils.confirm("do you want to continue?"):
            out.write("quitting...\n")
            utils.xterm_title_reset()
            lpms.terminate()

    for package in packages:
        i += 1;
        instruct['i'] = i
        if not initpreter.InitializeInterpreter(package, instruct, ['remove'], remove=True).initialize():
            repo, category, name, version = package 
            out.warn("an error occured during remove operation: %s/%s/%s-%s" % (repo, category, name, version))

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
