# Copyright 2009 - 2011 Burak Sezer <burak.sezer@linux.org.tr>
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

import re

import lpms
from lpms import out
from lpms.db import api

class Info(object):
    def __init__(self, params):
        self.instdb = api.InstallDB()
        self.repodb = api.RepositoryDB()
        self.params = params
        self.repo = None
        self.category = None
        self.name = None
        self.version = None

    def usage(self):
        out.normal("Get information about given package")
        out.green("General Usage:\n")
        out.write(" $ lpms -i repo/category/pkgname\n")
        out.write("\nrepo and category keywords are optional.\n")
        lpms.terminate()

    def show_package(self, packages):
        package = packages.get(0)
        installed_packages = self.instdb.find_package(package_name=package.name, \
                package_category=package.category)
        metadata = self.repodb.get_package_metadata(package_id=package.id)
        if installed_packages:
            installed_versions, available_versions, package_options = {}, {}, {}
            for package_item in packages:
                if package_item.arch in available_versions:
                    available_versions[package_item.arch].add(package_item.version)
                else:
                    available_versions[package_item.arch] = set([package_item.version])

            for installed_package in installed_packages:
                if installed_package.arch in installed_versions:
                    installed_versions[installed_package.arch].add(installed_package.version)
                else:
                    installed_versions[installed_package.arch] = set([installed_package.version])
                if installed_package.applied_options is None:
                    continue
                for option in installed_package.options:
                    if option in installed_package.applied_options:
                        key = out.color("{"+installed_package.slot+"} "\
                                +installed_package.repo+"::"+installed_package.version, "yellow")
                        if not key in package_options:
                            package_options[key] = [out.color(option, "red")]
                        else:
                            package_options[key].append(out.color(option, "red"))
                for option in installed_package.options:
                    if not option in installed_package.applied_options:
                        key = out.color("{"+installed_package.slot+"} "\
                                +installed_package.repo+"::"+installed_package.version, "yellow")
                        if not key in package_options:
                            package_options[key] = [option]
                        else:
                            package_options[key].append(option)
            versions = ""
            for arch in available_versions:
                versions += out.color(arch, "yellow")+"("+", ".join(available_versions[arch])+") "
            installed_vers = ""
            for arch in installed_versions:
                installed_vers += out.color(arch, "yellow")+"("+", ".join(installed_versions[arch])+") "
            out.write("[%s] %s/%s\n" % (out.color("I", "backgroundgreen"), out.color(package.category, "brightgreen"), \
                    out.color(package.name, "brightgreen")))
            out.write("    %s  %s\n" % (out.color("available versions:", "green"), versions))
            out.write("    %s  %s\n" % (out.color("installed versions:", "green"), installed_vers))
            out.write("    %s             %s\n" % (out.color("summary:", "green"), metadata.summary))
            out.write("    %s            %s\n" % (out.color("homepage:", "green"), metadata.homepage))
            out.write("    %s             %s\n" % (out.color("license:", "green"), metadata.license))
            if package_options:
                out.write("    %s  " % out.color("options:", "green"))
                for index, version in enumerate(package_options):
                    if index == 0:
                        out.write("           => %s" % version+"("+", ".join(package_options[version])+")")
                    else:
                        out.write("                         => %s" % out.color(version, "brightblue")+\
                                "("+", ".join(package_options[version])+")")
                    out.write("\n")
        else:
            available_versions, package_options = {}, {}
            for package_item in packages:
                if package_item.arch in available_versions:
                    available_versions[package_item.arch].add(package_item.version)
                else:
                    available_versions[package_item.arch] = set([package_item.version])
                if package_item.options is not None:
                    package_options["{"+package_item.slot+"} "+package_item.repo+"::"\
                            +package_item.version] = package_item.options
            versions = ""
            for arch in available_versions:
                versions += out.color(arch, "yellow")+"("+", ".join(available_versions[arch])+") "
            out.write("%s %s/%s\n" % (out.color(" * ", "green"), package.category, out.color(package.name, "white")))
            out.write("    %s  %s\n" % (out.color("available versions:", "green"), versions))
            out.write("    %s             %s\n" % (out.color("summary:", "green"), metadata.summary))
            out.write("    %s            %s\n" % (out.color("homepage:", "green"), metadata.homepage))
            out.write("    %s             %s\n" % (out.color("license:", "green"), metadata.license))
            if package_options:
                out.write("    %s  " % out.color("options:", "green"))
                for index, version in enumerate(package_options):
                    if index == 0:
                        out.write("           => %s" % out.color(version, "brightblue")+\
                                "("+", ".join(package_options[version])+")")
                    else:
                        out.write("                         => %s" % out.color(version, \
                                "brightblue")+"("+", ".join(package_options[version])+")")
                    out.write("\n")

    def run(self):
        if lpms.getopt("--help") or len(self.params) == 0:
            self.usage()

        for param in self.params:
            param = param.split("/")
            if len(param) == 3:
                myrepo, mycategory, myname = param
                packages = self.repodb.find_package(package_name=myname, \
                        package_repo=myrepo, package_category=mycategory)
            elif len(param) == 2:
                mycategory, myname = param
                packages = self.repodb.find_package(package_name=myname, \
                        package_category=mycategory)
            elif len(param) == 1:
                packages = self.repodb.find_package(package_name=param[0])
            else:
                out.error("%s seems invalid." % out.color("/".join(param), "brightred"))
                lpms.terminate()
            if not packages:
                out.error("%s not found!" % out.color("/".join(param), "brightred"))
                lpms.terminate()
            
            # Show time!
            self.show_package(packages)

