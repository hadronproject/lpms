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

from lpms import utils
from lpms import out

def show(packages, conflicts, options, installdb):
    '''Shows operation summary to the user'''
    # TODO: This can be splitted as a module
    for package in packages:
        status_bar = [' ', '  ']
        other_version = ""
        installed_packages = installdb.find_package(
                package_name=package.name, \
                package_category=package.category)
        if not installed_packages:
            installed_package = None
            status_bar[0] = out.color("N", "brightgreen")
        else:
            if not [installed_package for installed_package in installed_packages \
                    if package.slot == installed_package.slot]:
                status_bar[1] = out.color("NS", "brightgreen")
            else:
                for installed_package in installed_packages:
                    if installed_package.slot == package.slot:
                        if package.version != installed_package.version:
                            compare = utils.vercmp(package.version, \
                                    installed_package.version)
                            if compare == -1:
                                status_bar[0] = out.color("D", "brightred")
                                other_version = "[%s]" % out.color(\
                                        installed_package.version, "brightred")
                            elif compare == 1:
                                status_bar[0] = out.color("U", "brightgreen")
                                other_version = "[%s]" % out.color(\
                                        installed_package.version, "green")
                        elif package.version == installed_package.version:
                            status_bar[0] = out.color("R", "brightyellow")

        class FormattedOptions(list):
            def __init__(self, data):
                super(FormattedOptions, self).extend(data)

            def append(self, item, color=None):
                self.remove(item)
                if color is not None:
                    super(FormattedOptions, self).insert(0, out.color("*"+item, color))
                else:
                    super(FormattedOptions, self).insert(0, item)

        formatted_options = []
        if package.options is not None:
            installed_package = None
            for item in installed_packages:
                if item.slot == package.slot:
                    installed_package = item
            formatted_options = FormattedOptions(package.options)
            if package.id in options:
                if not status_bar[0].strip() or not status_bar[1].strip():
                    for applied_option in options[package.id]:
                        if installed_package:
                            if installed_package.applied_options is not None and not \
                                    applied_option in installed_package.applied_options:
                                formatted_options.append(applied_option, "brightgreen")
                                continue
                            elif installed_package.applied_options is None:
                                formatted_options.append(applied_option, "brightgreen")
                                continue
                        formatted_options.append(applied_option, "red")
                    if installed_package and installed_package.applied_options is not None:
                        for applied_option in installed_package.applied_options:
                            if not applied_option in options[package.id]:
                                formatted_options.append(applied_option, "brightyellow")
            else:
                for option in package.options:
                    if installed_package and installed_package.applied_options is not None and \
                            option in installed_package.applied_options:
                        formatted_options.append(option, "brightyellow")
                    else:
                        formatted_options.append(option)
        else:
            if hasattr(installed_package, "applied_options") and installed_package.applied_options is not None:
                formatted_options = [out.color("%"+applied_option, "brightyellow") \
                        for applied_option in installed_package.applied_options]

        out.write("  [%s] %s/%s/%s {%s:%s} {%s} %s%s\n" % (
                " ".join(status_bar), \
                package.repo, \
                package.category, \
                package.name, \
                out.color(package.slot, "yellow"),\
                out.color(package.version, "green"),\
                package.arch, \
                other_version, \
                " ("+", ".join(formatted_options)+")" if formatted_options else ""
                )
        )
        
        if package.id in conflicts:
            for conflict in conflicts[package.id]:
                category, name, slot = conflict.split("/")
                conflict = installdb.find_package(package_name=name, \
                        package_category=category, \
                        package_slot = slot).get(0)
                out.write("\t %s %s/%s/%s-%s" % (out.color(">> conflict:", "green"), \
                conflict.repo,\
                        conflict.category, \
                            conflict.name, \
                            conflict.version
                    ))

