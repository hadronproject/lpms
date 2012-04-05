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
from lpms import conf
from lpms import utils
from lpms import resolver
from lpms import internals
from lpms import initpreter
from lpms import shelltools
from lpms import interpreter
from lpms import file_relations
from lpms import file_collisions
from lpms import constants as cst

from lpms.db import dbapi
from lpms.db import api as DBapi

from lpms.operations import sync
from lpms.operations import build
from lpms.operations import update
from lpms.operations import remove
from lpms.operations import upgrade

from lpms.exceptions import UnavailablePackage

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
            spec = os.path.join(cst.repos, repo, category, name)+"/"+name+"-"+version+".py"
            out.normal("configuring %s/%s/%s-%s" % (repo, category, name, version))
            if not os.access(spec, os.R_OK):
                out.warn("%s seems not exist or not readable. skipping..." % spec)
                failed.append(package)
                continue
            if not initpreter.InitializeInterpreter(package, instruct, ['post_install']).initialize():
                out.warn("%s/%s/%s-%s could not configured." % (repo, category, name, version))
                failed.append(package)

    shelltools.remove_file(pending_file)
    if failed:
        with open(pending_file, 'wb') as data:
            pickle.dump(failed, data)

def update_repository(cmdline):
    '''Runs repository update operation'''
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
    if instruct['like']:
        # handle shortened package names
        database = dbapi.InstallDB()
        for item in instruct['like']:
            query = database.db.cursor.execute("SELECT name FROM metadata where name LIKE ?", (item,))
            results = query.fetchall()
            if results:
                for result in results:
                    pkgnames.append(result[0])
        del database
    file_relationsdb = dbapi.FileRelationsDB()
    reverse_dependsdb = dbapi.ReverseDependsDB()
    packages = [get_pkg(pkgname, repositorydb=False) for pkgname in pkgnames]
    instruct['count'] = len(packages); i = 0;
    if instruct["show-reverse-depends"]:
        instruct["ask"] = True
        # WARNING: the mechanism only shows directly reverse dependencies
        # supposing that if A is a reverse dependency of B and C is depends on A.
        # when the user removes B, A and C will be broken. But lpms will warn the user about A.
        broken_packages = []
        reversedb = dbapi.ReverseDependsDB()
        out.normal("resolving primary reverse dependencies...\n")
        for package in packages:
            category, name, version = package[1:]
            if lpms.getopt("--use-file-relations"):
                broken_packages.extend(file_relations.get_packages(category, name, version))
            else:
                broken_packages.extend(reversedb.get_reverse_depends(category, name))

        if broken_packages:
            out.warn("the following packages will be broken:\n")
            for broken_package in broken_packages:
                broken_repo, broken_category, broken_name, broken_version = broken_package
                out.write(" %s %s/%s/%s-%s\n" % (out.color(">", "brightred"), broken_repo, broken_category, \
                        broken_name, broken_version))
        else:
            out.warn("no reverse dependency found.")


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
    
    realroot = instruct["real_root"] if instruct["real_root"] else cst.root
    config = conf.LPMSConfig()
    instdb = dbapi.InstallDB()
    for package in packages:
        repo, category, name, ver = package
        slot = instdb.get_slot(category, name, ver)
        fdb = file_collisions.CollisionProtect(category, name, slot, version=ver, real_root=realroot)
        fdb.handle_collisions()
        if fdb.collisions:
            out.write(out.color(" > ", "brightyellow")+"file collisions detected while removing %s/%s/%s-%s\n\n" \
                    % (repo, category, name, ver))
        for (c_package, c_path) in fdb.collisions:
            c_category, c_name, c_slot, c_version = c_package
            out.write(out.color(" -- ", "red")+c_category+"/"+c_name+"-"\
                    +c_version+":"+c_slot+" -> "+c_path+"\n")
            if fdb.collisions and config.collision_protect and not \
                    lpms.getopt('--force-file-collision'):
                        out.write("\nquitting... use '--force-file-collision' to continue.\n")
                        lpms.terminate()
        i += 1;
        instruct['i'] = i
        if not initpreter.InitializeInterpreter(package, instruct, ['remove'], remove=True).initialize():
            repo, category, name, version = package 
            out.warn("an error occured during remove operation: %s/%s/%s-%s" % (repo, category, name, version))
        else:
            category, name, version = package[1:]
            file_relationsdb.delete_item_by_pkgdata(category, name, version, commit=True)
            reverse_dependsdb.delete_item(category, name, version, commit=True)

def resolve_dependencies(data, cmd_options, use_new_opts, specials=None):
    '''Resolve dependencies using fixit object. This function
    prepares a full operation plan for the next stages'''
    out.normal("resolving dependencies")
    fixit = resolver.DependencyResolver()
    return fixit.resolve_depends(data, cmd_options, use_new_opts, specials)

class GetPackage:
    '''Selects a convenient package for advanced dependency resolving phases'''
    def __init__(self, package):
        self.package = package
        self.repo = None
        self.category = None
        self.name = None
        self.version = None
        self.slot = None
        self.repodb = DBapi.RepositoryDB()

    def get_convenient_package(self, packages): 
        results = []
        repositories = utils.valid_repos()
        primary = None
        # Firstly, select the correct repository
        for repository in repositories:
            for package in packages:
                if self.slot is not None and \
                        package.slot != self.slot: continue
                if primary is None and package.repo == repository:
                    results.append(package)
                    primary = package.repo
                    continue
                elif primary is not None and package.repo == primary:
                    if not package in results:
                        results.append(package)
                    continue
            if repository != primary: continue

        # Second, select the best version
        versions = [result.version for result in results]
        best_version = utils.best_version(versions)
        for result in results:
            if result.version == best_version:
                return result

    def select(self):
        preform = self.package.split("/")
        if len(preform) == 3:
            self.repo, self.category, fullname = preform
        elif len(preform) == 2:
            self.category, fullname = preform
        elif len(preform) == 1:
            fullname = self.package

        if cst.slot_indicator in fullname:
            fullname, self.slot = fullname.split(":")

        self.name, self.version = utils.parse_pkgname(fullname)

        packages = self.repodb.find_package(package_repo=self.repo, package_name=self.name, \
                package_category=self.category, package_version=self.version)

        the_package = self.get_convenient_package(packages)
        if the_package is None:
            raise UnavailablePackage(self.package)
        return the_package

def pkgbuild(pkgnames, instruct):
    '''Starting point of build operation'''
    if instruct['like']:
        # handle shortened package names
        mydb = DBapi.RepositoryDB()
        for item in instruct['like']:
            query = mydb.database.cursor.execute("SELECT name FROM package where name LIKE ?", (item,))
            results = query.fetchall()
            if results:
                for result in results:
                    pkgnames.append(result[0])
        del mydb

    plan = resolve_dependencies([GetPackage(pkgname).select() for pkgname in pkgnames],
            instruct['cmd_options'], instruct['use-new-opts'],
            instruct['specials'])
    build.main(plan, instruct)
