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

import lpms

from lpms import out
from lpms import utils
from lpms import resolver

from lpms.db import dbapi
from lpms.operations import sync
from lpms.operations import build
from lpms.operations import update
from lpms.operations import upgrade


def update_repository(cmdline):
    update.main(cmdline)

def syncronize(cmdline, instruct):
    query = cmdline
    if not cmdline:
        query = utils.valid_repos()

    for repo in query:
        sync.SyncronizeRepo().run(repo)

    if instruct["upgrade"]:
        upgrade_system(instruct)

def get_pkg(pkgname):
    '''Parses given pkgnames:

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

    repodb = dbapi.RepositoryDB()
    repo = None; category = None; version = None
    if pkgname.startswith("="):
        pkgname = pkgname[1:]

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

    result = repodb.find_pkg(name, repo_name = repo, pkg_category = category, 
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
    out.normal("scanning database for package upgrades...\n")
    up = upgrade.UpgradeSystem()
    # prepares lists that include package names which 
    # are effected by upgrade operation.
    up.select_pkgs()

    if not up.packages:
        out.write("no package found to upgrade.\n")
        lpms.terminate()

    pkgbuild(up.packages, instruct)

def resolve_dependencies(data, cmd_options):
    '''Resolve dependencies using fixit object. This function 
    prepares a full operation plan for the next stages'''
    out.normal("resolving dependencies")
    fixit = resolver.DependencyResolver()
    return fixit.resolve_depends(data, cmd_options)

def pkgbuild(pkgnames, instruct):
    '''Starting point of build operation'''
    plan = resolve_dependencies([get_pkg(pkgname) for pkgname in pkgnames], 
            instruct['cmd_options'])
    build.main(plan, instruct)
