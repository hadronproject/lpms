import os

import lpms

from lpms import out
from lpms import conf
from lpms import utils
from lpms import constants as cst

from lpms.db import dbapi

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
        self.modified_by_package = []
        self.repodb = dbapi.RepositoryDB()
        self.instdb = dbapi.InstallDB()
        self.operation_data = {}
        self.valid_opts = []
        self.plan = {} 
        self.current_package = None
        self.special_opts = None
        self.package_query = []
        self.global_options = []
        self.config = conf.LPMSConfig()
        self.single_pkgs = []
        self.udo = {}
        self.get_user_defined_files()

    def get_user_defined_files(self):
        for user_defined_file in cst.user_defined_files:
            if not os.access(user_defined_file, os.W_OK):
                continue
            with open(user_defined_file) as data:
                data = [line.strip() for line in data.readlines() \
                        if line != "#"]
            setattr(self, "user_defined_"+os.path.basename(user_defined_file), data)

    def parse_user_defined_options_file(self):
        if not hasattr(self, "user_defined_options"):
            return

        for user_defined_option in self.user_defined_options:
            category, name, versions, opts = self.parse_user_defined_file(user_defined_option, True)
            self.udo.update({(category, name):(versions, opts)})

    def parse_user_defined_file(self, data, opt=False):
        user_defined_options = None
        if opt:
            data = data.split(" ", 1)
            if len(data) > 1:
                data, user_defined_options = data
                user_defined_options = [atom.strip() for atom in \
                        user_defined_options.strip().split(" ")]
            else:
                data = data[0]
        affected = []
        slot = None
        slot_parsed = data.split(":")
        if len(slot_parsed) == 2:
            data, slot = slot_parsed

        def parse(pkgname):
            category, name = pkgname.split("/")
            name, version = utils.parse_pkgname(name)
            versions = []
            map(lambda x: versions.extend(x), \
                    self.repodb.get_version(name, pkg_category=category).values())
            return category, name, version, versions

        if ">=" == data[:2]:
            category, name, version, versions = parse(data[2:])

            for ver in versions:
                if utils.vercmp(ver, version) == 1:
                    affected.append(ver)
            affected.append(version)

            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, affected

        elif "<=" == data[:2]:
            category, name, version, versions = parse(data[2:])
            for ver in versions:
                if utils.vercmp(ver, version) == -1:
                    affected.append(ver)
            affected.append(version)
            
            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, affected

        elif "<" == data[:1]:
            category, name, version, versions = parse(data[1:])
            for ver in versions:
                if utils.vercmp(ver, version) == -1:
                    affected.append(ver)
                    
            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, affected

        elif ">" == data[:1]:
            category, name, version, versions = parse(data[1:])

            for ver in versions:
                if utils.vercmp(ver, version) == 1:
                    affected.append(ver)
                    
            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, affected

        elif "==" == data[:2]:
            pkgname = data[2:]
            category, name = pkgname.split("/")
            name, version = utils.parse_pkgname(name)
            
            if user_defined_options:
                return category, name, affected, user_defined_options

            return category, name, version
        else:
            category, name = data.split("/")
            versions = []
            map(lambda x: versions.extend(x), \
                    self.repodb.get_version(name, pkg_category=category).values())
            
            if user_defined_options:
                return category, name, versions, user_defined_options

            return category, name, versions

    def package_select(self, data, instdb=False):
        db = self.repodb
        if instdb:
            db = self.instdb
        slot = None
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
            version_data = db.find_pkg(name, pkg_category=category, selection = True)
            if not version_data:
                if instdb:
                    return
                out.error("unmet dependency for %s: %s" % ("/".join(self.current_package[:-1])+\
                        "-"+self.current_package[-1], data))
                lpms.terminate()

            if isinstance(version_data, list):
                version_data = version_data[-1]

            # FIXME: fix db.get_version and use it
            if slot is None:
                map(lambda ver: versions.extend(ver), version_data[-1].values())
            else:
                try:
                    versions = version_data[-1][slot]
                except KeyError:
                    out.error("%s is invalid slot for %s" % (slot, data))
                    lpms.terminate()

            return category, name, utils.best_version(versions)

        name, version = utils.parse_pkgname(pkgname)

        category, name = name.split("/")
        result = []
        repo = db.find_pkg(name, pkg_category=category, selection = True)
        if not repo:
            if instdb:
                return
            out.error("unmet dependency for %s: %s" % ("/".join(self.current_package[:-1])+\
                    "-"+self.current_package[-1], pkgname))
            lpms.terminate()
            #raise UnmetDependency(pkgname)


        if slot is None:
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
            versions = repo[-1][int(slot)]

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
            return "".join(data[:first_index]), utils.internal_opts(opt.strip().split(" "), self.global_options)
        
        return "".join(data)

    def fix_dynamic_deps(self, data, options):
        depends = []; opts = []; no = []
        for opt in options:
            prev_indent_level = 0
            if opt in data:
                deps = data[opt]
                for dep in deps:
                    if isinstance(dep, str):
                        if dep == "||":
                            continue
                        depends.append(dep)
                    elif isinstance(dep, tuple):
                        subopt, subdep = dep
                        if subopt.count("\t") == 1:
                            if subopt.strip() in options:
                                prev_indent_level = 1
                                depends.extend(subdep)
                                opts.append(subopt.strip())
                        elif subopt.count("\t") - 1 == prev_indent_level:
                            if subopt.strip() in options:
                                prev_indent_level = subopt.count("\t")
                                depends.extend(subdep)
                                opts.append(subopt.strip())
        for line in data:
            if line in options:
                continue
            else:
                if "||" in data[line]:
                    depends.extend(data[line][data[line].index("||")+1:])

            for opt in data[line]:
                if isinstance(opt, tuple):
                    no.append(opt[0].strip())

        return depends, opts, no 

    def parse_package_name(self, data, instdb=False):
        #try:
        try:
            name, opts = self.opt_parser(data)
        except ValueError:
            result = self.package_select(data, instdb)
            if not result:
                return
            return result, []
        else:
            result = self.package_select(name, instdb),
            if not result:
                return
            return result, opts
        #except UnmetDependency as err:
        #    print err

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

    def collect(self, repo, category, name, version, use_new_opts, recursive=True):

        dependencies = self.repodb.get_depends(repo, category, name, version)
        options = []
        if (repo, category, name, version) in self.operation_data:
            options.extend(self.operation_data[(repo, category, name, version)][-1])

        db_options = self.repodb.get_options(repo, category, name)
        inst_options  = self.instdb.get_options(repo, category, name)

        if use_new_opts or not self.instdb.get_version(name, pkg_category=category):
            for go in self.global_options:
                if not db_options:
                    out.error("%s/%s-%s not found." % (category, name, version))
                    lpms.terminate()

                if version in db_options and db_options[version]:
                    db_option = db_options[version].split(" ")
                    if go in db_option and not go in options:
                         options.append(go)

            if self.udo and (category, name) in self.udo and version in self.udo[(category, name)][0]:
                for opt in self.udo[(category, name)][1]:
                    if utils.opt(opt, self.udo[(category, name)][1], self.global_options):
                        if not opt in options:
                            options.append(opt)
                    else:
                        if opt[1:] in options:
                            options.remove(opt[1:])

            if self.special_opts and name in self.special_opts:
                for opt in self.special_opts[name]:
                    if utils.opt(opt, self.special_opts[name], self.global_options):
                        if not opt in options:
                            options.append(opt)
                    else:
                        if opt[1:] in options:
                            options.remove(opt[1:])

        # FIXME: WHAT THE FUCK IS THAT??
        if not dependencies:
            lpms.terminate()

        local_plan = {"build":[], "runtime": [], "postmerge": [], "conflict": []}

        plan = {}

        def parse_depend_line(string):
            parsed = []
            data = string.split(" ")
            for i in data:
                listed = list(i)
                if not "[" in listed and not "]" in listed:
                    if "/" in listed:
                        parsed.append(i)
                elif "[" in listed:
                    if "]" in listed:
                        parsed.append(i)
                    else:
                        index = data.index(i) + 1
                        while True:
                            if not "]" in data[index]:
                                if "/" in listed:
                                    i += " "+ data[index].strip()
                                index += 1
                            else:
                                i += " "+ data[index]
                                parsed.append(i)
                                break
            return parsed

        for key in ('build', 'runtime', 'conflict', 'postmerge'):
            dynamic_deps = [dep for dep in dependencies[key] if isinstance(dep, dict)]

            if dynamic_deps:
                dyn_packages, dyn_options, no  = self.fix_dynamic_deps(dynamic_deps[0], options)
                for d in no:
                    if d in options: 
                        options.remove(d)
                for dyn_dep in dyn_packages:
                    if key == "conflict":
                        dyn_package_data = self.parse_package_name(dyn_dep, instdb=True)
                        if not dyn_package_data:
                            continue
                    else:
                        dyn_package_data = self.parse_package_name(dyn_dep)
                    dyn_dep_repo = self.get_repo(dyn_package_data[0])
                    (dcategory, dname, dversion), dopt = dyn_package_data
                    if key == "conflict":
                        local_plan[key].append([dyn_dep_repo, dcategory, dname, dversion])
                        continue
                    local_plan[key].append([dyn_dep_repo, dcategory, dname, dversion, dopt])
                     
            static_deps = " ".join([dep for dep in dependencies[key] if isinstance(dep, str)])

            if static_deps:
                for stc_dep in parse_depend_line(static_deps):
                    if key == "conflict":
                        stc_package_data = self.parse_package_name(stc_dep, instdb=True)
                        if not stc_package_data:
                            continue
                    else:
                        stc_package_data = self.parse_package_name(stc_dep)
                    stc_dep_repo = self.get_repo(stc_package_data[0])
                    (scategory, sname, sversion), sopt = stc_package_data
                    if key == "conflict":
                        local_plan[key].append([stc_dep_repo, scategory, sname, sversion])
                        continue
                    local_plan[key].append([stc_dep_repo, scategory, sname, sversion, sopt])

        self.operation_data.update({(repo, category, name, version): [local_plan, options]})
        
        #FIXME: postmerge dependency?
        if not local_plan['build'] and not local_plan['runtime']:
            if not (repo, category, name, version) in self.single_pkgs:
                self.single_pkgs.append((repo, category, name, version))

        for key in ('build', 'runtime', 'postmerge'):
            if not local_plan[key]:
                continue
            for local in local_plan[key]:
                lrepo, lcategory, lname, lversion, lopt = local
                fullname = (lrepo, lcategory, lname, lversion)
                if (repo, category, name, version) in self.single_pkgs:
                    self.single_pkgs.remove((repo, category, name, version))
                if key == "postmerge":
                    self.package_query.append((fullname, (repo, category, name, version)))
                    self.collect(lrepo, lcategory, lname, lversion, self.use_new_opts)
                else:
                    self.package_query.append(((repo, category, name, version), fullname))
                if fullname in self.plan:
                    plan_version, plan_options = self.plan[fullname]
                    if (lrepo, lcategory, lname, lversion) in self.operation_data:
                        for plan_option in plan_options:
                            # FIXME: This is a bit problematic.
                            self.modified_by_package.append(fullname)
                            if not plan_option in self.operation_data[fullname][-1]:
                                self.operation_data[fullname][-1].append(plan_option)
                                self.collect(lrepo, lcategory, lname, lversion, self.use_new_opts)
                    continue

                self.plan.update({fullname: (lversion, lopt)})
                if recursive:
                    self.collect(lrepo, lcategory, lname, lversion, self.use_new_opts)

    def resolve_depends(self, packages, cmd_options, use_new_opts, specials=None):
        self.special_opts = specials
        self.parse_user_defined_options_file()
        setattr(self, "use_new_opts", use_new_opts)

        for options in (self.config.options.split(" "), cmd_options):
            for opt in options:
                if utils.opt(opt, cmd_options, self.config.options.split(" ")):
                    if not opt in self.global_options:
                        self.global_options.append(opt)
                else:
                    if opt in self.global_options:
                        self.global_options.remove(opt)

        primary = []
        packages = list(set(packages))
        for pkg in packages:
            self.current_package = pkg
            repo, category, name, version = pkg
            self.collect(repo, category, name, version, True, recursive=False)
      
        primary.extend(self.package_query)
        self.package_query = []

        for i in primary:
            repo, category, name, version = i[1]
            self.collect(repo, category, name, version, True)

        if not self.package_query and primary:
            self.package_query.extend(primary)

        if not self.package_query or lpms.getopt("--ignore-depends"):
            return packages, self.operation_data

        plan = []

        try:
            for package in packages:
                if not package in [data[0] for data in self.package_query]:
                     plan.append(package)

            processed = topsort(self.package_query)
            for single_pkg in self.single_pkgs:
                if not single_pkg in processed:
                    processed.append(single_pkg)

            for pkg in processed:
                repo, category, name, version = pkg
                if (repo, category, name, version) in packages:
                    if not pkg in plan:
                        plan.append(pkg)
                        continue 

                data = self.instdb.find_pkg(name, pkg_category = category)
                
                if data:
                    irepo = self.instdb.get_repo(category, name, version)
                    db_options = self.instdb.get_options(irepo, category, name)

                    if version in db_options:
                        for opt in self.operation_data[pkg][-1]:
                            if not opt in db_options[version].split(" ") and not pkg in plan:
                                if self.use_new_opts or pkg in self.modified_by_package:
                                    if not pkg in plan:
                                        plan.append(pkg)
                    else:
                        if not version in db_options and (lpms.getopt("-U") or lpms.getopt("--upgrade") \
                                 or lpms.getopt("--force-upgrade")):
                            if not pkg in plan:
                                plan.append(pkg)
                        else: 
                            if not pkg in packages and pkg in self.operation_data: 
                                del self.operation_data[pkg] 
                else:
                    if not pkg in plan:
                        plan.append(pkg)

            locked_packages = []
            if hasattr(self, "user_defined_lock"):
                for line in self.user_defined_lock:
                    locked_packages.extend([self.parse_user_defined_file(line)])

            for item in plan:
                plan_category = item[1]; plan_name = item[2]; plan_version = item[3]
                for locked_package in locked_packages:
                    if plan_category == locked_package[0] and \
                            plan_name == locked_package[1] and \
                            plan_version in locked_package[2]:
                                out.write("\n")
                                for v in locked_package[2]:
                                    out.warn("%s-%s" % ("/".join(item[:-1]), v))
                                out.write("\n")
                                if len(locked_package[2]) > 1:
                                    out.error("these packages were locked by system administrator.")
                                else:
                                    out.error("this package was locked by system administrator.")
                                lpms.terminate()
            plan.reverse()
            return plan, self.operation_data

        except CycleError as err:
            # FIXME: We need more powerful output.
            answer, num_parents, children = err
            for cycle in find_cycles(parent_children=children):
                out.brightred("Circular Dependency:\n")
                for cyc in cycle:
                    print(cyc)
                lpms.terminate()
                #out.write(cycle+"\n\n")
