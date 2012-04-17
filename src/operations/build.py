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

    def options_info(self):
        # FIXME: This is no good.
        if self.env.options is not None:
            self.env.options = self.env.options.split(" ")
        else:
            self.env.options = []
        return [o for o in self.env.options if utils.opt(o, self.env.cmd_options, 
            self.env.default_options)]

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
                            if short == "$version": self.revisioned = True; self.revision = interphase.group()
                            result = "".join(self.env.__dict__[short[1:]].split(interphase.group()))
                            if not short in ("$name", "$my_slot", "$slot"): setattr(self.env, "raw_"+short[1:], result)
                            data = data.replace(short, result)
                    else:
                        if short == "$version": self.revisioned = True; self.revision = interphase.group()
                        result = "".join(self.env.__dict__[short[1:]].split(interphase.group()))
                        if not short in ("$name", "$my_slot", "$slot"): setattr(self.env, "raw_"+short[1:], result)
                        data = data.replace(short, result)
                except KeyError: pass
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
        if not os.path.isfile(self.env.spec_file):
            out.error("%s not found!" % self.env.spec_file)
            raise BuildError
        if not self.import_script(self.env.spec_file):
            out.error("an error occured while processing the spec: %s" \
                    % out.color(self.env.spec_file, "red"))
            out.error("please report the above error messages to the package maintainer.")
            raise BuildError

    def main(self, data, instruct):
        packages, dependencies, options = data
        
        if instruct["pretend"]:
            self.pretty_print(packages, options)
            lpms.terminate()

        for package in packages:
            if not os.path.ismount("/proc"):
                out.warn("/proc is not mounted. You have been warned.")
            if not os.path.ismount("/dev"):
                out.warn("/dev is not mounted. You have been warned.")

            self.spec_file = os.path.join(cst.repos, package.repo, package.category, \
                    package.name+"-"+package.version+cst.spec_suffix)
            # Ask?
            for keyword in ('repo', 'name', 'category', 'name', \
                    'version', 'slot', 'options'):
                setattr(self.env, keyword, getattr(package, keyword))
            setattr(self.env, "applied_options", options.get(package.id, None))
            
            # set local environment variables
            if not lpms.getopt("--unset-env-variables"):
               self.set_local_environment_variables()


            interphase = re.search(r'-r[0-9][0-9]', self.env.version)
            if not interphase:
                interphase = re.search(r'-r[0-9]', self.env.version)
            try:
                self.env.raw_version = self.env.version.replace(interphase.group(), "")
            except AttributeError:
                self.env.raw_version = self.env.version
 
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

            out.write("  [%s] %s/%s/%s {%s:%s} {%s} %s\n" % (
                    " ".join(status_bar), \
                    package.repo, \
                    package.category, \
                    package.name, \
                    out.color(package.slot, "yellow"),\
                    out.color(package.version, "green"),\
                    package.arch, \
                    other_version)
            )
