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

import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import constants as cst

from lpms.db import dbapi
from lpms.exceptions import CycleError, UnmetDependency
from lpms.resolver.topological_sorting import topsort, find_cycles

class DependencyResolver(object):
    def __init__(self):
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()
        self.operation_data = {}
        self.valid_opts = []
        self.plan = {} 
        self.current_package = None
        self.special_opts = None
        self.package_query = []
        self.global_options = []
        self.config = conf.LPMSConfig()
        self.single_pkgs = []
        self.udo = {}
        self.get_user_defined_files()
        self.should_upgrade = []
        self.active = None
        self.invalid_elements = ['||']
        self.removal = {}
        self.modified_by_package = {}
        
        self.locked_packages = []
        if hasattr(self, "user_defined_lock"):
            for line in self.user_defined_lock:
                self.locked_packages.extend([self.parse_user_defined_file(line)])

    def get_user_defined_files(self):
        for user_defined_file in cst.user_defined_files:
            if not os.access(user_defined_file, os.W_OK):
                continue
            with open(user_defined_file) as data:
                data = [line.strip() for line in data.readlines() \
                        if line != "#" and line.strip()]
                if "".join(data) == "":
                    continue
            setattr(self, "user_defined_"+os.path.basename(user_defined_file), data)

    def parse_user_defined_options_file(self):
        if not hasattr(self, "user_defined_options"):
            return

        for user_defined_option in self.user_defined_options:
            category, name, versions, opts = self.parse_user_defined_file(user_defined_option, True)
            self.udo.update({(category, name):(versions, opts)})

    def parse_user_defined_file(self, data, opt=False):
        return utils.parse_user_defined_file(data, self.repodb, opt)

    def remove_locked_versions(self, category, name, versions):
        '''Removes locked versions from package bundle if it effected'''
        for locked_package in self.locked_packages:
            locked_category, locked_name, locked_version_data = locked_package
            if locked_category != category and locked_name != name:
                continue
            if isinstance(locked_version_data, list):
                result = []
                for version in versions:
                    if not version in locked_version_data:
                        result.append(version)
                return result
            elif isinstance(locked_version_data, basestring):
                if locked_version_data in versions:
                    versions.remove(locked_version_data)
                    return versions
        return versions

    def get_versions(self, versions, slot=None):
        vers = []
        data = versions.values()
        if slot is not None:
            if slot in versions:
                data = versions[slot]
        if not isinstance(data[0], list):
            return data
        map(lambda v: vers.extend(v), data)
        return vers

    def get_best_version(self, versions):
        return utils.best_version(versions)
    
    def parse_slot(self, category, name, db, slot):
        if slot is not None and slot.endswith("*"):
            slots = db.get_version(name, pkg_category = category)
            selected_slots = [item for item in slots if item.startswith(slot.replace("*", "."))]
            if not selected_slots:
                out.error("%s is invalid slot for %s/%s" % (slot, category, name))
                return False
            else:
                return self.get_best_version(selected_slots)
        return slot

    def package_select(self, incoming, instdb=False):
        db = self.repodb
        if instdb:
            db = self.instdb
        slot = None
        gte, lte, lt, gt, et = False, False, False, False, False
        slot_parsed = incoming.split(":")
        if len(slot_parsed) == 2:
            data, slot = slot_parsed
        elif len(slot_parsed) > 2:
            out.error("%s invalid dependency in %s.py" % (data, self.active))
            lpms.terminate()
        else:
            data = incoming

        if ">=" == data[:2]:
            gte = True
            pkgname = data[2:]
        elif "<=" == data[:2]:
            lte = True
            pkgname = data[2:]
        elif "<" == data[:1]:
            lt = True
            pkgname = data[1:]
        elif ">" == data[:1]:
            gt = True
            pkgname = data[1:]
        elif "==" == data[:2]:
            et = True
            pkgname = data[2:]
        else:
            category, name = data.split("/")
            slot = self.parse_slot(category, name, db, slot)
            versions = []
            repo = db.find_pkg(name, pkg_category=category, pkg_slot=slot)
            if not repo:
                if instdb:
                    return
                out.error("unmet dependency: %s depends on %s" % (out.color(self.active, \
                        "red"), out.color(incoming, "red")))
                lpms.terminate()

            # FIXME: ungodly hack, because of our fucking database
            if isinstance(repo, tuple):
                repo = [repo]
            
            for valid_repo in utils.valid_repos():
                for version_data in repo:
                    if valid_repo != version_data[0]:
                        continue
                    # FIXME: fix db.get_version and use it
                    if slot is None:
                        map(lambda ver: versions.extend(ver), version_data[-1].values())
                    else:
                        try:
                            versions = version_data[-1][slot]
                        except KeyError:
                            versions = self.get_versions(version_data[-1])
                        if not slot in self.instdb.get_version(name, repo_name=valid_repo, \
                                pkg_category=category):
                            self.should_upgrade.append((category, name))
                    if versions: break
                if versions: break
            
            versions = self.remove_locked_versions(category, name, versions)
            
            if not versions:
                out.warn("this package seems locked by the system administrator: %s/%s" % (category, name))
                lpms.terminate()

            return category, name, utils.best_version(versions)

        name, version = utils.parse_pkgname(pkgname)
        category, name = name.split("/")
        slot = self.parse_slot(category, name, db, slot)
        
        result = []
        repo_query = db.find_pkg(name, pkg_category=category, pkg_slot=slot)
        if not repo_query:
            if instdb:
                return
            out.error("unmet dependency: %s depends on %s" % (out.color(self.active, \
                        "red"), out.color(incoming, "red")))
            lpms.terminate()

        for valid_repo in utils.valid_repos():
            if isinstance(repo_query, list):
                for repo in repo_query:
                    if valid_repo == repo[0]:
                        break
            else:
                if valid_repo != repo_query[0]:
                    continue
                else:
                    repo = repo_query
            versions = []
            if slot is None:
                # FIXME: because of our database :'(
                try:
                    map(lambda v: versions.extend(v), repo[-1].values())
                except AttributeError:
                    # FIXME: What the fuck?
                    print(data)
            else:
                if slot in repo[-1]:
                    versions = repo[-1][slot]
                else:
                    continue

            installed_versions = self.instdb.get_version(name, pkg_category=category)

            if installed_versions:
                dec = utils.vercmp(version, self.get_best_version(self.get_versions(installed_versions, slot)))
                
                if lt:
                    if dec != 1 and not (category, name) in self.should_upgrade:
                        self.should_upgrade.append((category, name))
                elif gte:
                    if dec == 1 and not (category, name) in self.should_upgrade:
                        self.should_upgrade.append((category, name))
                elif lte:
                    if dec == -1 and not (category, name) in self.should_upgrade:
                        self.should_upgrade.append((category, name))
                elif gt:
                    if dec != -1 and not (category, name) in self.should_upgrade:
                        self.should_upgrade.append((category, name))
                elif et:
                    if dec != 0 and not (category, name) in self.should_upgrade:
                        self.should_upgrade.append((category, name))

            for rv in versions:
                vercmp = utils.vercmp(rv, version) 
                if lt:
                    if vercmp == -1:
                        result.append(rv)
                elif gt:
                    if vercmp == 1 or vercmp == 0:
                        result.append(rv)
                elif lte:
                    if vercmp == -1 or vercmp == 0:
                        result.append(rv)
                elif gte:
                    version = version.strip()
                    if utils.vercmp(rv, version) == 1 or utils.vercmp(rv, version) == 0:
                        result.append(rv)
                elif et:
                    if vercmp == 0:
                        result = self.remove_locked_versions(category, name, [rv])
                        if not result:
                            out.warn("this package seems locked by the system administrator: %s/%s" % (category, name))
                            lpms.terminate()
                        return category, name, rv

            if result:
                break
        if not result:
            out.error("unmet dependency: %s depends on %s" % (out.color(self.active, "red"), 
                out.color(incoming, "red")))
            lpms.terminate()

        result = self.remove_locked_versions(category, name, result)
        if not result:
            out.warn("this package seems locked by the system administrator: %s/%s" % (category, name))
            lpms.terminate()

        return category, name, utils.best_version(result)

    def opt_parser(self, data):
        data = list(data)
        if "[" in data:
            first_index = data.index("[")
            try:
                end_index = data.index("]")
            except ValueError:
                out.error("%s -- ']' not found in package name" % "".join(data))
                lpms.terminate()

            opts = []
            opt = "".join(data[first_index+1:end_index])
            pkgname = "".join(data[:first_index])
            for atomic_opt in opt.split(","):
                atomic_opt = atomic_opt.strip()
                if atomic_opt.startswith("-"):
                    if not pkgname in self.removal:
                        self.removal.update({pkgname: [atomic_opt[1:]]})
                    else:
                        if not atomic_opt[1:] in self.removal[pkgname]:
                            self.removal[pkgname].append(atomic_opt[1:])
                    if not atomic_opt[1:] in opts:
                        opts.append(atomic_opt[1:])
                    continue
                if not atomic_opt in opts:
                    opts.append(atomic_opt)

            return pkgname, utils.internal_opts(opts, self.global_options)

        return "".join(data)

    def fix_dynamic_deps(self, data, options):
        depends = []; opts = []; no = []
        for opt in options:
            prev_indent_level = 0
            if opt in data:
                deps = data[opt]
                for dep in deps:
                    if isinstance(dep, str):
                        if dep == "||":
                            continue
                        depends.append(dep)
                    elif isinstance(dep, tuple):
                        subopt, subdep = dep
                        if subopt.count("\t") == 1:
                            if subopt.strip() in options:
                                prev_indent_level = 1
                                depends.extend(subdep)
                                opts.append(subopt.strip())
                        elif subopt.count("\t") - 1 == prev_indent_level:
                            if subopt.strip() in options:
                                prev_indent_level = subopt.count("\t")
                                depends.extend(subdep)
                                opts.append(subopt.strip())
        for line in data:
            if line in options:
                continue
            else:
                if "||" in data[line]:
                    depends.extend(data[line][data[line].index("||")+1:])

            for opt in data[line]:
                if isinstance(opt, tuple):
                    no.append(opt[0].strip())

        return depends, opts, no 

    def parse_package_name(self, data, instdb=False):
        try:
            name, opts = self.opt_parser(data)
        except ValueError:
            result = self.package_select(data, instdb)
            if not result:
                return
            return result, []
        else:
            result = self.package_select(name, instdb)
            if not result:
                return
            return result, opts

    def get_repo(self, data):
        if len(data) == 2:
            category, name = data
            return self.repodb.get_repo(category, name)
        elif len(data) == 3:
            category, name, version = data
            return self.repodb.get_repo(category, name, version)
        elif len(data) == 4:
            category, name, version = data[:-1]
            return self.repodb.get_repo(category, name, version)

    def get_valid_options(self, options, valid_options):
        result = []
        if isinstance(valid_options, basestring):
            valid_options = [vo.strip() for vo in \
                    valid_options.split(" ")]
        for option in options:
            if option in valid_options:
                result.append(option)
        return result

    def collect(self, repo, category, name, version, use_new_opts, recursive=True):
        self.active = os.path.join(repo, category, name)+"-"+version
        dependencies = self.repodb.get_depends(repo, category, name, version)
        options = []

        if (repo, category, name, version) in self.operation_data:
            options.extend(self.operation_data[(repo, category, name, version)][-1])

        db_options = self.repodb.get_options(repo, category, name)
        inst_options  = self.instdb.get_options(repo, category, name)
        if not version in inst_options or use_new_opts or not self.instdb.get_version(name, \
                pkg_category=category) or (repo, category, name, version) in self.modified_by_package:

            if (repo, category, name, version) in self.modified_by_package:
                for item in self.modified_by_package[(repo, category, name, version)]:
                    for i in item[-1]:
                        if not i in options:
                            options.append(i)

            for go in self.global_options:
                if not db_options:
                    out.error("%s/%s-%s not found." % (category, name, version))
                    lpms.terminate()

                if version in db_options and db_options[version]:
                    db_option = db_options[version].split(" ")
                    if go in db_option and not go in options:
                        options.append(go)

            if self.udo and (category, name) in self.udo and version in self.udo[(category, name)][0]:
                for opt in self.udo[(category, name)][1]:
                    if utils.opt(opt, self.udo[(category, name)][1], self.global_options):
                        if not opt in options:
                            options.append(opt)
                    else:
                        if opt[1:] in options:
                            options.remove(opt[1:])

            if self.special_opts and name in self.special_opts:
                for opt in self.special_opts[name]:
                    if utils.opt(opt, self.special_opts[name], self.global_options):
                        if not opt in options:
                            options.append(opt)
                    else:
                        if opt[1:] in options:
                            options.remove(opt[1:])
                        
        else:
            # save existing options
            if version in inst_options:
                for iopt in inst_options[version].split(" "):
                    if iopt in self.global_options and not iopt in options:
                        options.append(iopt)

        if category+"/"+name in self.removal:
            for key in self.removal[category+"/"+name]:
                options.remove(key)

        # FIXME: WHAT THE FUCK IS THAT??
        if not dependencies:
            print repo, category, name, version, dependencies
            print self.repodb.get_repo(category, name, version)
            lpms.terminate()

        local_plan = {"build":[], "runtime": [], "postmerge": [], "conflict": []}

        plan = {}

        def parse_depend_line(string):
            parsed = []
            data = string.split(" ")
            for i in data:
                listed = list(i)
                if not "[" in listed and not "]" in listed:
                    if "/" in listed:
                        parsed.append(i)
                elif "[" in listed:
                    if "]" in listed:
                        parsed.append(i)
                    else:
                        index = data.index(i) + 1
                        while True:
                            if not "]" in data[index]:
                                if "/" in listed:
                                    i += " "+ data[index].strip()
                                index += 1
                            else:
                                i += " "+ data[index]
                                parsed.append(i)
                                break
            return parsed

        for key in ('build', 'runtime', 'conflict', 'postmerge'):
            dynamic_deps = [dep for dep in dependencies[key] if isinstance(dep, dict)]

            if dynamic_deps:
                dyn_packages, dyn_options, no  = self.fix_dynamic_deps(dynamic_deps[0], options)
                for d in no:
                    if d in options: 
                        options.remove(d)
                for dyn_dep in dyn_packages:
                    if dyn_dep in self.invalid_elements:
                        continue
                    if key == "conflict":
                        dyn_package_data = self.parse_package_name(dyn_dep, instdb=True)
                        if not dyn_package_data:
                            continue
                    else:
                        dyn_package_data = self.parse_package_name(dyn_dep)
                    dyn_dep_repo = self.get_repo(dyn_package_data[0])
                    (dcategory, dname, dversion), dopt = dyn_package_data
                    if key == "conflict":
                        local_plan[key].append([dyn_dep_repo, dcategory, dname, dversion])
                        continue
                    if dopt and use_new_opts:
                        if (stc_dep_repo, scategory, sname, sversion) in self.modified_by_package:
                            self.modified_by_package.update({(dyn_dep_repo, dcategory, dname, dversion): [(repo, category, name, version, dopt)]})
                        else:
                            self.modified_by_package[(dyn_dep_repo, dcategory, dname, dversion)] = [(repo, category, name, version, dopt)]
                    repo_options = self.repodb.get_options(dyn_dep_repo, dcategory, dname)
                    if dversion in repo_options:
                        dopt = self.get_valid_options(dopt, repo_options[dversion])
                    else: dopt = []
                    local_plan[key].append([dyn_dep_repo, dcategory, dname, dversion, dopt])
                     
            static_deps = " ".join([dep for dep in dependencies[key] if isinstance(dep, str)])

            if static_deps:
                for stc_dep in parse_depend_line(static_deps):
                    if stc_dep in self.invalid_elements:
                        continue
                    if key == "conflict":
                        stc_package_data = self.parse_package_name(stc_dep, instdb=True)
                        if not stc_package_data:
                            continue
                    else:
                        stc_package_data = self.parse_package_name(stc_dep)
                    stc_dep_repo = self.get_repo(stc_package_data[0])
                    (scategory, sname, sversion), sopt = stc_package_data
                    if key == "conflict":
                        local_plan[key].append([stc_dep_repo, scategory, sname, sversion])
                        continue
                    if sopt:
                        if (stc_dep_repo, scategory, sname, sversion) in self.modified_by_package:
                            self.modified_by_package.update({(stc_dep_repo, scategory, sname, sversion): [(repo, category, name, version, sopt)]})
                        else:
                            self.modified_by_package[(stc_dep_repo, scategory, sname, sversion)] = [(repo, category, name, version, sopt)]
                    repo_options = self.repodb.get_options(stc_dep_repo, scategory, sname)
                    if sversion in repo_options:
                        sopt = self.get_valid_options(sopt, repo_options[sversion])
                    else: sopt = []
                    local_plan[key].append([stc_dep_repo, scategory, sname, sversion, sopt])

        self.operation_data.update({(repo, category, name, version): [local_plan, options]})
        
        #FIXME: postmerge dependency?
        if not local_plan['build'] and not local_plan['runtime']:
            if not (repo, category, name, version) in self.single_pkgs:
                self.single_pkgs.append((repo, category, name, version))

        for key in ('build', 'runtime', 'postmerge'):
            if not local_plan[key]:
                continue
            for local in local_plan[key]:
                lrepo, lcategory, lname, lversion, lopt = local
                fullname = (lrepo, lcategory, lname, lversion)
                if (repo, category, name, version) in self.single_pkgs:
                    self.single_pkgs.remove((repo, category, name, version))
                if key == "postmerge":
                    self.package_query.append((fullname, (repo, category, name, version)))
                    self.collect(lrepo, lcategory, lname, lversion, self.use_new_opts)
                else:
                    self.package_query.append(((repo, category, name, version), fullname))
                
                if (lrepo, lcategory, lname, lversion) in self.modified_by_package:
                    self.collect(lrepo, lcategory, lname, lversion, self.use_new_opts)
 
                if fullname in self.plan:
                    plan_version, plan_options = self.plan[fullname]
                    if (lrepo, lcategory, lname, lversion) in self.operation_data:
                        for plan_option in plan_options:
                            # FIXME: This is a bit problematic.
                            if not plan_option in self.operation_data[fullname][-1]:
                                self.operation_data[fullname][-1].append(plan_option)
                                self.collect(lrepo, lcategory, lname, lversion, self.use_new_opts)
                    continue

                self.plan.update({fullname: (lversion, lopt)})
                if recursive:
                    self.collect(lrepo, lcategory, lname, lversion, self.use_new_opts)

    def resolve_depends(self, packages, cmd_options, use_new_opts, specials=None):
        self.special_opts = specials
        self.parse_user_defined_options_file()
        setattr(self, "use_new_opts", use_new_opts)

        for options in (self.config.options.split(" "), cmd_options):
            for opt in options:
                if utils.opt(opt, cmd_options, self.config.options.split(" ")):
                    if not opt in self.global_options:
                        self.global_options.append(opt)
                else:
                    if opt in self.global_options:
                        self.global_options.remove(opt)

        primary = []
        packages = list(set(packages))
        for pkg in packages:
            self.current_package = pkg
            repo, category, name, version = pkg
            self.collect(repo, category, name, version, True, recursive=False)
      
        primary.extend(self.package_query)
        self.package_query = []

        for i in primary:
            repo, category, name, version = i[1]
            self.collect(repo, category, name, version, True)

        if not self.package_query and primary:
            self.package_query.extend(primary)

        if not self.package_query or lpms.getopt("--ignore-depends"):
            return packages, self.operation_data, self.modified_by_package

        plan = []

        try:
            for package in packages:
                if not package in [data[0] for data in self.package_query]:
                     plan.append(package)

            processed = topsort(self.package_query)
            for single_pkg in self.single_pkgs:
                if not single_pkg in processed:
                    processed.append(single_pkg)

            for pkg in processed:
                repo, category, name, version = pkg
                if (repo, category, name, version) in packages:
                    if not pkg in plan:
                        plan.append(pkg)
                        continue 

                data = self.instdb.find_pkg(name, pkg_category=category, repo_name=repo)
                if data:
                    # the package is installed
                    irepo = self.instdb.get_repo(category, name, version)
                    db_options = self.instdb.get_options(irepo, category, name)
                    if version in db_options:
                        for opt in self.operation_data[pkg][-1]:
                            if not opt in db_options[version].split(" ") and not pkg in plan:
                                if self.use_new_opts or pkg in self.modified_by_package:
                                    if not pkg in plan:
                                        plan.append(pkg)
                            if category+"/"+name in self.removal:
                                if not pkg in plan:
                                    plan.append(pkg)
                    else:
                        # new version
                        if lpms.getopt("-U") or lpms.getopt("--upgrade") or lpms.getopt("--force-upgrade") \
                                or (category, name) in self.should_upgrade:
                            if not pkg in plan:
                                plan.append(pkg)
                        else: 
                            if not pkg in packages and pkg in self.operation_data: 
                                del self.operation_data[pkg] 
                else:
                    # fresh install
                    if not pkg in plan:
                        plan.append(pkg)

            if lpms.getopt("--ignore-reinstall"):
                # ignore installed packages
                # this is useful for package sets.
                out.normal("cleaning out installed packages...")
                new_plan = []; rmplan = []
                for item in plan:
                    installed_versions = []
                    repo, category, name, version = item
                    result = self.instdb.find_pkg(name, pkg_category=category, repo_name=repo)
                    if result:
                        map(lambda slot: installed_versions.extend(result[-1][slot]), result[-1])
                        if not version in installed_versions:
                            new_plan.append(item)
                        else:
                            for package in packages:
                                if item == package: rmplan.append(item)
                    else:
                        new_plan.append(item)
                
                # use the new plan if it is not empty
                if new_plan: plan = new_plan

                # remove the packages from directly from command line
                for item in rmplan:
                    if item in plan: plan.remove(item)

            if not plan: out.write("no package is going to be installed.\n"); lpms.terminate()

            plan.reverse()
            return plan, self.operation_data, self.modified_by_package

        except CycleError as err:
            # FIXME: We need more powerful output.
            answer, num_parents, children = err
            for cycle in find_cycles(parent_children=children):
                out.brightred("Circular Dependency:\n")
                for cyc in cycle:
                    print(cyc)
                lpms.terminate()
                #out.write(cycle+"\n\n")
