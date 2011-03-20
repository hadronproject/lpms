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
from lpms import internals
from lpms import shelltools
from lpms import interpreter
from lpms import constants as cst

from lpms.db import dbapi
from lpms.operations import merge

# FIXME: This module is very ugly. I will re-write it.

class Build(internals.InternalFuncs):
    def __init__(self, pkgname):
        super(Build, self).__init__()
        self.pkgname = pkgname
        self.env.pkgname = pkgname
        self.repo_db = dbapi.RepositoryDB()
        self.download_plan = []
        self.extract_plan = []
        self.urls = []
        self.env.__dict__.update({"get": self.get, "cmd_options": [], "options": []})
        self.spec_file = None
        self.config = conf.LPMSConfig()
        utils.set_environment_variables()

    def best_pkg(self):
        """ Select the package version and return spec's path """
        result = []
        if self.pkgname.startswith("="):
            name, version = utils.parse_pkgname(self.pkgname[1:])
            # FIXME: if there are the same packages in different categories, 
            # warn user.
            for pkg in self.repo_db.find_pkg(name):
                repo_ver = pkg[3].split(' ')
                if version in repo_ver:
                    repo, category, name = pkg[:-1]
                    result = (repo, category, name, version)
            if len(result) == 0:
                lpms.catch_error("%s not found!" % out.color(self.pkgname[1:], "brightred"))
        else:
            data = self.repo_db.find_pkg(self.pkgname)
            if not data:
                lpms.catch_error("%s not found!" % out.color(self.pkgname, "brightred"))
            
            data = data[0]
            repo_ver = data[3].split(' ')
            if len(repo_ver) != 1:
                result = utils.best_version(data)
            else:
                result = data
        
        repo = result[0]; category = result[1]
        version = result[3]; pkgname = result[2]
        spec_file = os.path.join(cst.repos, repo, category,
                pkgname, pkgname+"-"+version)
        spec_file += cst.spec_suffix

        return spec_file, repo, pkgname, category, version

    def options_info(self):
        # FIXME: This is no good.
        if self.env.options is not None:
            self.env.options = self.env.options.split(" ")
        else:
            self.env.options = []
        return [o for o in self.env.options if utils.opt(o, self.env.cmd_options, 
            self.env.default_options)]

    def check_cache(self, url):
        return os.path.isfile(
                os.path.join(self.config.src_cache,
                os.path.basename(url)))

    def prepare_download_plan(self, applied):
        for url in self.urls:
            self.extract_plan.append(url)
            if type(url) != tuple:
                if self.check_cache(url):
                    continue
                self.download_plan.append(url)
            else:
                if self.check_cache(url[1]):
                    continue
                if url[0] in applied: self.download_plan.append(url[1])
        self.env.extract_plan = self.extract_plan

    def prepare_environment(self):
        """ Prepares self.environment """ 
        if self.env.sandbox is None:
            if self.config.sandbox:
                self.env.__setattr__("sandbox", True)

        self.env.build_dir = os.path.join(self.config.build_dir, 
            self.env.category, self.env.fullname, "source", self.env.srcdir)
        self.env.install_dir = os.path.join(self.config.build_dir, 
            self.env.category, self.env.fullname, "install")
        
        try:
            if len(os.listdir(self.env.install_dir)) != 0:
                shelltools.remove_dir(self.env.install_dir)
        except OSError:
            pass

        for i in ('build_dir', 'install_dir'):
            if not os.path.isdir(getattr(self.env, i)):
                os.makedirs(getattr(self.env, i))

    def extract_sources(self):
        for url in self.env.extract_plan:
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
            
    def parse_url_tag(self):
        def set_shortening(data, opt=False):
            for short in ('$name', '$version', '$fullname', '$my_fullname', '$my_name', '$my_version'):
                try:
                    data = data.replace(short, self.env.__dict__[short[1:]])
                except KeyError:
                    pass
            if opt:
                self.urls.append((opt, data))
            else:
                self.urls.append(data)

        for i in self.env.src_url.split(" "):
            result = i.split("(")
            if len(result) == 1:
                set_shortening(result[0])
            elif len(result) == 2:
                set_shortening(result[1], opt=True)

def prepare_plan(pkgnames, instruct):
    # dependency resolotion will be here as well.
    plan =[]
    for pkgname in pkgnames:
        opr = Build(pkgname)

        if not pkgname.endswith(cst.spec_suffix):
            best = opr.best_pkg()
            mytags = ('spec_file', 'repo', 'name', 'category', 'version')
            for tag in mytags:
                opr.env.__dict__[tag] = best[mytags.index(tag)]
            opr.import_script(opr.env.spec_file)
        else:
            opr.env.spec_file = os.path.join(os.getcwd(), pkgname)
            if not os.path.isfile(opr.env.spec_file):
                lpms.terminate("%s not found!" % opr.env.spec_file)

            opr.import_script(opr.env.spec_file)

            opr.env.name, opr.env.version = utils.parse_pkgname(os.path.basename(opr.env.spec_file))
            # set category and repository value for local packages.
            opr.env.category = "local"
            opr.env.repo = "local"

        metadata = utils.metadata_parser(opr.env.metadata)
        opr.env.__dict__.update(instruct)

        opr.env.fullname = opr.env.name+"-"+opr.env.version
        for attr in ('options', 'summary', 'license', 'homepage'):
            setattr(opr.env, attr, metadata[attr])
        opr.env.default_options = opr.config.options.split(" ")
        opr.env.applied = opr.options_info()
        
        if "srcdir" in opr.env.__dict__.keys():
            opr.env.srcdir = opr.env.__dict__["srcdir"]
        else:
            opr.env.srcdir = opr.env.fullname

        if instruct["pretend"]:
            show(opr.env.repo, opr.env.category,
                    opr.env.name, opr.env.version,
                    opr.env.applied, opr.env.options,
                    [])
            continue

        if "src_url" in metadata.keys():
            opr.env.src_url = metadata["src_url"]
        else:
            if "src_url" in local_env.keys():
                opr.env.src_url = local_env["src_url"]

        #for short in ('my_fullname', 'my_name', 'my_version', 'srcdir'):
        #    if short in opr.env.__dict__.keys():
        #        opr.env.__dict__[short] = local_env[short]
        plan.append(opr.env.__dict__)
        
    return plan

def main(pkgnames, instruct):
    #pkgnames = resolve_dependencies(pkgnames)
    operation_plan = prepare_plan(pkgnames, instruct)
    count = len(operation_plan); i = 1
    if instruct["ask"]:
        out.normal("these packages will be merged, respectively:\n")
        for x in operation_plan:
            show(x["repo"], x["category"], x["name"], x["version"],
                    x["applied"], x["options"], [])
        out.write("\nTotal %s package will be merged.\n\n" % out.color(str(count), "green"))
        if not utils.confirm("do you want to continue?"):
            out.write("quitting...\n")
            lpms.terminate()

    for plan in operation_plan:
        opr = Build(plan["pkgname"])
        for key in plan.keys():
            opr.env.__dict__[key] = plan[key]
        opr.prepare_environment()
        utils.xterm_title("(%s/%s) lpms: building %s/%s-%s from %s" % (i, count, opr.env.category, 
            opr.env.name, opr.env.version, opr.env.repo))
        out.normal("(%s/%s) building %s/%s from %s" % (i, count,
            out.color(opr.env.category, "green"),
            out.color(opr.env.name+"-"+opr.env.version, "green"), opr.env.repo)); i += 1
        # warn the user
        if opr.env.sandbox:
            out.notify("sandbox is enabled")
        else:
            out.warn_notify("sandbox is disabled")

        # fetch packages which are in download_plan list
        opr.parse_url_tag()
        opr.prepare_download_plan(opr.env.applied)
        if not fetcher.URLFetcher().run(opr.download_plan):
            lpms.catch_error("\nplease check the spec")

        
        opr.extract_sources()
        if opr.env.stage == "unpack":
            lpms.terminate()

        if len(opr.env.applied) != 0:
            out.notify("applied options: %s" % 
                    " ".join(opr.env.applied))
        
        os.chdir(opr.env.build_dir)
        interpreter.run(opr.env.spec_file, opr.env)
        utils.xterm_title("lpms: %s/%s finished" % (opr.env.category, opr.env.pkgname))
        merge.main(opr.env)
        opr.env.__dict__.clear()
        utils.xterm_title_reset()

def show(repo, category, pkgname, version, applied, options, download_plan):
    out.write(" %s/%s/%s-%s " % (repo, out.color(category, "brightwhite"), 
        out.color(pkgname, "brightgreen"), version))
    
    if options is not None:
        no_applied = []
        out.write("(")
        for o in options:
            if o in applied:
                out.write(out.color(o, "brightred"))
                if options[-1] != o:
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

