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
import glob

import lpms

from lpms import conf
from lpms import out
from lpms import utils
from lpms import fetcher
from lpms import archive
from lpms import shelltools
from lpms import interpreter
from lpms import constants as cst

from lpms.db import dbapi

class Environment(object):
    def __init__(self, pkgname):
        self.__dict__["pkgname"] = pkgname

class Build(object):
    def __init__(self, pkgname):
        self.pkgname = pkgname
        self.env = Environment(self.pkgname)
        self.repo_db = dbapi.RepositoryDB()
        self.download_plan = []
        self.extract_plan = []
        self.env.__dict__.update({"cmd_options": [], "options": []})
        self.spec_file = None
        self.config = conf.LPMSConfig()
        utils.set_environment_variables()

    def select_package(self):
        """ Select the package version and return spec's path """
        if self.pkgname.startswith("="):
            name, version = utils.parse_pkgname(self.pkgname[1:]+cst.spec_suffix)
            for pkg in self.repo_db.find_pkg(name):
                if pkg[3] == version:
                    data = pkg
        else:
            data = self.repo_db.find_pkg(self.pkgname)
            if len(data) == 0:
                lpms.catch_error("%s not found!" % out.color(self.pkgname, "brightred"))
            elif len(data) != 1:
                data = utils.best_version(data)
            else:
                data = data[0]
        tags = ('repo', 'category', 'pkgname', 'version')
        for tag in tags:
            self.env.__setattr__(tag, data[tags.index(tag)])

        spec_file = os.path.join(cst.repos, self.env.repo, self.env.category,
                self.env.pkgname, self.env.pkgname+"-"+self.env.version)
        spec_file += cst.spec_suffix
        return spec_file

    def options_info(self):
        # FIXME: This is no good
        opts = self.env.options
        if opts is not None:
            opts = opts.split(" ")
        else:
            opts = []
        return [o for o in opts if utils.opt(o, self.env.cmd_options, self.env.default_options)]

    def check_cache(self, url):
        if os.path.isfile(os.path.join(self.config.src_cache, os.path.basename(url))):
            return True

    def prepare_download_plan(self, urls, applied):
        for url in urls:
            self.extract_plan.append(url)
            if type(url) != tuple:
                if self.check_cache(url):
                    continue
                self.download_plan.append(url)
            else:
                if self.check_cache(url[1]):
                    continue
                if url[0] in applied: self.download_plan.append(url[1])

    def prepare_environment(self):
        """ Prepares self.environment """ 
        self.env.__dict__.update(utils.import_script(self.spec_file))
        name_data = utils.parse_pkgname(os.path.basename(self.spec_file))
        if len(name_data) == 2:
            pkgname, version = name_data
        elif len(name_data) == 3:
            pkgname = data[0]; version = data[1]+"-"+data[2]

        if "srcdir" in self.env.__dict__.keys():
            srcdir = self.env.srcdir
        else:
            srcdir = pkgname+"-"+version

        if self.env.sandbox is None:
            if self.config.sandbox:
                self.env.__setattr__("sandbox", True)

        # FIXME:
        self.env.__setattr__("spec", self.spec_file)
        self.env.__setattr__("srcdir", srcdir)
        self.env.__setattr__("pkgname", pkgname)
        self.env.__setattr__("full_name", pkgname+"-"+version)
        self.env.__setattr__("build_dir", os.path.join(self.config.build_dir, 
            self.env.category, pkgname+"-"+version, "source", srcdir))
        self.env.__setattr__("install_dir", os.path.join(self.config.build_dir, 
            self.env.category, pkgname+"-"+version, "install"))
        
        try:
            if len(os.listdir(self.env.install_dir)) != 0:
                shelltools.remove_dir(self.env.install_dir)
        except OSError:
            pass

        for i in ('build_dir', 'install_dir'):
            if not os.path.isdir(getattr(self.env, i)):
                os.makedirs(getattr(self.env, i))

    def extract_sources(self):
        for url in self.extract_plan:
            archive_path = os.path.join(self.config.src_cache, os.path.basename(url))
            target = os.path.dirname(self.env.build_dir)
            unpack_file = os.path.join(os.path.dirname(target), ".unpacked")
            if os.path.isfile(unpack_file):
                if self.env.force:
                    shelltools.remove_file(unpack_file)
                else:
                    out.notify("%s seems already unpacked." % os.path.basename(archive_path))
                    continue
            archive.extract(str(archive_path), str(target))
            shelltools.touch(unpack_file)

def main(pkgnames, instruct):
    """Main function for build operation
    It needs a list, which contains package names"""
    pkg_count = len(pkgnames); i = 1
    ask_list = []
    for pkgname in pkgnames:
        opr = Build(pkgname)

        if not pkgname.endswith(cst.spec_suffix):
            # prepare the package
            opr.spec_file = opr.select_package()
            options = opr.repo_db.get_options(opr.env.pkgname, opr.env.repo, opr.env.category)[0]
            src_url = opr.repo_db.get_src_url(opr.env.pkgname)[0][0]
        else:
            opr.spec_file = os.path.join(os.getcwd(), pkgname)
            if not os.path.isfile(opr.spec_file):
                lpms.terminate("%s not found!" % opr.spec_file)

            local_env = utils.import_script(pkgname)
            metadata = utils.metadata_parser(local_env["metadata"])
            if "src_url" in metadata.keys():
                src_url = metadata["src_url"]
            else:
                if "src_url" in local_env.keys():
                    src_url = local_env["src_url"]

            opr.env.pkgname, opr.env.version = utils.parse_pkgname(os.path.basename(opr.spec_file))
            # set category and repository value for local packages.
            opr.env.category = "local"
            opr.env.repo = "local"
            options = metadata["options"]

        if instruct["show_opts"]:
            out.normal("available options for %s" % out.color(opr.env.category+"/"+pkgname+"-"+opr.env.version, "green"))
            out.notify(options)
            continue

        opr.env.__dict__.update(instruct)
        opr.prepare_environment()
        
        opr.env.__setattr__("options", options)
        opr.env.__setattr__("default_options", opr.config.options.split(" "))
        applied = opr.options_info()
        # FIXME
        if instruct["pretend"]:
            pretend(opr.env.repo, opr.env.category, 
                    opr.env.pkgname, opr.env.version, 
                    applied, opr.env.options, opr.download_plan)
            continue

        if instruct["ask"]:
            ask_list.append((opr.env.repo, opr.env.category, 
                opr.env.pkgname, opr.env.version, applied, 
                opr.env.options, opr.download_plan))
            if pkgnames[-1] == pkgname:
                out.normal("These packages will be built:")
                for repo, category, pkgname, version, applied, options, download_plan in ask_list:
                    pretend(repo, category, pkgname, version, applied, options, download_plan)
                return
            continue

        opr.prepare_download_plan(utils.parse_url_tag(src_url,
            opr.env.pkgname, opr.env.version), applied)

        out.normal("(%s/%s) building %s/%s from %s" % (i, pkg_count,
            out.color(opr.env.category, "green"),
            out.color(opr.env.pkgname+"-"+opr.env.version, "green"), opr.env.repo)); i += 1
        
        # warn the user
        if opr.env.sandbox:
            out.notify("sandbox is enabled")
        else:
            out.warn_notify("sandbox is disabled")
        
        # fetch packages which are in download_plan list
        if not fetcher.URLFetcher().run(opr.download_plan):
            lpms.catch_error("\nplease check the spec")

        
        opr.extract_sources()
        if opr.env.stage == "unpack":
            lpms.terminate()

        if len(applied) != 0:
            out.notify("applied options: %s" % 
                    " ".join(applied))

        os.chdir(opr.env.build_dir)
        interpreter.run(opr.spec_file, opr.env)
        opr.env.__dict__.clear()

def pretend(repo, category, pkgname, version, applied, options, download_plan):
    out.write(" %s/%s/%s-%s " % (repo, out.color(category, "brightwhite"), 
        out.color(pkgname, "brightgreen"), version))
    
    if options is not None:
        no_applied = []
        out.write("(")
        opts = options.split(" ")
        for o in opts:
            if o in applied:
                out.write(out.color(o, "red"))
                if opts[-1] != o:
                    out.write(" ")
            else:
                no_applied.append("-"+o)
            
        for no in no_applied:
            out.write(no)
            if no_applied[-1] != no:
                out.write(" ")
        out.write(")")

    if len(download_plan) == 0:
        out.write(" 0 kb")
    out.write("\n")

