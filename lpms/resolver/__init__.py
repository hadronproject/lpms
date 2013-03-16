# Copyright 2009 - 2012 Burak Sezer <purak@hadronproject.org>
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

# Standard Libraries
import re
import os

# lpms Libraries
import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import constants as cst

from lpms.db import api
from lpms.types import LCollect
from lpms.types import PackageItem
from lpms.resolver import topological_sorting

# Get lpms' exceptions
from lpms.exceptions import ConflictError
from lpms.exceptions import LockedPackage
from lpms.exceptions import DependencyError
from lpms.exceptions import ConditionConflict
from lpms.exceptions import UnavailablePackage

class DependencyResolver(object):
    '''Dependency resolving engine for lpms'''
    def __init__(self, packages, cmd_options=[], \
            custom_options={}, use_new_options=False):
        self.packages = packages
        self.cmd_options = cmd_options
        self.custom_options = custom_options
        self.use_new_options = use_new_options
        self.conflicts = {}
        self.current_package = None
        self.parent_package = None
        self.conf = conf.LPMSConfig()
        self.instdb = api.InstallDB()
        self.repodb = api.RepositoryDB()
        self.conditional_packages = {}
        self.processed = {}
        self.package_heap = {}
        self.control_chars = ["||"]
        self.inline_options = {}
        self.inline_option_targets = {}
        self.package_dependencies = {}
        self.postmerge_dependencies = set()
        self.package_options = {}
        self.repository_cache = {}
        self.user_defined_options = {}
        self.package_query = []
        self.locked_packages = []
        self.global_options = set()
        self.forbidden_options = set()
        self.dependency_keywords = (
                'static_depends_build', 
                'static_depends_runtime', 
                'static_depends_conflict', 
                'static_depends_postmerge',
                'optional_depends_build',
                'optional_depends_runtime',
                'optional_depends_conflict',
                'optional_depends_postmerge'
        )
        for option in self.conf.options.split(" "):
            if option.strip():
                if not option.startswith("-"):
                    self.global_options.add(option)
                else:
                    self.forbidden_options.add(option[1:])
        self.get_user_defined_files()
        self.parse_user_defined_options_file()
        if hasattr(self, "user_defined_lock_file"):
            for locked_item in self.user_defined_lock_file:
                self.locked_packages.extend(self.parse_user_defined_file(locked_item))

        self.custom_arch_requests = {}
        if hasattr(self, "user_defined_arch_file"):
            for arch_item in self.user_defined_arch_file:
                self.custom_arch_requests.update(utils.ParseArchFile(arch_item, \
                        self.repodb).parse())

    def get_user_defined_files(self):
        for user_defined_file in cst.user_defined_files:
            if not os.access(user_defined_file, os.W_OK):
                continue
            with open(user_defined_file) as data:
                data = [line.strip() for line in data.readlines() \
                        if line != "#" and line.strip()]
                if "".join(data) == "":
                    continue
            setattr(self, "user_defined_"+os.path.basename(user_defined_file)+"_file", data)

    def parse_user_defined_options_file(self):
        if not hasattr(self, "user_defined_options_file"): return
        for item in self.user_defined_options_file:
            self.user_defined_options.update(self.parse_user_defined_file(item, True))

    def parse_user_defined_file(self, data, options=False):
        return utils.ParseUserDefinedFile(data, self.repodb, options).parse()

    def parse_inline_options(self, name):
        result = []
        for inline in re.findall("\[(.*?)\]", name):
            result.extend([item for item in inline.split(" ") if item.strip()])
        return result

    def get_convenient_slot(self, packages, slot):
        if slot is not None and slot.endswith("*"):
            slots = [ package.slot for package in packages ]
            selected_slots = [ item for item in slots if item.startswith(slot.replace("*", ".")) ]
            if not selected_slots:
                out.error("%s is invalid slot for %s/%s" % (slot, category, name))
                return False
            else:
                return utils.best_version(selected_slots)
        return slot

    def get_convenient_package(self, package, instdb=False):
        def inline_options_management(inline_options):
            # TODO: inline_options variable must be a set
            # Check inline options, if an option is not available for the package, warn the user
            for inline_option in inline_options:
                if not inline_option in package.options:
                    out.warn("%s option is not available for %s/%s/%s-%s. So that the option is removing..." % (
                        inline_option,
                        package.repo,
                        package.category,
                        package.name,
                        package.version
                    ))
                    inline_options.remove(inline_option)

            if inline_options:
                target = self.current_package.id if self.current_package is not \
                        None else self.parent_package.id
                my_package = package.category+"/"+package.name+"/"+package.slot
                if target in self.inline_option_targets:
                    if my_package in self.inline_option_targets[target]:
                        for option in inline_options:
                            self.inline_option_targets[target][my_package].add(option)
                    else:
                        self.inline_option_targets[target][my_package] = set(inline_options)
                else:
                    self.inline_option_targets[target] = {my_package: set(inline_options)}
                
                if package.id in self.inline_options:
                    if not package.id in self.package_options:
                        self.package_options[package.id] = set()
                    for option in inline_options:
                        if not option in self.inline_options[package.id]:
                            self.inline_options[package.id].append(option)
                            if package.id in self.package_options:
                                self.package_options[package.id].add(option)
                else:
                    self.inline_options[package.id] = inline_options
                    if package.id in self.package_options:
                        for inline_option in inline_options:
                            self.package_options[package.id].add(inline_option)
                    else:
                        self.package_options[package.id] = set(inline_options)

        convenient_arches = utils.get_convenient_arches(self.conf.arch)
        current_package = self.parent_package if self.parent_package is not \
                None else self.current_package
        result = LCollect()
        database = self.repodb if instdb is False else self.instdb
        slot = None
        gte, lte, lt, gt, et = False, False, False, False, False
        slot_parsed = package.split(":")

        if len(slot_parsed) == 2:
            data, slot = slot_parsed
        elif len(slot_parsed) > 2:
            out.error("%s invalid dependency in %s.py" % (data, self.current_package))
            # Use and exception
            raise DependencyError
        else:
            data = package

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
            inline_options = self.parse_inline_options(name)
            if inline_options:
                name = name[:name.index("[")]
            if (category, name) in self.repository_cache:
                results = self.repository_cache[(category, name)]
            else:
                results = database.find_package(package_name=name, package_category=category)
                self.repository_cache[(category, name)] = results
            slot = self.get_convenient_slot(results, slot)
            if not results:
                if instdb:
                    return
                current_package = current_package.repo+"/"+current_package.category+\
                        "/"+current_package.name+"-"+current_package.version+":"+current_package.slot
                out.error("unmet dependency: %s depends on %s" % (out.color(current_package, \
                        "red"), out.color(package, "red")))
                raise DependencyError
            try:
                package = utils.get_convenient_package(
                        results, 
                        self.locked_packages,
                        self.custom_arch_requests, 
                        convenient_arches, 
                        self.instdb, 
                        slot
                )
            except UnavailablePackage:
                for result in results:
                    out.error("%s/%s/%s-%s:%s {%s} is unavailable for your arch(%s)." % (result.repo, result.category, \
                            result.name, result.version, result.slot, result.arch, self.conf.arch))
                out.write("\n")
                out.write("%s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), current_package.repo, \
                        current_package.category, current_package.name, current_package.version, \
                        current_package.slot, current_package.arch))
                out.write(" %s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), current_package.repo, \
                        current_package.category, current_package.name, current_package.version, \
                        current_package.slot, current_package.arch))
                raise DependencyError
            except LockedPackage:
                out.error("these package(s) is/are locked by the system administrator:")
                for result in results:
                    out.error_notify("%s/%s/%s-%s:%s {%s}" % (result.repo, result.category, \
                            result.name, result.version, result.slot, result.arch))
                out.write("\n")
                out.write("%s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), current_package.repo, \
                        current_package.category, current_package.name, current_package.version, \
                        current_package.slot, current_package.arch))
                out.write(" %s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), current_package.repo, \
                        current_package.category, current_package.name, current_package.version, \
                        current_package.slot, current_package.arch))
                raise DependencyError

            # Set some variables to manage inline options
            inline_options_management(inline_options)

            return package

        category, name = pkgname.split("/")
        inline_options = self.parse_inline_options(name)
        if inline_options:
            name = name[:name.index("[")]
        name, version = utils.parse_pkgname(name)
        if (category, name) in self.repository_cache:
            results = self.repository_cache[(category, name)]
        else:
            results = database.find_package(package_name=name, package_category=category)
            self.repository_cache[(category, name)] = results
        slot = self.get_convenient_slot(results, slot)
        packages = []
        decision_point = {}
        owner_package = current_package.repo+"/"+current_package.category+\
                "/"+current_package.name+"-"+current_package.version
        if gte:
            decision_point = {"type": ">=", "version": version, \
                    "owner_package": owner_package, "owner_id": current_package.id}
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == 1 or comparison == 0:
                    packages.append(result)
        elif lte:
            decision_point = {"type": "<=", "version": version, \
                    "owner_package": owner_package, "owner_id": current_package.id}
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == -1 or comparison == 0:
                    packages.append(result)
        elif lt:
            decision_point = {"type": "<", "version": version, \
                    "owner_package": owner_package, "owner_id": current_package.id}
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == -1:
                    packages.append(result)
        elif gt:
            decision_point = {"type": ">", "version": version, \
                    "owner_package": owner_package, "owner_id": current_package.id}
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == 1:
                    packages.append(result)
        elif et:
            decision_point = {"type": "==", "version": version, \
                    "owner_package": owner_package, "owner_id": current_package.id}
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == 0:
                    packages.append(result)

        if not packages:
            out.error("unmet dependency: %s/%s/%s-%s:%s {%s} depends on %s" % \
                    (current_package.repo, \
                    current_package.category, \
                    current_package.name, \
                    current_package.version, \
                    current_package.slot, \
                    current_package.arch, \
                    out.color(package, "red")))
            raise DependencyError

        try:
            package = utils.get_convenient_package(
                    results if not packages else packages,
                    self.locked_packages,
                    self.custom_arch_requests,
                    convenient_arches,
                    self.instdb,
                    slot
                    )
        except UnavailablePackage:
            for result in results:
                out.error("%s/%s/%s-%s:%s {%s}is unavailable for your arch(%s)." % (result.repo, result.category, \
                        result.name, result.version, result.slot, result.arch, self.conf.arch))
            out.write("\n")
            out.write("%s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), current_package.repo, \
                    current_package.category, current_package.name, current_package.version, \
                    current_package.slot, current_package.arch))
            out.write(" %s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), current_package.repo, \
                    current_package.category, current_package.name, current_package.version, \
                    current_package.slot, current_package.arch))
            raise DependencyError
        except LockedPackage:
            out.error("these package(s) is/are locked by the system administrator:")
            for result in results:
                out.error_notify("%s/%s/%s-%s:%s {%s}" % (result.repo, result.category, \
                        result.name, result.version, result.slot, result.arch))
            out.write("\n")
            out.write("%s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), current_package.repo, \
                    current_package.category, current_package.name, current_package.version, \
                    current_package.slot, current_package.arch))
            out.write(" %s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), current_package.repo, \
                    current_package.category, current_package.name, current_package.version, \
                    current_package.slot, current_package.arch))
            raise DependencyError

        # Set some variables to manage inline options
        inline_options_management(inline_options)

        if package.id in self.conditional_packages:
            self.conditional_packages[package.id].append(decision_point)
        else:
            self.conditional_packages[package.id] = [decision_point]

        return package

    def parse_suboptional_dependencies(self, bundle, options, instdb=False):
        added = []
        result = []
        for parent in bundle:
            pass_parent = False
            if "&&" in parent:
                for and_option in [and_option.strip() for and_option in parent.split("&&")]:
                    if not and_option in options:
                        pass_parent = True
                        break
                if pass_parent: 
                    if "||" in bundle[parent]:
                        for package in bundle[parent][bundle[parent].index("||")+1:]:
                            result.append(self.get_convenient_package(package, instdb))
                    continue
            else:
                if not parent in options: 
                    if "||" in bundle[parent]:
                        for package in bundle[parent][bundle[parent].index("||")+1:]:
                            result.append(self.get_convenient_package(package, instdb))
                    continue

            for child in bundle[parent]:
                if isinstance(child, tuple):
                    pass_child = False
                    raw_option, packages = child
                    if "&&" in raw_option:
                        for and_option in [and_option.strip() for and_option in \
                                raw_option.split("&&")[1:]]:
                            if not and_option in options: 
                                pass_child = True
                                break
                    if pass_child:
                        if "||" in packages:
                            for package in packages[packages.index("||")+1:]:
                                result.append(self.get_convenient_package(package, instdb)) 
                        continue
                    raw_option = raw_option.split("&&")[0].rstrip()
                    if raw_option.count("\t") != 1:
                        previous_item = bundle[parent][bundle[parent].index(child) - 1]
                        if isinstance(previous_item, tuple):
                            if not previous_item[0] in added:
                                continue
                    previous_child = raw_option.replace("\t", "")
                    if previous_child in options:
                        added.append(raw_option)
                        if "||" in packages:
                            for package in packages[:packages.index("||")]:
                                result.append(self.get_convenient_package(package, instdb))
                        else:
                            for package in packages:
                                result.append(self.get_convenient_package(package, instdb))
                    else:
                        if "||" in packages:
                            for package in packages[packages.index("||")+1:]:
                                result.append(self.get_convenient_package(package, instdb))
                else:
                    if child in self.control_chars:
                        continue
                    result.append(self.get_convenient_package(child, instdb))
        return result
    
    def keep_dependency_information(self, package_id, keyword, dependency):
        bundle = (dependency.category, dependency.name, \
                dependency.version, dependency.slot, dependency.arch)
        if not package_id in self.package_dependencies:
            self.package_dependencies[package_id] = { keyword: set([bundle]) }
        else:
            if keyword in self.package_dependencies[package_id]:
                self.package_dependencies[package_id][keyword].add(bundle)
            else:
                self.package_dependencies[package_id].update({ keyword: set([bundle]) })

    def collect_dependencies(self, package):
        dependencies = []
        current_options = set()
        already_added = {}

        def process_option(option):
            if option.startswith("-"):
                if option[1:] in options:
                    options.remove(option[1:])
            else:
                options.add(option)

        # Set the global options(from /etc/lpms/build.conf) for the package
        options = self.global_options
        if package.id in self.user_defined_options:
            for option in self.user_defined_options[package.id]:
                process_option(option)
        
        # Set the options that given via command line
        for cmd_option in self.cmd_options:
            if not cmd_option in options:
                process_option(cmd_option)

        # Set the options that given via command line with package name and version
        for keyword in self.custom_options:
            name, version = utils.parse_pkgname(keyword)
            if package.name == name:
                if version is None:
                    for custom_option in self.custom_options[keyword]:
                        process_option(custom_option)
                else:
                    if version == package.version:
                        for custom_option in self.custom_options[keyword]:
                            process_option(custom_option)

        # Set inline options. These options are declared in the specs like the following:
        # sys-fs/udev[gudev] 
        if package.id in self.inline_options:
            for option in self.inline_options[package.id]:
                process_option(option)

        previous_targets = self.instdb.find_inline_options(target=package.category+"/"\
                +package.name+"/"+package.slot)
        for previous_target in previous_targets:
            if self.instdb.find_package(package_id=previous_target.package_id):
                for option in previous_target.options:
                    process_option(option)

        # Set the options that used by the package
        if package.options:
            for option in options:
                if option in package.options:
                    if not package.id in self.package_options:
                        self.package_options[package.id] = set([option])
                        continue
                    self.package_options[package.id].add(option)

        def check_conflicts(dependency):
            for item in self.conflicts:
                if dependency.pk in self.conflicts[item]:
                    out.error("%s/%s/%s-%s has a conflict with %s" % (
                        self.package_heap[item].repo,
                        self.package_heap[item].category,
                        self.package_heap[item].name,
                        self.package_heap[item].version,
                        dependency.pk)
                    )
                    out.error("on the other hand, %s/%s/%s-%s wants to install with %s" % (
                        package.repo,
                        package.category,
                        package.name,
                        package.version,
                        dependency.pk
                    ))
                    raise ConflictError

        #Firstly, check static dependencies
        for keyword in self.dependency_keywords:
            if keyword.startswith("static"):
                for dependency in getattr(package, keyword):
                    if keyword.endswith("conflict"):
                        dependency = self.get_convenient_package(dependency, instdb=True)
                        # The package is not installed.
                        if dependency is None:
                            continue
                        self.keep_dependency_information(package.id, keyword, dependency)
                        self.package_heap[dependency.id] = dependency
                        if package.id in self.conflicts:
                            self.conflicts[package.id].add(dependency.pk)
                        else:
                            self.conflicts[package.id] = set([dependency.pk])
                        continue
                    proper_dependency = self.get_convenient_package(dependency)
                    # TODO: This is a temporary workaround
                    # We must implement more proper exception handling mech. and give more informative messages to users.
                    if proper_dependency is None:
                        raise UnavailablePackage(dependency)
                    if proper_dependency.id in already_added and \
                            already_added[proper_dependency.id] == options:
                                continue
                    already_added[proper_dependency.id] = options
                    self.keep_dependency_information(package.id, keyword, proper_dependency)
                    check_conflicts(proper_dependency)
                    dependencies.append(proper_dependency)
                    if keyword.endswith("postmerge"):
                        self.postmerge_dependencies.add((proper_dependency.id, package.id))

        # Secondly, Check optional dependencies
        for keyword in self.dependency_keywords:
            if keyword.startswith("optional"):
                for dependency_bundle in getattr(package, keyword):
                    instdb = True if keyword.endswith("conflict") else False
                    optional_dependencies = self.parse_suboptional_dependencies(dependency_bundle, options, instdb)
                    for dependency in optional_dependencies:
                        if keyword.endswith("conflict"):
                            if dependency is None:
                                continue
                            self.keep_dependency_information(package.id, keyword, dependency)
                            self.package_heap[dependency.id] = dependency
                            if package.id in self.conflicts:
                                self.conflicts[package.id].add(dependency.pk)
                            else:
                                self.conflicts[package.id] = set([dependency.pk])
                            continue
                        if dependency.id in already_added and \
                                already_added[dependency.id] == options:
                                    continue
                        already_added[dependency.id] = options
                        if current_options:
                            if package.id in self.package_options:
                                for option in current_options:
                                    self.package_options[package.id].add(option)
                            else:
                                self.package_options[package.id] = current_options
                        self.keep_dependency_information(package.id, keyword, dependency)
                        check_conflicts(dependency)
                        dependencies.append(dependency)
                        if keyword.endswith("postmerge"):
                            self.postmerge_dependencies.add((dependency.id, package.id))
        return dependencies

    def handle_condition_conflict(self, decision_point, final_plan, primary_key, \
            condition_set, result_set):
        conflict_condition, decision_condition = condition_set
        result = final_plan.check_pk(primary_key)
        if isinstance(result, int):
            conflict_id = final_plan[result].id
            if conflict_id not in self.conditional_packages:
                final_plan[result] = package
                return False
            for conflict_point in self.conditional_packages[conflict_id]:
                if conflict_point["type"].startswith(conflict_condition):
                    if decision_point["type"].startswith(decision_condition):
                        compare_result = utils.vercmp(decision_point["version"], \
                                conflict_point["version"])
                        if compare_result in result_set:
                            self.conflict_point = conflict_point
                            raise ConditionConflict(conflict_point)

    def create_operation_plan(self):
        '''Resolve dependencies and prepares a convenient operation plan'''
        single_packages = PackageItem()
        for package in self.packages:
            self.parent_package = package
            self.current_package = None
            self.package_heap[package.id] = package
            dependencies = []
            package_dependencies = self.collect_dependencies(package)
            if not package_dependencies:
                single_packages.add(package)
                continue
            # Create a list that consists of parent and child items
            for dependency in package_dependencies:
                dependency.parent = package.category+"/"+package.name+"/"+package.slot
                dependencies.append((package.id, dependency))
            while True:
                buff = []
                for parent, dependency in dependencies:
                    self.current_package = dependency
                    self.parent_package = None
                    self.package_query.append((dependency.id, parent))
                    if dependency.id in self.processed:
                        if self.processed[dependency.id] == self.package_options.get(dependency.id, None):
                            # This package was processed and it has no option changes
                            continue

                    # Keep the package options to prevent extra transaction
                    self.processed[dependency.id] = self.package_options.get(dependency.id, None)

                    # Keep the package information for the next operations.
                    # We don't want to create a new transaction for it.
                    self.package_heap[dependency.id] = dependency

                    # Get its dependencies
                    package_collection = self.collect_dependencies(dependency)
                    if not package_collection:
                        # The item has no dependency
                        continue
                    # Create a list that consists of parent and child items
                    for item in package_collection:
                        item.parent = package.category+"/"+package.name+"/"+package.slot
                        buff.append((dependency.id, item))
                if not buff:
                    # End of the node
                    break
                dependencies = buff

        try:
            # Sort packages for building operation
            plan = topological_sorting.topsort(self.package_query)
        except topological_sorting.CycleError as err:
            answer, num_parents, children = err
            out.brightred("Circular dependency detected:\n")
            for items in topological_sorting.find_cycles(parent_children=children):
                for item in items:
                    package = self.repodb.find_package(package_id=item).get(0)
                    out.write(package.repo+"/"+package.category+"/"+package.name+"-"\
                            +package.version+":"+package.slot+"  ")
            out.write("\n")
            raise DependencyError
        
        # This part detects inline option conflicts
        removed = {}
        option_conflict = set()
        for package_id in self.inline_option_targets:
            for target in self.inline_option_targets[package_id]:
                for option in self.inline_option_targets[package_id][target]:
                    if option.startswith("-"):
                        if option in removed:
                            removed[option].add((package_id, target))
                        else:
                            removed[option] = set([(package_id, target)])
                    else:
                        if "-"+option in removed:
                            for (my_pkg_id, my_target)  in removed["-"+option]:
                                if my_target == target:
                                    option_conflict.add((my_target, \
                                            self.package_heap[package_id], \
                                            self.package_heap[my_pkg_id],\
                                            option))
        if option_conflict:
            out.error("option conflict detected:\n")
            for (pkg, add, remove, option)in option_conflict:
                out.error(out.color(option, "red")+" option on "+pkg+"\n")
                out.warn("%s/%s/%s/%s adds the option." % (add.repo, add.category, \
                        add.name, add.version))
                out.warn("%s/%s/%s/%s removes the option." % (remove.repo, remove.category, \
                        remove.name, remove.version))
            lpms.terminate()

        self.conditional_versions = {}
        for (key, values) in self.conditional_packages.items():
            for value in values:
                target_package = self.package_heap[key]
                my_item = {
                            "type": value["type"],
                            "version": value["version"],
                            "target": target_package.category+"/"+target_package.name+\
                                    "/"+target_package.slot,
                }
                if not value["owner_id"] in self.conditional_versions:
                    self.conditional_versions[value["owner_id"]] = [my_item]
                else:
                    self.conditional_versions[value["owner_id"]].append(my_item)

        # TODO: I think I must use most professional way for ignore-depends feature.
        if lpms.getopt("--ignore-depends"):
            return self.packages, \
                    self.package_dependencies, \
                    self.package_options, \
                    self.inline_option_targets, \
                    self.conditional_versions, \
                    self.conflicts

        # Workaround for postmerge dependencies
        for (id_dependency, id_package) in self.postmerge_dependencies:
            plan.remove(id_dependency)
            plan.insert(plan.index(id_package)+1, id_dependency)

        final_plan = PackageItem()
        required_package_ids = [package.id for package in self.packages]
        for package_id in plan:
            package = self.package_heap[package_id]
            continue_conditional = False
            # If a package has a conditional decision point,
            # we should consider the condition
            if package.id not in self.conditional_packages:
                for c_package_id in self.conditional_packages:
                    c_package = self.package_heap[c_package_id]
                    if package.pk == c_package.pk:
                        continue_conditional = True
                        if package_id in required_package_ids:
                            final_plan.add_by_pk(c_package)
                            break
                if package_id in required_package_ids:
                    if continue_conditional is False:
                        final_plan.add_by_pk(package)
            if continue_conditional:
                continue
            installed_package = self.instdb.find_package(
                    package_category=package.category,
                    package_name=package.name,
                    package_slot=package.slot
            )
            if installed_package:
                if package.id in self.inline_options:
                    if installed_package.get(0).applied_options is None:
                        final_plan.add_by_pk(package)
                        continue
                    continue_inline = False
                    for inline_option in self.inline_options[package.id]:
                        if not inline_option in installed_package.get(0).applied_options:
                            final_plan.add_by_pk(package)
                            continue_inline = True
                            break
                    if continue_inline:
                        continue
                try:
                    conditional_versions_query = self.instdb.find_conditional_versions(
                            target=package.category+"/"+package.name+"/"+package.slot)
                    if conditional_versions_query:
                        for item in conditional_versions_query:
                            item.decision_point["package_id"]=item.package_id
                            if package.id in self.conditional_packages:
                                if not item.decision_point in self.conditional_packages[package.id]:
                                    self.conditional_packages[package.id].append(item.decision_point)
                            else:
                                self.conditional_packages[package.id] = [item.decision_point]
                    if package.id in self.conditional_packages:
                        decision_points = self.conditional_packages[package.id]
                        for decision_point in decision_points:
                            comparison = utils.vercmp(installed_package.get(0).version, \
                                        decision_point["version"])
                            if decision_point["type"] == ">=":
                                if self.handle_condition_conflict(decision_point, final_plan, \
                                        package.pk, ("<", ">"), (0, 1)) is False:
                                    continue
                                if not comparison in (1, 0) or package.id in required_package_ids:
                                    final_plan.add_by_pk(package)
                            elif decision_point["type"] == "<":
                                if self.handle_condition_conflict(decision_point, final_plan, \
                                        package.pk, (">", "<"), (0, -1)) is False:
                                    continue
                                if comparison != -1:
                                    final_plan.add_by_pk(package)
                            elif decision_point["type"] == ">":
                                if self.handle_condition_conflict(decision_point, final_plan, \
                                        package.pk, ("<", ">"), (0, 1)) is False:
                                    continue
                                if comparison != 1 or package.id in required_package_ids:
                                    final_plan.add_by_pk(package)
                            elif decision_point["type"] == "<=":
                                if self.handle_condition_conflict(decision_point, final_plan, \
                                        package.pk, (">", "<"), (0, -1)) is False:
                                    continue
                                if not comparison in (-1, 0) or package.id in required_package_ids:
                                    final_plan.add_by_pk(package)
                            elif decision_point["type"] == "==":
                                if comparison != 0 or package.id in required_package_ids:
                                    final_plan.add_by_pk(package)
                except ConditionConflict:
                    if not "owner_package" in decision_point:
                        conflict_package = self.instdb.find_package(package_id=\
                                decision_point["package_id"]).get(0)
                        decision_point["owner_package"] = conflict_package.repo+"/"+ \
                        conflict_package.category+"/"+ \
                        conflict_package.name+"/"+ \
                        conflict_package.version

                    out.error("while selecting a convenient version of %s, a conflict detected:\n" % \
                            out.color(package.pk, "red"))
                    out.notify(decision_point["owner_package"]+" wants "+\
                            decision_point["type"]+decision_point["version"])
                    out.notify(self.conflict_point["owner_package"]+" wants "+\
                            self.conflict_point["type"]+self.conflict_point["version"])
                    lpms.terminate("\nplease contact the package maintainers.")

                # Use new options if the package is effected
                if self.use_new_options and not package in final_plan:
                    if package.id in self.package_options:
                        for option in self.package_options[package.id]:
                            if not option in installed_package.get(0).applied_options:
                                final_plan.add_by_pk(package)
                                break
            else:
                final_plan.add_by_pk(package)

        # Oh my god! Some packages have no dependency.
        if single_packages:
            for single_package in single_packages:
                for item_id in plan:
                    if self.package_heap[item_id].pk == single_package.pk:
                        single_packages.remove(single_package)
                        break
            for single_package in single_packages:
                final_plan.insert_into(0, single_package)

        return final_plan, \
                self.package_dependencies, \
                self.package_options, \
                self.inline_option_targets, \
                self.conditional_versions, \
                self.conflicts
