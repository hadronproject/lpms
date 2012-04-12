
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
from lpms.exceptions import UnavailablePackage

class DependencyResolver(object):
    def __init__(self, packages):
        self.packages = packages
        self.current_package = None
        self.conf = conf.LPMSConfig()
        self.instdb = api.InstallDB
        self.repodb = api.RepositoryDB()
        self.control_chars = ["||"]
        self.inline_options = {}
        self.repository_stack = {}
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
                self.locked_packages.extend([self.parse_user_defined_file(locked_item)])

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
        return utils.parse_user_defined_file(data, self.repodb, options)

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
            lpms.terminate()
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
            results = database.find_package(package_name=name, package_category=category)
            slot = self.get_convenient_slot(results, slot)
            if not results:
                if instdb: return
                out.error("unmet dependency: %s depends on %s" % (out.color(self.current_package, \
                        "red"), out.color(package, "red")))
                # FIXME: use an exception
                lpms.terminate()
            try:
                package = utils.get_convenient_package(results, self.custom_arch_requests, \
                        convenient_arches, slot)
            except UnavailablePackage:
                for result in results:
                    out.error("%s/%s/%s-%s:%s is unavailable for your arch(%s): " % (result.repo, result.category, \
                            result.name, result.version, result.slot, self.conf.arch))
                lpms.terminate()

            if package.id in self.inline_options:
                for option in inline_options:
                    if not option in self.inline_options[package.id]:
                        self.inline_options[package.id].append(option)
            else:
                self.inline_options[package.id] = inline_options


            for locked in self.locked_packages:
                if (package.category, package.name) == locked[:2]:
                    if package.version in locked[2]:
                        out.error("%s/%s/%s-%s:%s seems to be locked by the system administrator." \
                                % (package.repo, package.category, package.name, package.version, package.slot))
                        # FIXME: Use and exception for this
                        lpms.terminate()
            return package

        category, name = pkgname.split("/")
        inline_options = self.parse_inline_options(name)
        if inline_options:
            name = name[:name.index("[")]
        name, version = utils.parse_pkgname(name)
        results = database.find_package(package_name=name, package_category=category)
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
            out.error("unmet dependency: %s depends on %s" % (out.color(self.current_package, \
                    "red"), out.color(package, "red")))
            # FIXME: use an exception
            lpms.terminate()

        try:
            package = utils.get_convenient_package(results, self.custom_arch_requests, \
                    convenient_arches, slot)
        except UnavailablePackage:
            for result in results:
                out.error("%s/%s/%s-%s:%s is unavailable for your arch(%s): " % (result.repo, result.category, \
                        result.name, result.version, result.slot, self.conf.arch))
            lpms.terminate()

        for locked in self.locked_packages:
            if (package.category, package.name) == locked[:2]:
                if package.version in locked[2]:
                    out.error("%s/%s/%s-%s:%s seems to be locked by the system administrator." \
                            % (package.repo, package.category, package.name, package.version, package.slot))
                    # FIXME: Use and exception for this
                    lpms.terminate()
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

    def collect_dependencies(self, package):
        dependencies = []
        # Set options for the package
        options = self.global_options
        if package.id in self.user_defined_options:
            for option in self.user_defined_options[package.id]:
                if option.startswith("-"):
                    if option[1:] in options:
                        options.remove(option[1:])
                else:
                    if not option in options:
                        options.add(option)
        if package.id in self.inline_options:
            for option in self.inline_options[package.id]:
                if option.startswith("-"):
                    if option[1:] in options:
                        options.remove(option[1:])
                else:
                    if not option in options:
                        options.append(option)

        #Firstly, check static dependencies
        for keyword in self.dependency_keywords:
            if keyword.startswith("static"):
                for dependency in getattr(package, keyword):
                    dependency = self.get_convenient_package(dependency)
                    dependencies.append(dependency)

        # Check optional dependencies
        for keyword in self.dependency_keywords:
            if keyword.startswith("optional"):
                for dependency_bundle in getattr(package, keyword):
                    dependencies.extend(self.parse_suboptional_dependencies(dependency_bundle, options))
        return dependencies

    def create_operation_plan(self):
        for package in self.packages:
            self.current_package = "%s/%s/%s-%s:%s" % (package.repo, package.category, \
                    package.name, package.version, package.slot)
            self.repository_stack[package.id] = package
            for i in self.collect_dependencies(package):
                print i.category, i.name, i.version
        exit()
