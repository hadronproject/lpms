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

import lpms

from lpms import out
from lpms import conf
from lpms import utils

from lpms.db import dbapi

#################################################################
# 
# Dependency resolver for lpms. Some parts from RADLogic.
#   * http://www.radlogic.com
#   * http://www.radlogic.com/releases/topsort.py
#
# I used topological sorting algorithm for resolving dependencies.
# 
# The piece of code that relevants with lpms, I have written it.
#                                                       
# purak
#
#################################################################
"""Provide toplogical sorting (i.e. dependency sorting) functions.

The topsort function is based on code posted on Usenet by Tim Peters.

Modifications:
- added doctests
- changed some bits to use current Python idioms
  (listcomp instead of filter, +=/-=, inherit from Exception)
- added a topsort_levels version that ports items in each dependency level
  into a sub-list
- added find_cycles to aid in cycle debugging

Run this module directly to run the doctests (unittests).
Make sure they all pass before checking in any modifications.

Requires Python >= 2.2
(For Python 2.2 also requires separate sets.py module)

This requires the rad_util.py module.

"""

__version__ = '$Revision: 0.9 $'
__date__ = '$Date: 2007/03/27 04:15:26 $'
__credits__ = '''Tim Peters -- original topsort code
Tim Wegener -- doctesting, updating to current idioms, topsort_levels,
               find_cycles
'''

class CycleError(Exception):
    """Cycle Error"""
    pass

class UnmetDependency(Exception):
    pass

def is_rotated(seq1, seq2):
    """Return true if the first sequence is a rotation of the second sequence.

    >>> seq1 = ['A', 'B', 'C', 'D']
    >>> seq2 = ['C', 'D', 'A', 'B']
    >>> int(is_rotated(seq1, seq2))
    1

    >>> seq2 = ['C', 'D', 'B', 'A']
    >>> int(is_rotated(seq1, seq2))
    0

    >>> seq1 = ['A', 'B', 'C', 'A']
    >>> seq2 = ['A', 'A', 'B', 'C']
    >>> int(is_rotated(seq1, seq2))
    1

    >>> seq2 = ['A', 'B', 'C', 'A']
    >>> int(is_rotated(seq1, seq2))
    1

    >>> seq2 = ['A', 'A', 'C', 'B']
    >>> int(is_rotated(seq1, seq2))
    0

    """
    # Do a sanity check.
    if len(seq1) != len(seq2):
        return False
    # Look for occurrences of second sequence head item in first sequence.
    start_indexes = []
    head_item = seq2[0]
    for index1 in range(len(seq1)):
        if seq1[index1] == head_item:
            start_indexes.append(index1)
    # Check that wrapped sequence matches.
    double_seq1 = seq1 + seq1
    for index1 in start_indexes:
        if double_seq1[index1:index1+len(seq1)] == seq2:
            return True
    return False


def topsort(pairlist):
    """Topologically sort a list of (parent, child) pairs.

    Return a list of the elements in dependency order (parent to child order).

    >>> print topsort( [(1,2), (3,4), (5,6), (1,3), (1,5), (1,6), (2,5)] )
    [1, 2, 3, 5, 4, 6]

    >>> print topsort( [(1,2), (1,3), (2,4), (3,4), (5,6), (4,5)] )
    [1, 2, 3, 4, 5, 6]

    >>> print topsort( [(1,2), (2,3), (3,2)] )
    Traceback (most recent call last):
    CycleError: ([1], {2: 1, 3: 1}, {2: [3], 3: [2]})

    """
    num_parents = {}  # element -> # of predecessors
    children = {}  # element -> list of successors
    for parent, child in pairlist:
        # Make sure every element is a key in num_parents.
        if not parent in num_parents:
            num_parents[parent] = 0
        if not child in num_parents:
            num_parents[child] = 0

        # Since child has a parent, increment child's num_parents count.
        num_parents[child] += 1

        # ... and parent gains a child.
        children.setdefault(parent, []).append(child)

    # Suck up everything without a parent.
    answer = [x for x in num_parents.keys() if num_parents[x] == 0]

    # For everything in answer, knock down the parent count on its children.
    # Note that answer grows *in* the loop.
    for parent in answer:
        del num_parents[parent]
        if parent in children:
            for child in children[parent]:
                num_parents[child] -= 1
                if num_parents[child] == 0:
                    answer.append( child )
            # Following "del" isn't needed; just makes
            # CycleError details easier to grasp.
            #del children[parent]

    if num_parents:
        # Everything in num_parents has at least one child ->
        # there's a cycle.
        raise CycleError(answer, num_parents, children)
    return answer

def topsort_levels(pairlist):
    """Topologically sort a list of (parent, child) pairs into depth levels.

    This returns a generator.
    Turn this into a an iterator using the iter built-in function.
    (if you iterate over the iterator, each element gets generated when
    it is asked for, rather than generating the whole list up-front.)

    Each generated element is a list of items at that dependency level.

    >>> dependency_pairs = [(1,2), (3,4), (5,6), (1,3), (1,5), (1,6), (2,5)]
    >>> for level in iter(topsort_levels( dependency_pairs )):
    ...    print level
    [1]
    [2, 3]
    [4, 5]
    [6]

    >>> dependency_pairs = [(1,2), (1,3), (2,4), (3,4), (5,6), (4,5)]
    >>> for level in iter(topsort_levels( dependency_pairs )):
    ...    print level
    [1]
    [2, 3]
    [4]
    [5]
    [6]

    >>> dependency_pairs = [(1,2), (2,3), (3,4), (4, 3)]
    >>> try:
    ...     for level in iter(topsort_levels( dependency_pairs )):
    ...         print level
    ... except CycleError, exc:
    ...     print 'CycleError:', exc
    [1]
    [2]
    CycleError: ({3: 1, 4: 1}, {3: [4], 4: [3]})


    The cycle error should look like.
    CycleError: ({3: 1, 4: 1}, {3: [4], 4: [3]})
    # todo: Make the doctest more robust (i.e. handle arbitrary dict order).

    """
    num_parents = {}  # element -> # of predecessors
    children = {}  # element -> list of successors
    for parent, child in pairlist:
        # Make sure every element is a key in num_parents.
        if not parent in num_parents:
            num_parents[parent] = 0
        if not child in num_parents:
            num_parents[child] = 0

        # Since child has a parent, increment child's num_parents count.
        num_parents[child] += 1

        # ... and parent gains a child.
        children.setdefault(parent, []).append(child)

    return topsort_levels_core(num_parents, children)

def topsort_levels_core(num_parents, children):
    """Topologically sort a bunch of interdependent items based on dependency.

    This returns a generator.
    Turn this into a an iterator using the iter built-in function.
    (if you iterate over the iterator, each element gets generated when
    it is asked for, rather than generating the whole list up-front.)

    Each generated element is a list of items at that dependency level.

    >>> list(topsort_levels_core(
    ...          {1: 0, 2: 1, 3: 1, 4: 1, 5: 2, 6: 2},
    ...          {1: [2, 3, 5, 6], 2: [5], 3: [4], 4: [], 5: [6]}))
    [[1], [2, 3], [4, 5], [6]]

    >>> list(topsort_levels_core(
    ...          {1: 0, 2: 2, 3: 1},
    ...          {1: [2], 2: [3], 3: [2]}))
    Traceback (most recent call last):
    CycleError: ({2: 1, 3: 1}, {2: [3], 3: [2]})

    This function has a more complicated interface than topsort_levels,
    but is useful if the data is easier to generate in this form.

    Arguments:
    num_parents -- key: item, value: number of parents (predecessors)
    children -- key: item, value: list of children (successors)

    """
    while 1:
        # Suck up everything without a predecessor.
        level_parents = [x for x in num_parents.keys() if num_parents[x] == 0]

        if not level_parents:
            break

        # Offer the next generated item,
        # which is a list of the items at this dependency level.
        yield level_parents

        # For everything item in this level,
        # decrement the parent count,
        # since we have accounted for its parent.
        for level_parent in level_parents:

            del num_parents[level_parent]

            if level_parent in children:
                for level_parent_child in children[level_parent]:
                    num_parents[level_parent_child] -= 1
                del children[level_parent]

    if num_parents:
        # Everything in num_parents has at least one child ->
        # there's a cycle.
        raise CycleError(num_parents, children)
    else:
        # This is the end of the generator.
        raise StopIteration


def find_cycles(parent_children):
    """Yield cycles. Each result is a list of items comprising a cycle.

    Use a 'stack' based approach to find all the cycles.
    This is a generator, so yields each cycle as it finds it.

    It is implicit that the last item in each cycle list is a parent of the
    first item (thereby forming a cycle).

    Arguments:
    parent_children -- parent -> collection of children

    Simplest cycle:
    >>> cycles = list(find_cycles({'A': ['B'], 'B': ['A']}))
    >>> len(cycles)
    1
    >>> cycle = cycles[0]
    >>> cycle.sort()
    >>> print cycle
    ['A', 'B']

    Simplest cycle with extra baggage at the start and the end:
    >>> cycles = list(find_cycles(parent_children={'A': ['B'],
    ...                                            'B': ['C'],
    ...                                            'C': ['B', 'D'],
    ...                                            'D': [],
    ...                                            }))
    >>> len(cycles)
    1
    >>> cycle = cycles[0]
    >>> cycle.sort()
    >>> print cycle
    ['B', 'C']

    Double cycle:
    >>> cycles = list(find_cycles(parent_children={'A': ['B'],
    ...                                            'B': ['C1', 'C2'],
    ...                                            'C1': ['D1'],
    ...                                            'D1': ['E1'],
    ...                                            'E1': ['D1'],
    ...                                            'C2': ['D2'],
    ...                                            'D2': ['E2'],
    ...                                            'E2': ['D2'],
    ...                                            }))
    >>> len(cycles)
    2
    >>> for cycle in cycles:
    ...     cycle.sort()
    >>> cycles.sort()
    >>> cycle1 = cycles[0]
    >>> cycle1.sort()
    >>> print cycle1
    ['D1', 'E1']
    >>> cycle2 = cycles[1]
    >>> cycle2.sort()
    >>> print cycle2
    ['D2', 'E2']

    Simple cycle with children not specified for one item:
    # todo: Should this barf instead?
    >>> cycles = list(find_cycles(parent_children={'A': ['B'],
    ...                                            'B': ['A'],
    ...                                            'C': ['D']}))
    >>> len(cycles)
    1
    >>> cycle = cycles[0]
    >>> cycle.sort()
    >>> print cycle
    ['A', 'B']

    Diamond cycle
    >>> cycles = list(find_cycles(parent_children={'A': ['B1', 'B2'],
    ...                                            'B1': ['C'],
    ...                                            'B2': ['C'],
    ...                                            'C': ['A', 'B1']}))
    >>> len(cycles)
    3
    >>> sorted_cycles = []
    >>> for cycle in cycles:
    ...     cycle = list(cycle)
    ...     cycle.sort()
    ...     sorted_cycles.append(cycle)
    >>> sorted_cycles.sort()
    >>> for cycle in sorted_cycles:
    ...     print cycle
    ['A', 'B1', 'C']
    ['A', 'B2', 'C']
    ['B1', 'C']

    Hairy case (order can matter if something is wrong):
    (Note order of B and C in the list.)
    >>> cycles = list(find_cycles(parent_children={
    ...                                           'TD': ['DD'],
    ...                                           'TC': ['DC'],
    ...                                           'DC': ['DQ'],
    ...                                           'C': ['DQ'],
    ...                                           'DQ': ['IA', 'TO'],
    ...                                           'IA': ['A'],
    ...                                           'A': ['B', 'C'],
    ...                                           }))
    >>> len(cycles)
    1
    >>> cycle = cycles[0]
    >>> cycle.sort()
    >>> print cycle
    ['A', 'C', 'DQ', 'IA']

    """
    cycles = []
    visited_nodes = set()

    for parent in parent_children:
        if parent in visited_nodes:
            # This node is part of a path that has already been traversed.
            continue

        paths = [[parent]]
        while paths:
            path = paths.pop()

            parent = path[-1]

            try:
                children = parent_children[parent]
            except KeyError:
                continue

            for child in children:
                # Keeping a set of the path nodes, for O(1) lookups at the
                # expense of more memory and complexity, actually makes speed
                # worse. (Due to construction of sets.)
                # This is O(N).
                if child in path:
                    # This is a cycle.
                    cycle = path[path.index(child):]
                    # Check that this is not a dup cycle.
                    is_dup = False
                    for other_cycle in cycles:
                        if is_rotated(other_cycle, cycle):
                            is_dup = True
                            break
                    if not is_dup:
                        cycles.append(cycle)
                        yield cycle
                else:
                    # Push this new path onto the 'stack'.
                    # This is probably the most expensive part of the algorithm
                    # (a list copy).
                    paths.append(path + [child])
                    # Mark the node as visited.
                    visited_nodes.add(child)


class DependencyResolver(object):
    def __init__(self):
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()
        self.operation_data = {}
#        self.valid_opts = []
        self.plan = {} 
        self.current_package = None
        self.package_query = []
        self.config = conf.LPMSConfig()
        
    def package_select(self, data):
        #print data
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
            category, name = data.split("/")
            versions = []
            version_data = self.repodb.find_pkg(name, pkg_category=category, selection = True)
            if not version_data:
                out.error("unmet dependency for %s: %s" % ("/".join(self.current_package[:-1])+\
                        "-"+self.current_package[-1], data))
                lpms.terminate()

            if isinstance(version_data, list):
                version_data = version_data[-1]

           # FIXME: fix db.get_version and use it
            map(lambda ver: versions.extend(ver), version_data[-1].values())
            return category, name, utils.best_version(versions)

        name, version = utils.parse_pkgname(pkgname)
        category, name = name.split("/")
        result = []
        repo = self.repodb.find_pkg(name, pkg_category=category, selection = True)
        if not repo:
            out.error("unmet dependency for %s: %s" % ("/".join(self.current_package[:-1])+\
                    "-"+self.current_package[-1], pkgname))
            lpms.terminate()
            #raise UnmetDependency(pkgname)

        if slot == 0:
            versions = []
            # FIXME: because of our database :'(
            if isinstance(repo, list):
                repo = repo[0]
            try:
                map(lambda v: versions.extend(v), repo[-1].values())
            except AttributeError:
                # FIXME: What the fuck?
                print(data)
        else:
            versions = repo[-1][slot]

        for rv in versions:
            vercmp = utils.vercmp(rv, version) 
            if lt:
                if vercmp == -1:
                    result.append(rv)
            elif gt:
                if vercmp == 1 or vercmp == 0:
                    result.append(rv)
            elif lte:
                if vercmp == -1 or vercmp == 0:
                    result.append(rv)
            elif gte:
                version = version.strip()
                if utils.vercmp(rv, version) == 1 or utils.vercmp(rv, version) == 0:
                    result.append(rv)
            elif et:
                if vercmp == 0:
                    return category, name, rv

        return category, name, utils.best_version(result)

    def opt_parser(self, data):
        data = list(data)
        if "[" in data:
            first_index = data.index("[")
            try:
                end_index = data.index("]")
            except ValueError:
                out.error("%s -- ']' not found in package name" % "".join(data))
                lpms.terminate()

            opt = "".join(data[first_index+1:end_index])
            return "".join(data[:first_index]), opt.strip().split(" ")
        
        return "".join(data)

    def fix_dynamic_deps(self, data, options):
        depends = []
        for opt in options:
            prev_indent_level = 0
            if opt in data:
                deps = data[opt]
                for dep in deps:
                    if isinstance(dep, str):
                        depends.append(dep)
                    elif isinstance(dep, tuple):
                        subopt, subdep = dep
                        if subopt.count("\t") == 1:
                            if subopt.strip() in options:
                                prev_indent_level = 1
                                depends.extend(subdep)
                        elif subopt.count("\t") - 1 == prev_indent_level:
                            if subopt.strip() in options:
                                prev_indent_level = subopt.count("\t")
                                depends.extend(subdep)
        return depends

    def parse_package_name(self, data):
        #try:
        try:
            name, opts = self.opt_parser(data)
        except ValueError:
            return self.package_select(data), []
        else:
            return self.package_select(name), opts
        #except UnmetDependency as err:
        #    print err
        #    print "burak"

    def get_repo(self, data):
        if len(data) == 2:
            category, name = data
            return self.repodb.get_repo(category, name)
        elif len(data) == 3:
            category, name, version = data
            return self.repodb.get_repo(category, name, version)
        elif len(data) == 4:
            category, name, version = data[:-1]
            return self.repodb.get_repo(category, name, version)

    def collect(self, repo, category, name, version, options):
        dependencies = self.repodb.get_depends(repo, category, name, version)

        # FIXME: ???
        if not dependencies:
            lpms.terminate()

        local_plan = {"build":[], "runtime": []}

        for key in ('build', 'runtime'):
            dynamic_deps = [dep for dep in dependencies[key] if isinstance(dep, dict)]
            if dynamic_deps:
                for dyn_dep in self.fix_dynamic_deps(dynamic_deps[0], options):
                    dyn_package_data = self.parse_package_name(dyn_dep)
                    dyn_dep_repo = self.get_repo(dyn_package_data[0])
                    (dcategory, dname, dversion), dopt = dyn_package_data
                    local_plan[key].append((dyn_dep_repo, dcategory, dname, dversion, dopt))

            static_deps = " ".join([dep for dep in dependencies[key] if isinstance(dep, str)])

            if static_deps:
                for stc_dep in static_deps.split(" "):
                    stc_package_data = self.parse_package_name(stc_dep)
                    stc_dep_repo = self.get_repo(stc_package_data[0])
                    (scategory, sname, sversion), sopt = stc_package_data
                    local_plan[key].append((stc_dep_repo, scategory, sname, sversion, sopt))

        self.operation_data.update({(repo, category, name, version): (local_plan, options)})

        def fix_opts():
            for o in lopt:
                if not o in current_opts: return True

        for local_data in local_plan.values():
            if local_data:
                for local in local_data:
                    lrepo, lcategory, lname, lversion, lopt = local
                    fullname = (lrepo, lcategory, lname, lversion)
                    self.package_query.append(((repo, category, name, version), fullname))
                    if fullname in self.plan:
                        current_version, current_opts = self.plan[fullname]
                        if not fix_opts() or lversion != current_version:
                            continue

                    self.plan.update({fullname: (lversion, lopt)})
                    self.collect(lrepo, lcategory, lname, lversion, lopt)

    def resolve_depends(self, packages):
        for pkg in packages:
            self.current_package = pkg
            given_repo, given_category, given_name, given_version = pkg
            self.collect(given_repo, given_category, given_name, given_version, [])

        if not self.package_query or lpms.getopt("--ignore-depends"):
            return packages, self.operation_data

        plan = []
        try:
            for pkg in topsort(self.package_query):
                repo, category, name, version = pkg
                
                if (repo, category, name, version) in packages:
                    plan.append(pkg)
                    continue

                data = self.instdb.find_pkg(name, pkg_category = category)
                if data:
                    versions = []
                    map(lambda ver: versions.extend(ver), data[-1].values())
                    if not version in versions:
                        plan.append(pkg)
                    else:
                        if not pkg in packages:
                            del self.operation_data[pkg]
                else:
                    plan.append(pkg)

            plan.reverse()
            return plan, self.operation_data

        except CycleError as err:
            answer, num_parents, children = err
            for cycle in find_cycles(parent_children=children):
                out.brightred("Circular Dependency:\n")
                out.write(cycle+"\n\n")
