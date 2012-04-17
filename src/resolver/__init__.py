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
from lpms.exceptions import LockedPackage
from lpms.exceptions import DependencyError
from lpms.exceptions import UnavailablePackage

class DependencyResolver(object):
    '''Dependency resolving engine for lpms'''
    def __init__(self, packages, cmd_options=None, custom_options=None):
        self.packages = packages
        self.cmd_options = cmd_options
        self.custom_options = custom_options
        self.current_package = None
        self.parent_package = None
        self.conf = conf.LPMSConfig()
        self.instdb = api.InstallDB()
        self.repodb = api.RepositoryDB()
        self.processed = {}
        self.package_heap = {}
        self.control_chars = ["||"]
        self.inline_options = {}
        self.package_dependencies = {}
        self.package_options = {}
        self.repository_cache = {}
        self.user_defined_options = {}
        self.package_query = []
        self.locked_packages = []
        self.global_options = set()
        self.forbidden_option = set()
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
        convenient_arches = utils.get_convenient_arches(self.conf.arch)
        result = LCollect()
        database = self.repodb
        if instdb:
            database = self.instdb
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
                if instdb: return
                out.error("unmet dependency: %s depends on %s" % (out.color(self.current_package, \
                        "red"), out.color(package, "red")))
                raise DependencyError
            try:
                package = utils.get_convenient_package(results, self.locked_packages, \
                        self.custom_arch_requests, convenient_arches, slot)
            except UnavailablePackage:
                for result in results:
                    out.error("%s/%s/%s-%s:%s {%s} is unavailable for your arch(%s)." % (result.repo, result.category, \
                            result.name, result.version, result.slot, result.arch, self.conf.arch))
                out.write("\n")
                out.write("%s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), self.parent_package.repo, \
                        self.parent_package.category, self.parent_package.name, self.parent_package.version, \
                        self.parent_package.slot, self.parent_package.arch))
                out.write(" %s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), self.current_package.repo, \
                        self.current_package.category, self.current_package.name, self.current_package.version, \
                        self.current_package.slot, self.current_package.arch))
                raise DependencyError
            except LockedPackage:
                out.error("these package(s) is/are locked by the system administrator:")
                for result in results:
                    out.error_notify("%s/%s/%s-%s:%s {%s}" % (result.repo, result.category, \
                            result.name, result.version, result.slot, result.arch))
                out.write("\n")
                out.write("%s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), self.parent_package.repo, \
                        self.parent_package.category, self.parent_package.name, self.parent_package.version, \
                        self.parent_package.slot, self.parent_package.arch))
                out.write(" %s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), self.current_package.repo, \
                        self.current_package.category, self.current_package.name, self.current_package.version, \
                        self.current_package.slot, self.current_package.arch))
                raise DependencyError

            if inline_options:
                if package.id in self.inline_options:
                    for option in inline_options:
                        if not option in self.inline_options[package.id]:
                            self.inline_options[package.id].append(option)
                else:
                    self.inline_options[package.id] = inline_options

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
        if gte:
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == 1 or comparison == 0:
                    packages.append(result)
        elif lte:
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == -1 or comparison == 0:
                    packages.append(result)
        elif lt:
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == -1:
                    packages.append(result)
        elif gt:
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == 1:
                    packages.append(result)
        elif et:
            for result in results:
                comparison = utils.vercmp(result.version, version)
                if comparison == 0:
                    packages.append(result)

        if not packages:
            out.error("unmet dependency: %s/%s/%s-%s:%s {%s} depends on %s" % \
                    (self.current_package.repo, \
                    self.current_package.category, \
                    self.current_package.name, \
                    self.current_package.version, \
                    self.current_package.slot, \
                    self.current_package.arch, \
                    out.color(package, "red")))
            # FIXME: use an exception
            raise DependencyError

        try:
            package = utils.get_convenient_package(results, self.locked_packages, self.custom_arch_requests, \
                    convenient_arches, slot)
        except UnavailablePackage:
            for result in results:
                out.error("%s/%s/%s-%s:%s {%s}is unavailable for your arch(%s)." % (result.repo, result.category, \
                        result.name, result.version, result.slot, result.arch, self.conf.arch))
            out.write("\n")
            out.write("%s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), self.parent_package.repo, \
                    self.parent_package.category, self.parent_package.name, self.parent_package.version, \
                    self.parent_package.slot, self.parent_package.arch))
            out.write(" %s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), self.current_package.repo, \
                    self.current_package.category, self.current_package.name, self.current_package.version, \
                    self.current_package.slot, self.current_package.arch))
            raise DependencyError
        except LockedPackage:
            out.error("these package(s) is/are locked by the system administrator:")
            for result in results:
                out.error_notify("%s/%s/%s-%s:%s {%s}" % (result.repo, result.category, \
                        result.name, result.version, result.slot, result.arch))
            out.write("\n")
            out.write("%s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), self.parent_package.repo, \
                    self.parent_package.category, self.parent_package.name, self.parent_package.version, \
                    self.parent_package.slot, self.parent_package.arch))
            out.write(" %s %s/%s/%s-%s:%s {%s}\n" % (out.color("->", "brightyellow"), self.current_package.repo, \
                    self.current_package.category, self.current_package.name, self.current_package.version, \
                    self.current_package.slot, self.current_package.arch))
            raise DependencyError

        if inline_options:
            if package.id in self.inline_options:
                for option in inline_options:
                    if not option in self.inline_options[package.id]:
                        self.inline_options[package.id].append(option)
            else:
                self.inline_options[package.id] = inline_options

        return package

    def parse_suboptional_dependencies(self, bundle, options):
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
                            result.append(self.get_convenient_package(package))
                    continue
            else:
                if not parent in options: 
                    if "||" in bundle[parent]:
                        for package in bundle[parent][bundle[parent].index("||")+1:]:
                            result.append(self.get_convenient_package(package))
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
                                result.append(self.get_convenient_package(package)) 
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
                        for package in packages:
                            result.append(self.get_convenient_package(package))
                    else:
                        if "||" in packages:
                            for package in packages[packages.index("||")+1:]:
                                result.append(self.get_convenient_package(package))
                else:
                    if child in self.control_chars:
                        continue
                    result.append(self.get_convenient_package(child))
        return result
    
    def keep_dependency_information(self, package_id, keyword, dependency):
        bundle = (dependency.category, dependency.name, \
                dependency.version, dependency.arch)
        if not package_id in self.package_dependencies:
            self.package_dependencies[package_id] = { keyword: set([bundle]) }
        else:
            if keyword in self.package_dependencies[package_id]:
                self.package_dependencies[package_id][keyword].add(bundle)
            else:
                self.package_dependencies[package_id].update({ keyword: set(bundle) })

    def collect_dependencies(self, package):
        dependencies = []
        current_options = set()
        already_added = {}

        def process_option(option):
            if option.startswith("-"):
                if option[1:] in options:
                    options.remove(option[1:])
            else:
                if not option in options:
                    options.add(option)

        # Set global options(from /etc/lpms/build.conf) for the package
        options = self.global_options
        if package.id in self.user_defined_options:
            for option in self.user_defined_options[package.id]:
                process_option(option)
        
        # Set options that given via command line
        for cmd_option in self.cmd_options:
            if not cmd_option in options:
                process_option(cmd_option)

        # Set options that given via command line with package name and version
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
       
        # Set the options that used by the package
        for option in options:
            if package.options and option in package.options:
                current_options.add(option)

        #Firstly, check static dependencies
        for keyword in self.dependency_keywords:
            if keyword.startswith("static"):
                for dependency in getattr(package, keyword):
                    dependency = self.get_convenient_package(dependency)
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
                    dependencies.append(dependency)

        # Check optional dependencies
        for keyword in self.dependency_keywords:
            if keyword.startswith("optional"):
                for dependency_bundle in getattr(package, keyword):
                    for dependency in self.parse_suboptional_dependencies(dependency_bundle, options):
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
                        dependencies.append(dependency)
        return dependencies

    def create_operation_plan(self):
        for package in self.packages:
            self.parent_package = package
            self.package_heap[package.id] = package
            dependencies = []
            # Create a list that consists of parent and child items
            for dependency in self.collect_dependencies(package):
                dependencies.append((package.id, dependency))
            while True:
                buff = []
                for parent, dependency in dependencies:
                    self.current_package = dependency
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
        
        if not plan:
            # Oh my god! The package has no dependency.
            plan = [package.id for package in self.packages]

        final_plan = []
        if lpms.getopt("--ignore-depends"):
            return self.packages, self.package_dependencies, self.package_options

        for package_id in plan:
            final_plan.append(self.package_heap[package_id])

        return final_plan, self.package_dependencies, self.package_options
        #for index, i in enumerate(plan):
        #    package = self.package_heap[i]
        #    installed_package = self.instdb.find_package(package_name=package.name, package_category=package.category, \
        #            package_version=package.version)
        #    print index+1,  package.id, package.category, package.name, package.version
            #if package.id in self.package_options:
            #    print self.package_options[package.id]
