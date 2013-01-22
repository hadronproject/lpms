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
import xml.etree.cElementTree as iks

import lpms
from lpms import out
from lpms import conf
from lpms import utils
from lpms import fetcher
from lpms import shelltools
from lpms import constants as cst

app_name = "lhashgen"
app_version = "0.1"

class Generate(object):
    def __init__(self, current_dir, files):
        self.current_dir = current_dir
        self.repo_path = None
        self.files = files

    def parse_categories(self):
        for i in iks.iterparse(os.path.join(self.repo_path, cst.repo_info, cst.categories)):
            if i[1].tag == "category":
                yield(i[1].attrib["name"])

    def check_repo_dir(self):
        parsed = self.current_dir.split("/")
        self.repo_path = "/".join(parsed[:-2])
        repo_file = os.path.join(self.repo_path, cst.repo_file)
        if not os.path.isfile(repo_file):
            lpms.terminate("%s not found!" % repo_file)

        f = len(filter(lambda x: x == parsed[-2], self.parse_categories()))
        if f > 1:
            lpms.terminate("there are more than one \'%s\' entry in %s. You should remove one of them." 
                    % (parsed[-2], cst.categories))
        elif f == 0:
            lpms.terminate("\'%s\' seems an invalid category." % parsed[-2])

        specs = glob.glob("*"+cst.spec_suffix)
        if len(specs) == 0:
            lpms.terminate("there are no spec file in %s." % self.current_dir)

    def calculate_hashes(self):
        def write_archive_hash(urls, file_name):
            name, version = utils.parse_pkgname(file_name)
            for url in utils.parse_url_tag(urls, name, version):
                archive_name = os.path.basename(url)
                archive_path = os.path.join(conf.LPMSConfig().src_cache, archive_name)
                if not os.access(archive_path, os.F_OK):
                    fetcher.URLFetcher().run([url])
                sha1 = utils.sha1sum(archive_path)
                shelltools.echo("hashes", "%s %s %s" % (archive_name, sha1, os.path.getsize(archive_path)))

        excepts = ('hashes')
        shelltools.remove_file("hashes")
        if len(self.files) == 0:
            self.files = os.listdir(self.current_dir)

        for f in self.files:
            if f in excepts:
                continue
            if f.endswith(cst.spec_suffix):
                out.normal("processing %s" % f)
                shelltools.echo("hashes", "%s %s %s" % (f, utils.sha1sum(f), os.path.getsize(f)))
                content = utils.import_script(f)
                if "src_url" in utils.metadata_parser(content["metadata"]).keys():
                    write_archive_hash(utils.metadata_parser(content["metadata"])["src_url"], f)
                elif "src_url" in content.keys():
                    write_archive_hash(content["src_url"], f)
                else:
                    lpms.terminate("src_url was not defined in spec")
                del content
            elif os.path.isdir(f):
                for l in os.listdir(os.path.join(self.current_dir, f)):
                    path = os.path.join(f, l)
                    out.normal("processing %s" % path)
                    shelltools.echo("hashes", "%s %s %s" %  (path, utils.sha1sum(path), os.path.getsize(path)))


def usage():
    out.normal("A tool that creates \'hashes\' file for lpms packages.")
    out.green("General Usage:\n")
    out.write(" $ lhashgen <spec name>\n")
    out.write("\nIf you do not give any package name with command, it scans the directory and operates all valid specs\n")
    out.write("\nUse \'--version\' to see program's version\n")
    lpms.terminate()

def main(files):
    opr = Generate(os.getcwd(), files)
    if "--help" in files:
        usage()
    elif "--version" in files:
        out.write("%s-%s\n" % (app_name, app_version))
    opr.check_repo_dir()
    opr.calculate_hashes()
