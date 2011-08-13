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
import cPickle as pickle

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
    def __init__(self):
        super(Build, self).__init__()
        self.repo_db = dbapi.RepositoryDB()
        self.download_plan = []
        self.extract_plan = []
        self.urls = []
        self.env.__dict__.update({"get": self.get, "cmd_options": [], "options": []})
        self.spec_file = None
        self.config = conf.LPMSConfig()
        utils.set_environment_variables()

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
            if not isinstance(url, tuple):
                if self.check_cache(url):
                    continue
                self.download_plan.append(url)
            else:
                if self.check_cache(url[1]):
                    continue
                if url[0] in applied: self.download_plan.append(url[1])
        self.env.extract_plan = self.extract_plan

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

        for i in ('build_dir', 'install_dir'):
            if not os.path.isdir(getattr(self.env, i)):
                os.makedirs(getattr(self.env, i))

    def extract_sources(self):
        for url in self.env.extract_plan:
            archive_path = os.path.join(self.config.src_cache, os.path.basename(url))
            target = os.path.dirname(self.env.build_dir)
            unpack_file = os.path.join(os.path.dirname(target), ".unpacked")
            if os.path.isfile(unpack_file):
                if lpms.getopt("--force-unpack"):
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

    def compile_script(self):
        if not os.path.isfile(self.env.spec_file):
            lpms.catch_error("%s not found!" % self.env.spec_file)
        self.import_script(self.env.spec_file)


def main(raw_data, instruct):
    operation_plan, operation_data = raw_data
    # resume previous operation_plan
    # if skip_first returns True, skip first package 
    if instruct["resume"]:
        if os.path.exists(cst.resume_file):
            with open(cst.resume_file, "rb") as _data:
                operation_plan, operation_data = pickle.load(_data)
                if instruct["skip-first"]:
                    operation_plan = operation_plan[1:]

                if not operation_plan:
                    out.error("resume failed! package query not found.")
                    lpms.terminate()
        else:
            out.error("%s not found" % resume_file)
            lpms.terminate()

    count = len(operation_plan); i = 1
    if instruct["pretend"] or instruct["ask"]:
        out.write("\n")
        out.normal("these packages will be merged, respectively:\n")
        for atom in operation_plan:
            valid_options = operation_data[atom][-1]
            repo, category, name, version  = atom
            options = dbapi.RepositoryDB().get_options(repo, category, name, version)[version]
            show_plan(repo, category, name, version, valid_options, options)

        if instruct["pretend"]:
            lpms.terminate()

        utils.xterm_title("lpms: confirmation request")
        out.write("\nTotal %s package will be merged.\n\n" % out.color(str(count), "green"))
        if not utils.confirm("do you want to continue?"):
            out.write("quitting...\n")
            utils.xterm_title_reset()
            lpms.terminate()

    # resume feature
    # create a resume list. write package data(repo, category, name, version) to 
    # /var/tmp/lpms/resume file.
    if not instruct["resume"] or instruct["skip-first"]:
        if os.path.exists(cst.resume_file):
            shelltools.remove_file(cst.resume_file)
        with open(cst.resume_file, "wb") as _data:
            pickle.dump(raw_data, _data)

    for plan in operation_plan:
        opr = Build()
        setattr(opr.env, 'todb', operation_data[plan][0])
        setattr(opr.env, 'valid_opts', operation_data[plan][1])

        operation_data[plan]
        keys = {'repo':0, 'category':1, 'pkgname':2, 'version':3}
        for key in keys:
            setattr(opr.env, key, plan[keys[key]])

        # FIXME:
        opr.env.name = opr.env.pkgname
        opr.env.fullname = opr.env.pkgname+"-"+opr.env.version
        opr.env.spec_file = os.path.join(cst.repos, opr.env.repo, 
                opr.env.category, opr.env.pkgname, opr.env.pkgname)+"-"+opr.env.version+cst.spec_suffix
        opr.env.__dict__.update(instruct)
        opr.env.default_options = opr.config.options.split(" ")

        opr.compile_script()
        
        metadata = utils.metadata_parser(opr.env.metadata)
        for attr in ('options', 'summary', 'license', 'homepage', 'slot', 'arch'):
            try:
                setattr(opr.env, attr, metadata[attr])
            except KeyError:
                # slot?
                if attr == "slot":
                    setattr(opr.env, attr, "0")
                # arch
                elif attr == "arch":
                    setattr(opr.env, attr, None)

        setattr(opr.env, "i", i)
        setattr(opr.env, "count", count)
        setattr(opr.env, "filesdir", os.path.join(cst.repos, opr.env.repo, 
            opr.env.category, opr.env.pkgname, cst.files_dir))

        # FIXME: This is no good!
        ####################################
        if opr.env.options is None:
            opr.env.options = []

        if opr.env.valid_opts is None:
            opr.env.valid_opts = []
        ####################################

        if "src_url" in metadata:
            opr.env.src_url = metadata["src_url"]
        else:
            if not "src_url" in opr.env.__dict__.keys():
                opr.env.src_url = None

        if not "srcdir" in opr.env.__dict__:
            setattr(opr.env, "srcdir", opr.env.fullname)
        opr.prepare_environment()

        # start logging
        # we want to save starting time of the build operation
        lpms.logger.info("starting build (%s/%s) %s/%s/%s-%s" % (i, count, opr.env.repo, 
            opr.env.category, opr.env.name, opr.env.version))

        out.normal("(%s/%s) building %s/%s from %s" % (i, count,
            out.color(opr.env.category, "green"),
            out.color(opr.env.pkgname+"-"+opr.env.version, "green"), opr.env.repo)); i += 1

        out.notify("you are using %s userland and %s kernel" % (opr.config.userland, opr.config.kernel))

        if opr.env.sandbox:
            lpms.logger.info("sandbox enabled build")
            out.notify("sandbox is enabled")
        else:
            lpms.logger.warning("sandbox disabled build")
            out.warn_notify("sandbox is disabled")

        # fetch packages which are in download_plan list
        if opr.env.src_url is not None:
            opr.parse_url_tag()

            utils.xterm_title("lpms: downloading %s/%s/%s-%s" % (opr.env.repo, opr.env.category,
                opr.env.name, opr.env.version))
            
            opr.prepare_download_plan(opr.env.valid_opts)
            
            if not fetcher.URLFetcher().run(opr.download_plan):
                lpms.catch_error("\nplease check the spec")

            utils.xterm_title("lpms: extracting %s/%s/%s-%s" % (opr.env.repo, opr.env.category,
                opr.env.name, opr.env.version))

            opr.extract_sources()
            if opr.env.stage == "unpack":
                lpms.terminate()

        if opr.env.valid_opts is not None and len(opr.env.valid_opts) != 0:
            out.notify("applied options: %s" % 
                    " ".join(opr.env.valid_opts))
        
        os.chdir(opr.env.build_dir)
        if not interpreter.run(opr.env.spec_file, opr.env):
            lpms.terminate("errors occured :(")
            
        lpms.logger.info("finished %s/%s/%s-%s" % (opr.env.repo, opr.env.category, 
            opr.env.name, opr.env.version))

        utils.xterm_title("lpms: %s/%s finished" % (opr.env.category, opr.env.pkgname))
        #merge.main(opr.env)
        out.notify("cleaning build directory...\n")
        shelltools.remove_dir(os.path.dirname(opr.env.install_dir))
        catdir = os.path.dirname(os.path.dirname(opr.env.install_dir))
        if catdir:
            shelltools.remove_file(catdir)

        # resume feature
        # delete package data, if it is installed successfully
        with open(cst.resume_file, "rb") as _data:
            resume_plan, resume_data = pickle.load(_data)
        data = []

        for pkg in resume_plan:
            if pkg != (opr.env.repo, opr.env.category, 
                    opr.env.name, opr.env.version):
                data.append(pkg)

        shelltools.remove_file(cst.resume_file)
        with open(cst.resume_file, "wb") as _data:
            pickle.dump((data, resume_data), _data)

        opr.env.__dict__.clear()
        utils.xterm_title_reset()

def show_plan(repo, category, name, version, valid_options, options):
    result = []; status = [' ', '  ']; oldver= ""

    instdb = dbapi.InstallDB()
    repodb = dbapi.RepositoryDB()

    pkgdata = instdb.find_pkg(name, pkg_category=category)

    #ivers = []
    #if pkgdata:
    #    map(lambda ver: ivers.extend(ver), pkgdata[-1].values())

    if (category, name) == pkgdata[1:-1]:
        repovers = repodb.get_version(name, pkg_category = category)

        for key in repovers:
            if version in repovers[key]:
                try:
                    instver = pkgdata[-1][key][0]
                    cmpres = utils.vercmp(version, instver)
                    if cmpres == 1:
                        status[0] = out.color("U", "brightgreen")
                        oldver = "["+out.color(instver, "brightgreen")+"]"
                    elif cmpres == 0:
                        status[0] = out.color("R", "brightyellow")
                    elif cmpres == -1:
                        status[0] = out.color("D", "brightred")
                        oldver = "["+out.color(instver, "brightred")+"]"
                except KeyError:
                    status[-1] = out.color("NS", "brightgreen")
    else:
        status[0] = out.color("N", "brightgreen")


    out.write("[%s] %s/%s/%s-%s %s " % (" ".join(status), out.color(repo, "green"), out.color(category, "green"), 
        out.color(name, "green"), out.color(version, "green"), oldver))
    
    if options:
        try:
            irepo = instdb.get_repo(category, name, version)
            instopts = instdb.get_options(irepo, category, name, version)[version].split(" ")
        except (KeyError, TypeError):
            instopts = None

        for o in options.split(" "):
            if valid_options and o in valid_options:
                if instopts and not o in instopts:
                    result.insert(0, out.color(o+"*", "brightgreen"))
                    continue
                result.insert(0, out.color(o, "red"))
            else:
                if instopts and o in instopts:
                    result.insert(len(result)+1, "-"+out.color(o+"*", "brightyellow"))
                    continue
                result.insert(len(result)+1, "-"+o)

        out.write("("+" ".join(result)+")")

    out.write("\n")

