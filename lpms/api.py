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

from lpms.db import api as dbapi

from lpms.operations import sync
from lpms.operations import build
from lpms.operations import update
from lpms.operations import remove
from lpms.operations import upgrade

from lpms.exceptions import ConflictError
from lpms.exceptions import LockedPackage
from lpms.exceptions import DependencyError
from lpms.exceptions import PackageNotFound
from lpms.exceptions import UnavailablePackage

def configure_pending(packages, instruct):
    '''Configure packages that do not configured after merge operation'''

    if not utils.check_root(msg=False):
        lpms.terminate("you must be root.")

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
    if not utils.check_root(msg=False):
        lpms.terminate("you must be root.")

    if utils.is_lpms_running():
        out.warn("Ehmm... Seems like another lpms process is still going on. Please try again later.")
        lpms.terminate()
    update.main(cmdline)

def syncronize(cmdline, instruct):
    '''Syncronizes package repositories via any SCM
    and run update and upgrade operations if wanted'''
    if not utils.check_root(msg=False):
        lpms.terminate("you must be root.")

    query = cmdline
    available_repositories = utils.available_repositories()

    if not cmdline:
        query = available_repositories

    for repo in query:
        if repo in available_repositories:
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
    if not utils.check_root(msg=False):
        lpms.terminate("you must be root.")

    if instruct['like']:
        # handle shortened package names
        database = dbapi.InstallDB()
        for item in instruct['like']:
            query = database.db.cursor.execute("SELECT name FROM package where name LIKE ?", (item,))
            results = query.fetchall()
            if results:
                for result in results:
                    pkgnames.append(result[0])
        del database
    file_relationsdb = dbapi.FileRelationsDB()
    try:
        packages = [GetPackage(pkgname, installdb=True).select() for pkgname in pkgnames]
    except PackageNotFound as package_name:
        out.error("%s seems not installed." % package_name)
        lpms.terminate()

    instruct['count'] = len(packages); index = 0;
    # FIXME: I must create a new reverse dependency handler implementation

    #if instruct["show-reverse-depends"]:
    #    instruct["ask"] = True
    #    # WARNING: the mechanism only shows directly reverse dependencies
    #    # supposing that if A is a reverse dependency of B and C is depends on A.
    #    # when the user removes B, A and C will be broken. But lpms will warn the user about A.
    #    broken_packages = []
    #    reversedb = dbapi.ReverseDependsDB()
    #    out.normal("resolving primary reverse dependencies...\n")
    #    for package in packages:
    #        category, name, version = package[1:]
    #        if lpms.getopt("--use-file-relations"):
    #            broken_packages.extend(file_relations.get_packages(category, name, version))
    #        else:
    #            broken_packages.extend(reversedb.get_reverse_depends(category, name))

    #    if broken_packages:
    #        out.warn("the following packages will be broken:\n")
    #        for broken_package in broken_packages:
    #            broken_repo, broken_category, broken_name, broken_version = broken_package
    #            out.write(" %s %s/%s/%s-%s\n" % (out.color(">", "brightred"), broken_repo, broken_category, \
    #                    broken_name, broken_version))
    #    else:
    #        out.warn("no reverse dependency found.")

    if instruct['ask']:
        out.write("\n")
        for package in packages:
            out.write(" %s %s/%s/%s-%s\n" % (out.color(">", "brightgreen"), out.color(package.repo, "green"), 
                out.color(package.category, "green"), out.color(package.name, "green"), 
                out.color(package.version, "green")))
        utils.xterm_title("lpms: confirmation request")
        out.write("\nTotal %s package will be removed.\n\n" % out.color(str(instruct['count']), "green"))
        if not utils.confirm("do you want to continue?"):
            out.write("quitting...\n")
            utils.xterm_title_reset()
            lpms.terminate()
    
    realroot = instruct["real_root"] if instruct["real_root"] else cst.root
    config = conf.LPMSConfig()
    for package in packages:
        fdb = file_collisions.CollisionProtect(package.category, package.name, \
                package.slot, version=package.version, real_root=realroot)
        fdb.handle_collisions()
        if fdb.collisions:
            out.write(out.color(" > ", "brightyellow")+"file collisions detected while removing %s/%s/%s-%s\n\n" \
                    % (package.repo, package.category, package.name, package.version))
        for (c_package, c_path) in fdb.collisions:
            c_category, c_name, c_slot, c_version = c_package
            out.write(out.color(" -- ", "red")+c_category+"/"+c_name+"-"\
                    +c_version+":"+c_slot+" -> "+c_path+"\n")
            if fdb.collisions and config.collision_protect and not \
                    lpms.getopt('--force-file-collision'):
                        out.write("\nquitting... use '--force-file-collision' to continue.\n")
                        lpms.terminate()
        index += 1;
        instruct['index'] = index
        if not initpreter.InitializeInterpreter(package, instruct, ['remove'], remove=True).initialize():
            out.warn("an error occured during remove operation: %s/%s/%s-%s" % (package.repo, package.category, \
                    package.name, package.version))
        else:
            file_relationsdb.delete_item_by_pkgdata(package.category, package.name, package.version, commit=True)

class GetPackage:
    '''Selects a convenient package for advanced dependency resolving phases'''
    def __init__(self, package, installdb=False):
        self.package = package
        self.repo = None
        self.category = None
        self.name = None
        self.version = None
        self.slot = None
        self.conf = conf.LPMSConfig()
        self.custom_arch_request = {}
        self.locked_packages = []
        if not installdb:
            self.database = dbapi.RepositoryDB()
            arch_file = os.path.join(cst.user_dir, "arch")
            if os.path.isfile(arch_file):
                with open(arch_file) as lines:
                    for line in lines.readlines():
                        if not line.strip():
                            continue
                        self.custom_arch_request.update(utils.ParseArchFile(line.strip(), \
                                self.database).parse())

            lock_file = os.path.join(cst.user_dir, "lock")
            if os.path.isfile(lock_file):
                with open(lock_file) as lines:
                    for line in lines.readlines():
                        if not line.strip():
                            continue
                        self.locked_packages.extend(utils.ParseUserDefinedFile(line.strip(), \
                                self.database).parse())
        else:
            self.database = dbapi.InstallDB()

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
        
        packages = self.database.find_package(package_repo=self.repo, package_name=self.name, \
                package_category=self.category, package_version=self.version)
        
        if not packages:
            raise PackageNotFound(self.package)

        convenient_arches = utils.get_convenient_arches(self.conf.arch)

        try:
            the_package = utils.get_convenient_package(packages, self.locked_packages, \
                    self.custom_arch_request, convenient_arches, self.database, self.slot)
        except UnavailablePackage:
            for package in packages:
                out.error("%s/%s/%s-%s:%s is unavailable for your arch(%s)." % (package.repo, package.category, \
                        package.name, package.version, package.slot, self.conf.arch))
            lpms.terminate()
        except LockedPackage:
            out.error("these package(s) is/are locked by the system administrator:")
            for package in packages:
                out.error_notify("%s/%s/%s-%s:%s" % (package.repo, package.category, \
                        package.name, package.version, package.slot))
            lpms.terminate()

        if the_package is None:
            raise UnavailablePackage(self.package)
        return the_package

def resolve_dependencies(packages, instructions):
    '''
    Resolve dependencies using fixit object. This function
    prepares a full operation plan for the next stages
    '''
    out.normal("resolving dependencies")
    command_line_options = instructions.command_line_options \
            if instructions.command_line_options else []
    custom_options = instructions.custom_options \
            if instructions.custom_options else {}
    dependency_resolver = resolver.DependencyResolver(
            packages,
            command_line_options,
            custom_options,
            instructions.use_new_options
    )
    # To trigger resolver, call create_operation_plan
    return dependency_resolver.create_operation_plan()

def package_build(packages, instructions):
    '''Starting point of the build operation'''
    # Get package name or names if the user uses joker character
    """if instruct['like']:
        mydb = dbapi.RepositoryDB()
        for item in instruct['like']:
            query = mydb.database.cursor.execute("SELECT name FROM package where \
                    name LIKE ?", (item,))
            results = query.fetchall()
            if results:
                for result in results:
                    pkgnames.append(result[0])
        del mydb
    """
    # Resolve dependencies and trigger package builder
    try:
        # Prepare a plan using dependency resolver
        plan = resolve_dependencies([GetPackage(package).select() \
                for package in packages], instructions)
        # Run Build class to perform building task
        build.Build().run(plan, instructions)
    except PackageNotFound as package:
        out.error("%s count not found in the repository." % out.color(str(package), "red"))
    except ConflictError, DependencyError:
        # TODO: Parse this exception if debug mode is enabled.
        out.red("lpms was terminated due to some issues.\n")
    except UnavailablePackage as package:
        out.error("%s is unavailable for you." % out.color(str(package), "red"))
        out.error("this issue may be related with inconvenient arch or slotting.")
