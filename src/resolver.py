import lpms

from lpms import out
from lpms import conf
from lpms import utils

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

    def package_select(self, data):
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
            version_data = self.repodb.find_pkg(name, pkg_category=category, selection = True)
            if not version_data:
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
        repo = self.repodb.find_pkg(name, pkg_category=category, selection = True)
        if not repo:
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

        db_options = self.repodb.get_options(repo, category, name, version)

        if use_new_opts or not self.instdb.get_version(name, pkg_category=category):
            for go in self.global_options:
                if not db_options:
                    out.error("%s/%s-%s not found." % (category, name, version))
                    lpms.terminate()

                if version in db_options and db_options[version]:
                    db_option = db_options[version].split(" ")
                    if go in db_option and not go in options:
                        options.append(go)

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

        local_plan = {"build":[], "runtime": []}

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

        for key in ('build', 'runtime'):
            dynamic_deps = [dep for dep in dependencies[key] if isinstance(dep, dict)]

            if dynamic_deps:
                dyn_packages, dyn_options, no  = self.fix_dynamic_deps(dynamic_deps[0], options)
                for d in no:
                    if d in options:
                        options.remove(d)
                for dyn_dep in dyn_packages:
                    dyn_package_data = self.parse_package_name(dyn_dep)
                    dyn_dep_repo = self.get_repo(dyn_package_data[0])
                    (dcategory, dname, dversion), dopt = dyn_package_data
                    local_plan[key].append([dyn_dep_repo, dcategory, dname, dversion, dopt])
                    
            static_deps = " ".join([dep for dep in dependencies[key] if isinstance(dep, str)])

            if static_deps:
                for stc_dep in parse_depend_line(static_deps):
                    stc_package_data = self.parse_package_name(stc_dep)
                    stc_dep_repo = self.get_repo(stc_package_data[0])
                    (scategory, sname, sversion), sopt = stc_package_data
                    local_plan[key].append([stc_dep_repo, scategory, sname, sversion, sopt])

        self.operation_data.update({(repo, category, name, version): [local_plan, options]})

        def fix_opts():
            for o in lopt:
                if not o in current_opts: return True

        for local_data in local_plan.values():
            if local_data:
                for local in local_data:
                    lrepo, lcategory, lname, lversion, lopt = local
                    fullname = (lrepo, lcategory, lname, lversion)
                    if (repo, category, name, version) in self.single_pkgs:
                        self.single_pkgs.remove((repo, category, name, version))
                    self.package_query.append(((repo, category, name, version), fullname))
                    if fullname in self.plan:
                        current_version, current_opts = self.plan[fullname]
                        if not fix_opts() or lversion != current_version:
                            continue
                        lopt += current_opts

                    self.plan.update({fullname: (lversion, lopt)})
                    if recursive:
                        self.collect(lrepo, lcategory, lname, lversion, self.use_new_opts)

    def resolve_depends(self, packages, cmd_options, use_new_opts, specials=None):
        self.special_opts = specials
        setattr(self, "use_new_opts", use_new_opts)

        for options in (self.config.options.split(" "), cmd_options):
            for opt in options:
                if utils.opt(opt, cmd_options, self.config.options.split(" ")):
                    if not opt in self.global_options:
                        self.global_options.append(opt)
                else:
                    if opt in self.global_options:
                        self.global_options.remove(opt)

        # FIXME: this is obsoleted.
        def fix_opts():
            opts = []
            if db_options and version in db_options and db_options[version]:
                for db in db_options[version].split(" "):
                    if db in self.global_options: opts.append(db)
            return opts

        primary = []
        for pkg in packages:
            self.current_package = pkg
            repo, category, name, version = pkg

            db_options = self.repodb.get_options(repo, category, name, version)
            self.collect(repo, category, name, version, True, recursive=False)
      
        primary.extend(self.package_query)
        self.package_query = []

        for i in primary:
            repo, category, name, version = i[1]
            db_options = self.repodb.get_options(repo, category, name, version)
            self.collect(repo, category, name, version, True)
                  
        if not self.package_query or lpms.getopt("--ignore-depends"):
            return packages, self.operation_data

        plan = []

        try:
            for package in packages:
                if not package in [data[0] for data in self.package_query]:
                    plan.append(package)

            for pkg in topsort(self.package_query)+self.single_pkgs:
                repo, category, name, version = pkg

                if (repo, category, name, version) in packages:
                    plan.append(pkg)
                    continue

                data = self.instdb.find_pkg(name, pkg_category = category)

                if data:
                    db_options = self.instdb.get_options(repo, category, name, version)
                    # FIXME: get_options repo bilgisi olmadan calisabilmeli
                    if not db_options:
                        continue
                    if version in db_options:
                        for opt in self.operation_data[pkg][-1]:
                            if not opt in db_options[version].split(" ") and not pkg in plan:
                                plan.append(pkg)
                    else:
                        if not version in db_options and (lpms.getopt("-U") or lpms.getopt("--upgrade") \
                                or lpms.getopt("--force-upgrade")):
                            plan.append(pkg)
                        else:
                            if not pkg in packages:
                                del self.operation_data[pkg]
                else:
                    plan.append(pkg)

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
