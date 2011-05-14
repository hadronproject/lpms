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

# dependency resolver

import lpms

from lpms import out
from lpms import conf
from lpms import utils

from lpms.db import dbapi

# TODO:
# 1- kodu internals.py'ye bagla, bazi degiskenlerin bu noktada atamasi yapilabilir mi?[IPTAL]
# 2- surumler konusunda secici olunmasini sagla. su an otomatik olarak en yuksek versiyon kullaniliyor.[TAMAMLANDI]
# 3- kod biraz daha kisaltilip temizlenebilir.
# 4- preprocessor kodu daha iyi olabilir mi?

def preprocessor(data):
    '''A function that preprocess dependency data which from database or spec
    scripts. It returns a list and dictonary that contain dependencies'''

    # I know, the code is ugly, but it works!
    optional = {}; opt = None; deps = []
    for line in data:
        if '(' in list(line):
            atom = line.split('(')
            if len(atom[1].split(')')) == 2:
                optional[atom[0]] = []
                optional[atom[0]].extend(atom[1].split(')')[0].strip().split(' '))
            else:
                opt = atom[0]
                optional[opt] = [atom[1].split(' ')]
        elif ')' in list(line):
            atom = line.split(')')
            optional[opt].append(atom[0])
        else:
            deps.extend(line.split(' '))
    return optional, deps

class DependencyResolver(object):
    def __init__(self):
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()
        self.operation_plan = {}
        self.valid_opts = []
        self.count = {}
        self.plan = []
        self.control = {}
        self.config = conf.LPMSConfig()
        
    def version_selector(self, data):
        slot = 0
        gte, lte, lt, gt = False, False, False, False
        slot_parsed = data.split(":")
        if len(slot_parsed) == 2:
            data, slot = slot_parsed
            
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
            return False

        name, version = utils.parse_pkgname(pkgname)
        category, name = name.split("/")

        result = []
        repo = self.repodb.find_pkg(name, pkg_category=category)
        if slot == 0:
            versions = []
            map(lambda v: versions.extend(v), repo[-1].values())
        else:
            versions = repo[-1][slot]

        for rv in versions:
            if lt:
                if utils.vercmp(rv, version) == -1:
                    result.append(rv)
            elif gt:
                if utils.vercmp(rv, version) == 1:
                    result.append(rv)
            elif lte:
                if utils.vercmp(rv, version) == -1 or utils.vercmp(rv, version) == 0:
                    result.append(rv)
            elif gte:
                version = version.strip()
                if utils.vercmp(rv, version) == 1 or utils.vercmp(rv, version) == 0:
                    result.append(rv)
            elif et:
                if utils.vercmp(rv, version) == 0:
                    return rv
        return category, name, utils.best_version(result)

    def fix_connections(self):
        for node in self.operation_plan:
            i = 0
            for node2 in self.operation_plan:
                aq = []
                map(lambda x: aq.extend(x), self.operation_plan[node2][0])
                if node in aq:
                    i += 1
                self.count[node] = i

    def topological_sort(self):
        ready = [ node for node in self.operation_plan if self.count[node] == 0 ]
        while ready:
            node = ready.pop(-1)
            category, name = node.split('/')
            opts, version, repo, todb = self.operation_plan[node][1:] 
            self.plan.append((repo, category, name, version, opts, todb))
            for successor in self.operation_plan[node][0]:
                self.count[successor[0]] -= 1
                if self.count[successor[0]] == 0:
                    ready.append(successor[0])

    def collect(self, repo, category, name, version, cmd_options):
        options = self.repodb.get_options(repo, category, name, 
                version)[version]
        # catpkg: $category+"/"+name
        catpkg = category+"/"+name

        # collects 'option' info
        default_options = self.config.options.split(" ")
        valid_opts = utils.set_valid_options(options, cmd_options, default_options)
        
        depends = self.repodb.get_depends(repo, category, name, version)

        if catpkg in self.control:
            if valid_opts is None:
                valid_opts = self.control[catpkg]
            else:
                valid_opts.extend(self.control[catpkg])

        local_plan = []
        todb = {}

        for dep_type in depends:
            dynamic, static = preprocessor(depends[dep_type])
            if dynamic:
                for dyn in dynamic:
                    if '/' in dyn:
                        selected = self.version_selector(dyn)
                        if not selected:
                            # package version is not specified.
                            depcat, depname = dyn.split('/')
                            found = self.instdb.find_pkg(depname, pkg_category=depcat)
                            # if 'found' is False, the package is not installed.
                            if found:
                                # the package is already installed.
                                repo, rversions = found[0], found[-1]
                            else:
                                # pkg is not installed. lpms will find out it in repository.
                                rfound = self.repodb.find_pkg(depname, pkg_category=depcat)
                                repo , rversions = rfound[0], rfound[-1]
                            versions = []
                            map(lambda v: versions.extend(v), rversions.values())
                            depver = utils.best_version(versions)
                        else:
                            # package version is specified in the spec.
                            depcat, depname, depver = selected
                            repo = self.instdb.get_repo(depcat, depname)

                        if depver is None:
                            out.error("%s: unsatisfied dependency for %s" % (out.color(dyn, "red"), 
                                out.color(category+"/"+name, "red")))
                            lpms.terminate()

                        installed_opts = self.instdb.get_options(repo, depcat, depname, depver)
                        if installed_opts is not None and depver in installed_opts:
                            ctn = False
                            for opt in dynamic[dyn]:
                                if not opt in installed_opts[depver].split(' '):
                                    ctn = True
                            if not ctn:
                                continue
                        if not dyn in self.control:
                            self.control.update({depcat+"/"+depname: []})
                        for opt in dynamic[dyn]:
                            if not opt in self.control[depcat+"/"+depname]:
                                self.control[depcat+"/"+depname].append(opt)
                        local_plan.append((depcat+"/"+depname, depver))
                    else:
                        if valid_opts is not None and dyn in valid_opts:
                            local_plan.extend(dynamic[dyn])

            if static:
                for atom in static:
                    selected = self.version_selector(atom)
                    if not selected:
                        depcat, depname = atom.split('/')
                        found = self.instdb.find_pkg(depname, pkg_category=depcat)
                        if not found:
                            local_plan.append((atom, None))
                    else:
                        depcat, depname, depver = selected
                        local_plan.append((depcat+"/"+depname, depver))
            todb[dep_type] = list(set(local_plan))

        local_plan = list(set(local_plan))
        self.operation_plan.update({catpkg: [local_plan, valid_opts, version, repo, todb]})

        if local_plan:
            for dep, depver in local_plan:
                cat, pkgname = dep.split('/')
                result = self.repodb.find_pkg(pkgname, pkg_category=cat, selection = True)
                if not result:
                    out.error("%s : unsatisfied dependency for %s" % (out.color(dep, "red"), 
                        out.color(category+"/"+name, "red")))
                    lpms.terminate()

                if depver is None:
                    versions = []
                    map(lambda x: versions.extend(x), result[-1].values())
                    depver = utils.best_version(versions)
                self.collect(result[0], cat, pkgname, depver, cmd_options)
