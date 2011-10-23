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
from lpms.resolver.topological_sorting import topsort

class DependencyResolver(object):
    def __init__(self):
        self.modified_by_package = []
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

    def get_user_defined_files(self):
        for user_defined_file in cst.user_defined_files:
            if not os.access(user_defined_file, os.W_OK):
                continue
            with open(user_defined_file) as data:
                data = [line.strip() for line in data.readlines() \
                        if line != "#"]
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
        user_defined_options = None
        if opt:
            data = data.split(" ", 1)
            if len(data) > 1:
                data, user_defined_options = data
                user_defined_options = [atom.strip() for atom in \
                        user_defined_options.strip().split(" ")]
            else:
                data = data[0]
        affected = []
        slot = None
        slot_parsed = data.split(":")
        if len(slot_parsed) == 2:
            data, slot = slot_parsed

        def parse(pkgname):
            category, name = pkgname.split("/")
            name, version = utils.parse_pkgname(name)
            versions = []
            map(lambda x: versions.extend(x), \
                    self.repodb.get_version(name, pkg_category=category).values())
            return category, name, version, versions

        if ">=" == data[:2]:
            category, name, version, versions = parse(data[2:])

            for ver in versions:
                if utils.vercmp(ver, version) == 1:
                    affected.append(ver)
            affected.append(version)

            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, affected

        elif "<=" == data[:2]:
            category, name, version, versions = parse(data[2:])
            for ver in versions:
                if utils.vercmp(ver, version) == -1:
                    affected.append(ver)
            affected.append(version)
            
            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, affected

        elif "<" == data[:1]:
            category, name, version, versions = parse(data[1:])
            for ver in versions:
                if utils.vercmp(ver, version) == -1:
                    affected.append(ver)
                    
            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, affected

        elif ">" == data[:1]:
            category, name, version, versions = parse(data[1:])

            for ver in versions:
                if utils.vercmp(ver, version) == 1:
                    affected.append(ver)
                    
            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, affected

        elif "==" == data[:2]:
            pkgname = data[2:]
            category, name = pkgname.split("/")
            name, version = utils.parse_pkgname(name)
            
            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, version
        else:
            category, name = data.split("/")
            versions = []
            map(lambda x: versions.extend(x), \
                    self.repodb.get_version(name, pkg_category=category).values())
            
            if user_defined_options:
                return category, name, versions, user_defined_options

            return category, name, versions
        
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
            versions = []
            repo = db.find_pkg(name, pkg_category=category)
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
            return category, name, utils.best_version(versions)

        name, version = utils.parse_pkgname(pkgname)

        category, name = name.split("/")
        
        result = []
        repo_query = db.find_pkg(name, pkg_category=category)
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
                    #map(lambda v: versions.extend(v), repo[-1].values())

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
                        return category, name, rv

            if result:
                break
        if not result:
            out.error("unmet dependency: %s depends on %s" % (out.color(self.active, "red"), 
                out.color(incoming, "red")))
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
        #try:
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
        #except UnmetDependency as err:
        #    print err

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

    def collect(self, repo, category, name, version, use_new_opts, recursive=True):
        self.active = os.path.join(repo, category, name)+"-"+version
        dependencies = self.repodb.get_depends(repo, category, name, version)
        options = []

        if (repo, category, name, version) in self.operation_data:
            options.extend(self.operation_data[(repo, category, name, version)][-1])

        db_options = self.repodb.get_options(repo, category, name)
        inst_options  = self.instdb.get_options(repo, category, name)
        if not version in inst_options or use_new_opts or not self.instdb.get_version(name, \
                pkg_category=category):

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
                if fullname in self.plan:
                    plan_version, plan_options = self.plan[fullname]
                    if (lrepo, lcategory, lname, lversion) in self.operation_data:
                        for plan_option in plan_options:
                            # FIXME: This is a bit problematic.
                            self.modified_by_package.append(fullname)
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
            return packages, self.operation_data

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

                data = self.instdb.find_pkg(name, pkg_category = category)
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

            locked_packages = []
            if hasattr(self, "user_defined_lock"):
                for line in self.user_defined_lock:
                    locked_packages.extend([self.parse_user_defined_file(line)])

            for item in plan:
                plan_category = item[1]; plan_name = item[2]; plan_version = item[3]
                for locked_package in locked_packages:
                    if plan_category == locked_package[0] and \
                            plan_name == locked_package[1] and \
                            plan_version in locked_package[2]:
                                out.write("\n")
                                for v in locked_package[2]:
                                    out.warn("%s-%s" % ("/".join(item[:-1]), v))
                                out.write("\n")
                                if len(locked_package[2]) > 1:
                                    out.error("these packages were locked by system administrator.")
                                else:
                                    out.error("this package was locked by system administrator.")
                                lpms.terminate()
            plan.reverse()
            return plan, self.operation_data

        except CycleError as err:
            # FIXME: We need more powerful output.
            answer, num_parents, children = err
            for cycle in find_cycles(parent_children=children):
                out.brightred("Circular Dependency:\n")
                for cyc in cycle:
                    print(cyc)
                lpms.terminate()
                #out.write(cycle+"\n\n")
