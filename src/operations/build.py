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
# You should have received a copy of the GNU General Public Licens
# along with lpms.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import glob

import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import fetcher
from lpms import internals
from lpms import initpreter
from lpms import shelltools
from lpms import interpreter
from lpms import constants as cst

from lpms.db import api
from lpms.operations import merge
from lpms.exceptions import BuildError

class Build(internals.InternalFuncs):
    '''This class reads the specs and prepares the environment. 
    Finally, it runs interpreter for building.'''
    def __init__(self):
        super(Build, self).__init__()
        self.repodb = api.RepositoryDB()
        self.instdb = api.InstallDB()
        self.download_plan = []
        self.extract_plan = []
        self.urls = []
        self.env.__dict__.update({"get": self.get, "cmd_options": \
                [], "options": []})
        self.spec_file = None
        self.config = conf.LPMSConfig()
        if not lpms.getopt("--unset-env-variables"):
            utils.set_environment_variables()
        self.revisioned = False
        self.revision = None

    def set_local_environment_variables(self):
        '''Sets environment variables such as CFLAGS, CXXFLAGS and LDFLAGS if the user
        defines a local file which is included them'''
        switches = ["ADD", "REMOVE", "GLOBAL"]
        for item in cst.local_env_variable_files:
            if not os.access(item, os.R_OK):
                continue
            variable_type = item.split("/")[-1].upper()
            with open(item) as data:
                for line in data.readlines():
                    add = []; remove = []; global_flags = []
                    if line.startswith("#"):
                        continue
                    myline = [i.strip() for i in line.split(" ")]
                    target = myline[0]
                    if len(target.split("/")) == 2:
                        if target != self.env.category+"/"+self.env.name:
                            continue
                    elif len(target.split("/")) == 1:
                        if target != self.env.category:
                            if len(target.split("-")) == 1:
                                out.warn("warning: invalid line found in %s:" % item)
                                out.red("   "+line)
                            continue
                    else:
                        if len(target.split("-")) == 1:
                            out.warn("warning: invalid line found in %s:" % item)
                            out.red("   "+line)
                            continue

                    if variable_type == "ENV":
                        if myline[1] == "UNSET":
                            variable = myline[2]
                            if variable in os.environ:
                                del os.environ[variable]
                        else:
                            try:
                                variable, value = myline[1:]
                            except ValueError:
                                out.warn("warning: invalid line found in %s:" % item)
                                out.red("   "+line)
                            else:
                                os.environ[variable] = value

                    for switch in switches:
                        if not switch in myline[1:]:
                            continue
                        switch_index = myline.index(switch)
                        for word in myline[switch_index+1:]:
                            if word in switches: 
                                break
                            if switch == "GLOBAL":
                                global_flags.append(word)
                            if switch == "ADD":
                                add.append(word)
                            elif switch == "REMOVE":
                                remove.append(word)
                    
                    if global_flags:
                        if variable_type in os.environ:
                            del os.environ[variable_type]
                            os.environ[variable_type] = " ".join(global_flags)
                    else:
                        if add:
                            if variable_type in os.environ:
                                current = os.environ[variable_type]
                                current += " "+" ".join(add)
                                os.environ[variable_type] = current
                            else:
                                out.warn("%s not defined in your environment" % variable_type)
                        if remove:
                            if variable_type in os.environ:
                                current = os.environ[variable_type]
                                new = [atom for atom in current.split(" ") if not atom in remove]
                                os.environ[variable_type] = " ".join(new)
                            else:
                                out.warn("%s not defined in your environment" % variable_type)

    def is_downloaded(self, url):
        return os.path.isfile(
                os.path.join(self.config.src_cache,
                os.path.basename(url)))

    def prepare_download_plan(self, applied):
        for url in self.urls:
            if not isinstance(url, tuple):
                self.extract_plan.append(url)
                if self.is_downloaded(url):
                    continue
                self.download_plan.append(url)
            else:
                option, url = url
                if option in applied:
                    self.extract_plan.append(url)
                    if self.is_downloaded(url):
                        continue
                    self.download_plan.append(url)
        setattr(self.env, "extract_plan", self.extract_plan)

    def prepare_environment(self):
        if self.env.sandbox is None:
            if not self.config.sandbox and lpms.getopt("--enable-sandbox"):
                self.env.__setattr__("sandbox", True)
            elif self.config.sandbox and not lpms.getopt("--ignore-sandbox"):
                self.env.__setattr__("sandbox", True)

        self.env.build_dir = os.path.join(self.config.build_dir, 
            self.env.category, self.env.fullname, "source", self.env.srcdir)
        self.env.install_dir = os.path.join(self.config.build_dir, 
            self.env.category, self.env.fullname, "install")
        
        try:
            if not lpms.getopt("--resume-build") and len(os.listdir(self.env.install_dir)) != 0:
                shelltools.remove_dir(self.env.install_dir)
        except OSError:
            pass

        for target in ('build_dir', 'install_dir'):
            if not os.path.isdir(getattr(self.env, target)):
                os.makedirs(getattr(self.env, target))

    def parse_url_tag(self):
        def set_shortening(data, opt=False):
            for short in ('$url_prefix', '$src_url', '$slot', '$my_slot', '$name', '$version', \
                    '$fullname', '$my_fullname', '$my_name', '$my_version'):
                try:
                    interphase = re.search(r'-r[0-9][0-9]', self.env.__dict__[short[1:]])
                    if not interphase:
                        interphase = re.search(r'-r[0-9]', self.env.__dict__[short[1:]])
                        if not interphase:
                            data = data.replace(short, self.env.__dict__[short[1:]])
                        else:
                            if short == "$version":
                                self.revisioned = True
                                self.revision = interphase.group()
                            result = "".join(self.env.__dict__[short[1:]].split(interphase.group()))
                            if not short in ("$name", "$my_slot", "$slot"):
                                setattr(self.env, "raw_"+short[1:], result)
                            data = data.replace(short, result)
                    else:
                        if short == "$version":
                            self.revisioned = True
                            self.revision = interphase.group()
                        result = "".join(self.env.__dict__[short[1:]].split(interphase.group()))
                        if not short in ("$name", "$my_slot", "$slot"):
                            setattr(self.env, "raw_"+short[1:], result)
                        data = data.replace(short, result)
                except KeyError:
                    pass
            if opt:
                self.urls.append((opt, data))
            else:
                self.urls.append(data)

        for url in self.env.src_url.split(" "):
            result = url.split("(")
            if len(result) == 1:
                set_shortening(url)
            elif len(result) == 2:
                option, url = result
                url = url.replace(")", "")
                set_shortening(url, opt=option)

    def compile_script(self):
        if not os.path.isfile(self.spec_file):
            out.error("%s not found!" % self.spec_file)
            raise BuildError
        if not self.import_script(self.spec_file):
            out.error("an error occured while processing the spec: %s" \
                    % out.color(self.spec_file, "red"))
            out.error("please report the above error messages to the package maintainer.")
            raise BuildError

    def main(self, data, instruct):
        packages, dependencies, options = data
        
        if instruct["pretend"]:
            out.write("\n")
            out.normal("these packages will be merged, respectively:\n")
            self.pretty_print(packages, options)
            out.write("\ntotal %s package(s) listed.\n\n" \
                    % out.color(str(len(packages)), "green"))
            lpms.terminate()

        if instruct["ask"]:
            out.write("\n")
            out.normal("these packages will be merged, respectively:\n")
            self.pretty_print(packages, options)
            utils.xterm_title("lpms: confirmation request")
            out.write("\ntotal %s package(s) will be merged.\n\n" \
                    % out.color(str(len(packages)), "green"))
            if not utils.confirm("do you want to continue?"):
                out.write("quitting...\n")
                utils.xterm_title_reset()
                lpms.terminate()

        # clean source code extraction directory if it is wanted
        if lpms.getopt("--clean-tmp"):
            clean_tmp_exceptions = ("resume")
            for item in shelltools.listdir(cst.extract_dir):
                if item in clean_tmp_exceptions: continue
                path = os.path.join(cst.extract_dir, item)
                if path in clean_tmp_exceptions: continue
                if os.path.isdir(path):
                    shelltools.remove_dir(path)
                else:
                    shelltools.remove_file(path)

        index = 0
        for package in packages:
            self.env.package = package
            self.env.dependencies = dependencies.get(package.id, None)
            installed_package = self.instdb.find_package(package_name=package.name, \
                    package_category=package.category, package_slot=package.slot)
            self.env.previous_version = installed_package.get(0).version \
                    if installed_package else None
            # FIXME: This is no good
            self.env.__dict__.update(instruct)
            index += 1
            if not os.path.ismount("/proc"):
                out.warn("/proc is not mounted. You have been warned.")
            if not os.path.ismount("/dev"):
                out.warn("/dev is not mounted. You have been warned.")

            self.spec_file = os.path.join(cst.repos, package.repo, package.category, package.name, \
                    package.name+"-"+package.version+cst.spec_suffix)
            for keyword in ('repo', 'name', 'category', 'name', \
                    'version', 'slot', 'options'):
                setattr(self.env, keyword, getattr(package, keyword))
            self.env.fullname = self.env.name+"-"+self.env.version
            setattr(self.env, "applied_options", options.get(package.id, None))
            # set local environment variables
            if not lpms.getopt("--unset-env-variables"):
               self.set_local_environment_variables()

            interphase = re.search(r'-r[0-9][0-9]', self.env.version)
            if not interphase:
                interphase = re.search(r'-r[0-9]', self.env.version)
            
            if interphase is not None and interphase.group():
                self.env.version = self.env.version.replace(interphase.group(), "")
                self.env.revision = interphase.group()

            self.compile_script()

            metadata = utils.metadata_parser(self.env.metadata)
            if "src_url" in metadata:
                self.env.src_url = metadata["src_url"]
            else:
                if not "src_url" in self.env.__dict__.keys():
                    self.env.src_url = None

            setattr(self.env, "index", index)
            setattr(self.env, "count", len(packages))
            setattr(self.env, "filesdir", os.path.join(cst.repos, self.env.repo, \
                self.env.category, self.env.name, cst.files_dir))
            setattr(self.env, "src_cache", cst.src_cache)

            if not "srcdir" in self.env.__dict__:
                setattr(self.env, "srcdir", \
                        self.env.name+"-"+self.env.version)
            # FIXME: None?
            self.env.sandbox = None
            self.prepare_environment()

            # start logging
            # we want to save starting time of the build operation
            lpms.logger.info("starting build (%s/%s) %s/%s/%s-%s" % (index, len(packages), self.env.repo, 
                self.env.category, self.env.name, self.env.version))

            out.normal("(%s/%s) building %s/%s from %s" % (index, len(packages),
                out.color(self.env.category, "green"),
                out.color(self.env.name+"-"+self.env.version, "green"), self.env.repo));

            out.notify("you are using %s userland and %s kernel" % (self.config.userland, self.config.kernel))

            if self.env.sandbox:
                lpms.logger.info("sandbox enabled build")
                out.notify("sandbox is enabled")
            else:
                lpms.logger.warning("sandbox disabled build")
                out.warn_notify("sandbox is disabled")

            # fetch packages which are in download_plan list
            if self.env.src_url is not None:
                # preprocess url tags such as $name, $version and etc
                self.parse_url_tag()
                # if the package is revisioned, override build_dir and install_dir. remove revision number from these variables.
                if self.revisioned:
                    for variable in ("build_dir", "install_dir"):
                        new_variable = "".join(os.path.basename(getattr(self.env, variable)).split(self.revision))
                        setattr(self.env, variable, os.path.join(os.path.dirname(getattr(self.env, \
                                variable)), new_variable))

                utils.xterm_title("lpms: downloading %s/%s/%s-%s" % (self.env.repo, self.env.category,
                    self.env.name, self.env.version))
                
                self.prepare_download_plan(self.env.applied_options)
                
                if not fetcher.URLFetcher().run(self.download_plan):
                    lpms.terminate("\nplease check the spec")

            if self.env.applied_options is not None and len(self.env.applied_options) != 0:
                out.notify("applied options: %s" % 
                        " ".join(self.env.applied_options))
                
            if self.env.src_url is None and not self.extract_plan and hasattr(self.env, "extract"):
                # Workaround for #208
                self.env.extract_nevertheless = True

            # remove previous sandbox log if it is exist.
            if os.path.exists(cst.sandbox_log):
                shelltools.remove_file(cst.sandbox_log)
            os.chdir(self.env.build_dir)

            # ccache facility
            if "ccache" in self.config.__dict__ and self.config.ccache:
                if os.access("/usr/lib/ccache/bin", os.R_OK):
                    out.notify("ccache is enabled")
                    os.environ["PATH"] = "/usr/lib/ccache/bin:%(PATH)s" % os.environ
                    if "ccache_dir" in self.config.__dict__:
                        os.environ["CCACHE_DIR"] = self.config.ccache_dir
                    else:
                        os.environ["CCACHE_DIR"] = cst.ccache_dir
                    # sandboxed processes can access to CCACHE_DIR.
                    os.environ["SANDBOX_PATHS"] = os.environ['CCACHE_DIR']+":%(SANDBOX_PATHS)s" % os.environ
                else:
                    out.warn("ccache could not be enabled. so you should check dev-util/ccache")

            if not interpreter.run(self.spec_file, self.env):
                lpms.terminate("thank you for flying with lpms.")

            lpms.logger.info("finished %s/%s/%s-%s" % (self.env.repo, self.env.category, 
                self.env.name, self.env.version))

            utils.xterm_title("lpms: %s/%s finished" % (self.env.category, self.env.name))

            out.notify("cleaning build directory...\n")
            shelltools.remove_dir(os.path.dirname(self.env.install_dir))
            catdir = os.path.dirname(os.path.dirname(self.env.install_dir))
            if not os.listdir(catdir):
                shelltools.remove_dir(catdir)

            self.env.__dict__.clear()
            utils.xterm_title_reset()

    def pretty_print(self, packages, options):
        for package in packages:
            status_bar = ['','','','']
            other_version = ""
            installed_packages = self.instdb.find_package(
                    package_name=package.name, \
                    package_category=package.category)
            if not installed_packages:
                status_bar[0] = out.color("N", "brightgreen")
            else:
                if not [installed_package for installed_package in installed_packages \
                        if package.slot == installed_package.slot]:
                    status_bar[1] = out.color("NS", "brightgreen")
                else:
                    for installed_package in installed_packages:
                        if installed_package.slot == package.slot and \
                                package.version == installed_package.version:
                                    compare = utils.vercmp(package.version, \
                                            installed_package.version)
                                    if compare == -1:
                                        status_bar[1] = out.color("D", "brightred")
                                        other_version = "[%s]" % out.color(\
                                                installed_package.version, "brightred")
                                    elif compare == 1:
                                        status_bar[1] = out.color("U", "brightgreen")
                                        other_version = "[%s]" % out.color(\
                                                installed_package.version, "brightred")
                                    elif compare == 0:
                                        status_bar[1] = out.color("R", "brightyellow")

            formatted_options = ""
            if package.id in options:
                formatted_options = []
                if not status_bar[0] or not status_bar[1]:
                    for applied_option in options[package.id]:
                        formatted_options.append(out.color(applied_option, "red"))
                    for option in package.options:
                        if not option in options[package.id]:
                            formatted_options.append(option)

                formatted_options = "("+", ".join(formatted_options)+")"

            out.write("  [%s] %s/%s/%s {%s:%s} {%s} %s%s\n" % (
                    " ".join(status_bar), \
                    package.repo, \
                    package.category, \
                    package.name, \
                    out.color(package.slot, "yellow"),\
                    out.color(package.version, "green"),\
                    package.arch, \
                    other_version, \
                    formatted_options)
            )
