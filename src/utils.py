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

import re
import os
import sys
import stat
import glob
import string
import hashlib
import collections

import lpms
from lpms import out
from lpms import conf
from lpms import shelltools
from lpms import constants as cst


def check_cflags(flag):
    return flag in [atom.strip() for \
            atom in conf.LPMSConfig().CFLAGS.strip(" ")]

def set_parser(set_name):
    sets = []
    for repo in valid_repos():
        repo_set_file = os.path.join(cst.repos, repo, "info/sets", "%s.set" % set_name)
        if os.path.isfile((repo_set_file)):
            sets.append(repo_set_file)
            
    user_set_file = "%s/%s.set" % (cst.user_sets_dir, set_name)

    if os.path.isfile(user_set_file):
        sets.append(user_set_file)

    if len(sets) > 1:
        out.normal("ambiguous for %s\n" % out.color(set_name, "green"))
        def ask():
            for c, s in enumerate(sets):
                out.write("	"+out.color(str(c+1), "green")+") "+s+"\n")
            out.write("\nselect one of them:\n")
            out.write("to exit, press Q or q.\n")
            
        while True:
            ask()
            answer = sys.stdin.readline().strip()
            if answer == "Q" or answer == "q":
                lpms.terminate()
            elif answer.isalpha():
                out.warn("please give a number.")
                continue
            
            try:
                set_file = sets[int(answer)-1]
                break
            except (IndexError, ValueError):
                out.warn("invalid command.")
                continue
    elif len(sets) == 1:
        set_file = sets[0]
    else:
        out.warn("%s not found!")
        return []
    
    return [line for line in file(set_file).read().strip().split("\n") \
            if not line.startswith("#") and line != ""]

def select_repo(data):
    valid = valid_repos()

    if not valid:
        out.error("repo.conf is empty or not found. Please check it.")
        lpms.terminate()

    sorting = []
    
    for d in data:
        if d in valid:
            sorting.append(valid.index(d))
    if not sorting:
        return sorting
    return valid[sorted(sorting)[0]]

def valid_repos():
    if not os.path.isfile(cst.repo_conf):
        out.warn("%s not found!" % cst.repo_conf)
        return []

    with open(cst.repo_conf) as repo_file:
        return [repo[1:-1] for repo in repo_file.read().split("\n") \
                if repo.startswith("[") and repo.endswith("]")]

def is_lpms_running():
    for _dir in os.listdir("/proc"):
        if not _dir.isdigit():
            continue
        
        if int(_dir) == os.getpid():
            continue

        if get_process_name(_dir) == "lpms":
            return True
    return False

def get_process_name(pid):
    f = open("/proc/%s/stat" % pid)
    try:
        name = f.read().split(' ')[1].replace('(', '').replace(')', '')
    finally:
        f.close()
        # XXX - gets changed later and probably needs refactoring
    return name

def get_pid_list():
    """Returns a list of PIDs currently running on the system."""
    pids = [int(x) for x in os.listdir('/proc') if x.isdigit()]
    return pids

def pid_exists(pid):
    """Checks For the existence of a unix pid."""
    return pid in get_pid_list()

def get_mimetype(path):
    if not os.access(path, os.R_OK):
        return False
    
    if conf.LPMSConfig().userland == "BSD":
        data = os.popen("file -i %s" % path).read().strip()
        return data.split(":", 1)[1].split(";")[0].strip()

    import magic
    m = magic.open(magic.MIME_TYPE)
    m.load()
    mimetype = m.file(path.encode('utf-8'))
    m.close()
    return mimetype

def run_strip(path):
    p = os.popen("/usr/bin/strip --strip-unneeded %s" % path)
    ret = p.close()
    if ret:
        out.warn("/usr/bin/strip/ --strip-unneeded command failed for %s" % path)

def set_valid_options(options, cmd_options, default_options):
    if options is None:
        return 
    return [o for o in options.split(' ') if opt(o, cmd_options, 
        default_options)]

def confirm(text):
    turns = 5
    while turns:
        turns -= 1
        out.warn(text+"["+out.color("yes", "green")+"/"+out.color("no", "red")+"]")
        answer = sys.stdin.readline().strip()
        if answer == "yes" or answer == "y" or answer == "":
            return True
        elif answer == "no" or answer == "n":
            return False
        out.write(out.color("Sorry, response " + answer + " not understood! yes/y or no/n\n", "red"))

def parse_pkgname(script_name):
    #pkgname = []; version = []
    #parsed=script_name.split(".py")[0].split("-")
    #for i in parsed:
    #    if "." in list(i) or i.isdigit():
    #        version.append(i)
    #        continue
    #    elif "r" in list(i) and i == parsed[-1]:
    #        version.append(i)
    #        continue
    #    elif "p" in list(i) and i == parsed[-1]:
    #        version.append(i)
    #        continue
    #    for x in list(i):
    #        if x.isalnum() or x == "+" or x == "_":
    #            pkgname.append(x)
    #    pkgname.append("-")
    #version = ["-".join(version)]
    #version.insert(0, "".join(pkgname)[0:-1])
    #return version

    ############################################################################
    #
    # my parse_pkgparse code is crappy. So I am using drobbins' historical code.
    # I have found the code in portage-1.6.5
    # Thanks to Daniel Robbins :=P
    #
    ############################################################################
    return pkgsplit(script_name)

def check_path(binary):
    if not binary.startswith("/"):
        for path in os.environ["PATH"].split(":"):
            binary_path = os.path.join(path, binary)
            if os.access(binary_path, os.F_OK) and os.access(binary_path, os.X_OK):
                    return binary_path
        return False
    if os.access(binary, os.F_OK) and os.access(binary, os.X_OK):
        return binary
    return False

def export(variable, value):
    os.environ[variable] = value

def opt(option, cmd_options, default_options, from_package = []):
    def decision(data_set):
        for o in [d.strip() for d in data_set if d != ""]:
            if o[0] != "-" and o == option:
                return True
            elif o[0] == "-":
                if "".join(o.split("-")[1:]) == option:
                    return False
    for data_set in (from_package, cmd_options, default_options):
        my_dec = decision(data_set)
        if my_dec is None:
            continue
        else:
            return my_dec
    return False

def check_root(msg=True): 
    if os.getuid() != 0:
        if msg:
            lpms.catch_error("you must be root!")
        else:
            return False
    return True

def set_environment_variables():
    config = conf.LPMSConfig()
    export('HOST', config.CHOST)
    export('CFLAGS', config.CFLAGS)
    export('CXXFLAGS', config.CXXFLAGS)
    export('LDFLAGS', config.LDFLAGS)
    export('JOBS', config.MAKEOPTS)
    export('CC', config.CHOST+"-"+"gcc")
    export('CXX', config.CHOST+"-"+"g++")

def check_metadata(metadata):
    for tag in ('summary', 'license', 'homepage'):
        if not tag in metadata.keys():
            lpms.terminate("%s must be defined in metadata" % tag)
    return True

def get_gid(path):
    return os.stat(path)[stat.ST_GID]

def get_uid(path):
    return os.stat(path)[stat.ST_UID]

def get_mod(path):
    return stat.S_IMODE(os.stat(path)[stat.ST_MODE])

def get_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)/(1024*1024.0)
    else:
        foldersize = 0
        for path, dirs, files in os.walk(path):
            for f in files:
                filename = os.path.join(path, f)
                try:
                    foldersize += os.path.getsize(filename)
                except:
                    out.warn("file size not calculated: %s" % filename)
        return foldersize/(1024*1024.0)

def get_mtime(path):
    return os.stat(path)[stat.ST_MTIME]

def get_atime(path):
    return os.stat(path)[stat.ST_ATIME]

def sha1sum(path):
    try:
        buf = open(path).read()
    except:
        return False
    sh = hashlib.sha1()
    sh.update(buf)
    return sh.hexdigest()

# FIXME:
def get_src_url(metadata, name, version):
    for tag in ('src_url', 'src_repository'):
        if tag in metadata.keys():
            return parse_url_tag(metadata[tag], name, version)
    lpms.terminate("you must be define src_url or src_repository")

def get_indent_level(data):
    def getlspace(line):
        i, n = 0, len(line)
        while i < n and line[i] == " ":
            i += 1
        return i

    sorting = []
    for line in data:
        if "@" in list(line):
            indent_level = getlspace(line)
            if indent_level != 0:
                sorting.append(indent_level)
    if sorting:
        return "".join([" " for x in range(0, sorted(sorting)[0])])
    return "\t"

def internal_opts(data, global_options):
    def check_alnum(seq):
        for c in list(seq):
            if not c.isalnum():
                return False
        return True

    result = []

    for opt in data:
        if not opt.startswith("-"):
            if opt.endswith("?") and opt[:-1] in global_options:
                result.append(opt[:-1])
            elif opt.endswith("!?") and not opt[:-2] in global_options:
                result.append(opt[:-2])
            elif not opt.endswith("?") and not opt.endswith("!?"):
                result.append(opt)
        else:
            if opt.endswith("?") and not opt[1:-1] in global_options and \
                    check_alnum(opt[1:-1]):
                result.append(opt[1:-1])
            elif opt.endswith("!?") and opt[1:-2] in global_options:
                result.append(opt[1:-2])

    return result


def parse_opt_deps(depends):
    dependencies = {}
    data = [dep for dep in depends.split("\n") if dep != ""]
    indent = get_indent_level(data)
    for line in data:
        if line.startswith("#"):
            continue
        try:
            opt, deps = line.split("@")
        except ValueError:
            if not opt.count(indent) and not line.strip() == "":
                dependencies[opt.strip()].extend(line.strip().split(" "))
                continue
        if not opt.count(indent):
            dependencies[opt.strip()] = [d for d in deps.strip().split(" ") if d != ""]
            i = data.index(line) + 1
            for x in data[i:]:
                try:
                    subopt, subdep = x.split("@")
                except ValueError:
                    if len(dependencies[opt.strip()]) > 1:
                        if isinstance(dependencies[opt.strip()][-1][-1], list) and not x.strip() == "":
                            dependencies[opt.strip()][-1][-1].extend(x.strip().split(" "))
                    continue
                if not subopt.count(indent):
                    break
                subopt = "\t".join(subopt.split(indent)).rstrip()
                dependencies[opt.strip()].append((subopt, [sd for sd in subdep.strip().split(" ") if sd != ""]))
    return dependencies

# FIXME
def parse_url_tag(urls, name, version):
    download_list = []
    for i in urls.split(" "):
        result = i.split("(")
        if len(result) == 1:
            url = result[0].replace("$fullname", name+"-"+version)
            url = result[0].replace("$name", name); url = url.replace("$version", version)
            download_list.append(url)
        elif len(result) == 2:
            url = result[1].split(")")[0].replace("$name", name); url = url = url.replace("$version", version)
            url = url.replace("$fullname", name+"-"+version)
            download_list.append((result[0], url))
    return download_list

def pkg_selection_dialog(data):
    if not lpms.getopt("--ask-repo"):
        repo = select_repo([d[0] for d in data])
        result = [pkg for pkg in data if pkg[0] == repo]
        if len(result) == 1:
            return result

    out.normal("this package is contained by more than one repositories.\n")
    def ask():
        for count, pkg in enumerate(data):
            repo, category, name, version = pkg
            out.write("\t%s) %s/%s/%s\n" % (out.color(str(count+1), "green"), out.color(repo, "red"), 
                    category, name))
        out.write("\n")
        out.normal("select one of them: ")
        out.write("\nto exit, press 'Q' or 'q'\n")

    while True:
        # run the dialog, show packages from different repositories
        ask()
        answer = sys.stdin.readline().strip()
        if answer == "Q" or answer == "q":
            lpms.terminate()
        elif answer.isalpha():
            out.warn("you must give a number.\n")
            continue
        
        try:
            # FIXME: we need more control
            return data[int(answer)-1]
        except:
            out.warn("%s seems invalid.\n" % out.color(answer, "red"))
            continue

def metadata_parser(data, keys=None):
    metadata = collections.OrderedDict()
    if not keys:
        keys = ('summary', 'src_url', 'license', 'arch', 'homepage', 'options', 'slot')
    lines = data.strip().split('\n')
    subtotal = []
    for line in lines:
        line = line.split('@', 1)
        if len(line) == 1:
            last_item = list(metadata)[-1]
            metadata[last_item] = metadata[last_item]+" "+line[0].strip()
            continue
        mykey, mydata = line
        mykey = mykey.strip()
        if mykey in keys:
            metadata[mykey] = mydata.strip()
        else:
            last_item = list(metadata)[-1]
            metadata[last_item] = metadata[last_item]+" "+"@".join(line).strip()
    
    if not keys and not "options" in metadata:
        metadata["options"] = None

    return metadata

def depends_parser(depends):
    deps = {}
    for atom in depends.strip().split('\n'):
        if len(atom.split('@')) == 2:
            opt = atom.split('@')[0].strip()
            deps[opt] = []; data = atom.split('@')[1]
            if data != '\n' and data != '\t' and data != '':
                deps[opt].append(data.strip())
        else:
            data = atom.split('@')[0]
            if data != '\n' and data != '\t' and data != '':
                deps[opt].append(data.strip())
    return deps

def import_script(script_path):
    objects = {}
    try:
        exec compile(open(script_path).read(), "error", "exec") in objects
    except SyntaxError, err:
        lpms.catch_error("%s in %s" % (err, script_path))
    return objects

def indent(elem, level = 0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        #if not elem.tail or not elem.tail.strip():
        #    elem.tail = i
        for e in elem:
            indent(e, level+1)
            if not e.tail or not e.tail.strip():
                e.tail = i + "  "
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def reload_previous_repodb():
    dirname = os.path.dirname(cst.repositorydb_path)
    for _file in os.listdir(dirname):
        if _file.startswith("repositorydb") and _file.count(".") == 2:
            shelltools.copy(os.path.join(dirname, _file), cst.repositorydb_path)
            from datetime import datetime
            timestamp = _file.split(".")[-1]
            previous_date = datetime.fromtimestamp(float(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
            out.normal("loading previous database copy: %s" %
                    out.color(previous_date, "red"))
            return
    out.error("no repodb backup found.")

def list_disk_pkgs(repo, category):
    '''Lists pkgnames in the disk using repo and category name'''
    packages = []
    source_dir = os.path.join(cst.repos, repo, category)
    if not os.path.isdir(source_dir):
        out.warn("%s does not exist." % out.color(source_dir, "red"))
        return packages

    sources = os.listdir(source_dir)
    if not sources:
        out.warn("%s seems empty." % out.color(source_dir, "red"))
        return packages

    for source in sources:
        if glob.glob(os.path.join(source_dir, source)+"/*.py"):
            packages.append(source)
    return packages

def sandbox_dirs():
    dirs = []
    sandbox_config = os.path.join(cst.config_dir, cst.sandbox_file)
    if not os.path.isfile(sandbox_config):
        out.warn("%s is not found! So this may be harmfull!" % sandbox_config)
        return dirs

    for line in file(sandbox_config):
        line = line.strip()
        if not line.startswith("#") and len(line) > 0:
            dirs.append(line)
    return dirs

# xterm_title and xterm_title_reset were borrowed from PiSi
def xterm_title(message):
    if "TERM" in os.environ and sys.stderr.isatty():
        terminal_type = os.environ["TERM"]
        for term in ["xterm", "Eterm", "aterm", 
                "rxvt", "screen", "kterm", "rxvt-unicode"]:
            if terminal_type.startswith(term):
                sys.stderr.write("\x1b]2;"+str(message)+"\x07")
                sys.stderr.flush()
                break

def xterm_title_reset():
    if "TERM" in os.environ:
        xterm_title("")

###############################################################################
#
# 'vercmp' function is borrowed from Portage. I will fixed up it in the future.
#
###############################################################################

vercmp_cache = {}
_cat = r'[\w+][\w+.-]*'

# 2.1.2 A package name may contain any of the characters [A-Za-z0-9+_-].
# It must not begin with a hyphen,
# and must not end in a hyphen followed by one or more digits.
_pkg = r'[\w+][\w+-]*?'

_v = r'(cvs\.)?(\d+)((\.\d+)*)([a-z]?)((_(pre|p|beta|alpha|rc)\d*)*)'
_rev = r'\d+'
_vr = _v + '(-r(' + _rev + '))?'

_cp = '(' + _cat + '/' + _pkg + '(-' + _vr + ')?)'
_cpv = '(' + _cp + '-' + _vr + ')'
_pv = '(?P<pn>' + _pkg + '(?P<pn_inval>-' + _vr + ')?)' + '-(?P<ver>' + _v + ')(-r(?P<rev>' + _rev + '))?'

ver_regexp = re.compile("^" + _vr + "$")
suffix_regexp = re.compile("^(alpha|beta|rc|pre|p)(\\d*)$")
suffix_value = {"pre": -2, "p": 0, "alpha": -4, "beta": -3, "rc": -1}
endversion_keys = ["pre", "p", "alpha", "beta", "rc", "hr"]

def vercmp(ver1, ver2, silent=1):
	"""
	Compare two versions
	Example usage:
		>>> from portage.versions import vercmp
		>>> vercmp('1.0-r1','1.2-r3')
		negative number
		>>> vercmp('1.3','1.2-r3')
		positive number
		>>> vercmp('1.0_p3','1.0_p3')
		0
	
	@param pkg1: version to compare with (see ver_regexp in portage.versions.py)
	@type pkg1: string (example: "2.1.2-r3")
	@param pkg2: version to compare againts (see ver_regexp in portage.versions.py)
	@type pkg2: string (example: "2.1.2_rc5")
	@rtype: None or float
	@return:
	1. positive if ver1 is greater than ver2
	2. negative if ver1 is less than ver2 
	3. 0 if ver1 equals ver2
	4. None if ver1 or ver2 are invalid (see ver_regexp in portage.versions.py)
	"""

	if ver1 == ver2:
		return 0
	mykey=ver1+":"+ver2
	try:
		return vercmp_cache[mykey]
	except KeyError:
		pass
	match1 = ver_regexp.match(ver1)
	match2 = ver_regexp.match(ver2)
	
	# checking that the versions are valid
	if not match1 or not match1.groups():
		if not silent:
			print("!!! syntax error in version: %s") % ver1
		return None
	if not match2 or not match2.groups():
		if not silent:
			print("!!! syntax error in version: %s") % ver2
		return None

	# shortcut for cvs ebuilds (new style)
	if match1.group(1) and not match2.group(1):
		vercmp_cache[mykey] = 1
		return 1
	elif match2.group(1) and not match1.group(1):
		vercmp_cache[mykey] = -1
		return -1
	
	# building lists of the version parts before the suffix
	# first part is simple
	list1 = [int(match1.group(2))]
	list2 = [int(match2.group(2))]

	# this part would greatly benefit from a fixed-length version pattern
	if match1.group(3) or match2.group(3):
		vlist1 = match1.group(3)[1:].split(".")
		vlist2 = match2.group(3)[1:].split(".")

		for i in range(0, max(len(vlist1), len(vlist2))):
			# Implcit .0 is given a value of -1, so that 1.0.0 > 1.0, since it
			# would be ambiguous if two versions that aren't literally equal
			# are given the same value (in sorting, for example).
			if len(vlist1) <= i or len(vlist1[i]) == 0:
				list1.append(-1)
				list2.append(int(vlist2[i]))
			elif len(vlist2) <= i or len(vlist2[i]) == 0:
				list1.append(int(vlist1[i]))
				list2.append(-1)
			# Let's make life easy and use integers unless we're forced to use floats
			elif (vlist1[i][0] != "0" and vlist2[i][0] != "0"):
				list1.append(int(vlist1[i]))
				list2.append(int(vlist2[i]))
			# now we have to use floats so 1.02 compares correctly against 1.1
			else:
				# list1.append(float("0."+vlist1[i]))
				# list2.append(float("0."+vlist2[i]))
				# Since python floats have limited range, we multiply both
				# floating point representations by a constant so that they are
				# transformed into whole numbers. This allows the practically
				# infinite range of a python int to be exploited. The
				# multiplication is done by padding both literal strings with
				# zeros as necessary to ensure equal length.
				max_len = max(len(vlist1[i]), len(vlist2[i]))
				list1.append(int(vlist1[i].ljust(max_len, "0")))
				list2.append(int(vlist2[i].ljust(max_len, "0")))

	# and now the final letter
	# NOTE: Behavior changed in r2309 (between portage-2.0.x and portage-2.1).
	# The new behavior is 12.2.5 > 12.2b which, depending on how you look at,
	# may seem counter-intuitive. However, if you really think about it, it
	# seems like it's probably safe to assume that this is the behavior that
	# is intended by anyone who would use versions such as these.
	if len(match1.group(5)):
		list1.append(ord(match1.group(5)))
	if len(match2.group(5)):
		list2.append(ord(match2.group(5)))

	for i in range(0, max(len(list1), len(list2))):
		if len(list1) <= i:
			vercmp_cache[mykey] = -1
			return -1
		elif len(list2) <= i:
			vercmp_cache[mykey] = 1
			return 1
		elif list1[i] != list2[i]:
			a = list1[i]
			b = list2[i]
			rval = (a > b) - (a < b)
			vercmp_cache[mykey] = rval
			return rval

	# main version is equal, so now compare the _suffix part
	list1 = match1.group(6).split("_")[1:]
	list2 = match2.group(6).split("_")[1:]
	
	for i in range(0, max(len(list1), len(list2))):
		# Implicit _p0 is given a value of -1, so that 1 < 1_p0
		if len(list1) <= i:
			s1 = ("p","-1")
		else:
			s1 = suffix_regexp.match(list1[i]).groups()
		if len(list2) <= i:
			s2 = ("p","-1")
		else:
			s2 = suffix_regexp.match(list2[i]).groups()
		if s1[0] != s2[0]:
			a = suffix_value[s1[0]]
			b = suffix_value[s2[0]]
			rval = (a > b) - (a < b)
			vercmp_cache[mykey] = rval
			return rval
		if s1[1] != s2[1]:
			# it's possible that the s(1|2)[1] == ''
			# in such a case, fudge it.
			try:
				r1 = int(s1[1])
			except ValueError:
				r1 = 0
			try:
				r2 = int(s2[1])
			except ValueError:
				r2 = 0
			rval = (r1 > r2) - (r1 < r2)
			if rval:
				vercmp_cache[mykey] = rval
				return rval

	# the suffix part is equal to, so finally check the revision
	if match1.group(10):
		r1 = int(match1.group(10))
	else:
		r1 = 0
	if match2.group(10):
		r2 = int(match2.group(10))
	else:
		r2 = 0
	rval = (r1 > r2) - (r1 < r2)
	vercmp_cache[mykey] = rval
	return rval


##########################################################
#
#
# The following lines were borrowed from Portage-1.6.5.
# I modified the code for lpms. Thanks Gentoo team.
#
#
##########################################################

endversion={"pre":-2,"p":0,"alpha":-4,"beta":-3,"rc":-1}

def revverify(myrev):
    if len(myrev) == 0:
        return False
    if myrev[0] ==  'r':
        try:
            string.atoi(myrev[1:])
            return True
        except:
            pass
    return False

def ververify(myorigval, silent = 1):
    if len(myorigval) == 0:
        if not silient:
            out.error("package contains \'-\' part.")
        return False

    myval = string.split(myorigval, '.')
    if len(myval) == 0:
        if not silent:
            out.error("empty version string.")
        return False

    for x in myval[:-1]:
        if not len(x):
            if not silient:
                out.error("error in %s: two decimal points in a row" % myorigval)
            return False
        try:
            foo = string.atoi(x)
        except:
            if not silent:
                out.error("name error in %s : %s is not a valid version component" % (myorigval, x))
            return False

    if not len(myval[-1]):
        if not silent:
            out.error("name error in %s: two decimal points in a row" % myorigval)
        return False

    try:
        foo = string.atoi(myval[-1])
        return True
    except:
        pass

    if myval[-1][-1] in string.lowercase:
        try:
            foo = string.atoi(myval[-1][:-1])
            return True
        except:
            pass

    ep = string.split(myval[-1], '_')
    if len(ep) != 2:
        if not silent:
            out.error("name error in %s" % myorigval)
        return False
    try:
        foo = string.atoi(ep[0])
    except:
        if not silent:
            out.error("name error in %s: characters before _ must be numeric" % myorigval)
        return False

    for mye in endversion.keys():
        if ep[1][0:len(mye)] == mye:
            if len(mye) == len(ep[1]):
                return True
            else:
                try:
                    foo = string.atoi(ep[1][len(mye):])
                    return True
                except:
                    pass
    if not silent:
        out.error("name error in %s" % myorigval)
    return False

def pkgsplit(mypkg, silent = 1):
    myparts = string.split(mypkg, '-')
    if len(myparts) < 2:
        if not silent:
            out.error("name error in %s: missing a version or name part." % mypkg)
        return None
    
    for x in myparts:
        if len(x) == 0:
            if not silent:
                out.error("name error in %s: empty \'-\' part." % mypkg)
            return None

    if revverify(myparts[-1]):
        if ververify(myparts[-2]):
            if len(myparts) == 2:
                return None
            else:
                for x in myparts[:-2]:
                    if ververify(x):
                        return None
                return "-".join(myparts[:-2]), myparts[-2]+"-"+myparts[-1]
        else:
            return None

    elif ververify(myparts[-1], silent):
        if len(myparts) == 1:
            if not silent:
                out.error("name error in %s: missing name part." % mypkg)
            return None
        else:
            for x in myparts[:-1]:
                if ververify(x):
                    if not silent:
                        out.error("name error in %s: multiple version parts." % mypkg)
                    return None
            return "-".join(myparts[:-1]), myparts[-1]
    else:
        return None

def best_version(versions):
    if not versions:
        return
    versions = list(set(versions))
    listed_vers = {}
    for ver in versions:
        i = 0
        for __ver in versions:
            if ver !=  __ver:
                i += vercmp(ver, __ver)
                listed_vers[ver] = i
    
    if not listed_vers:
        return versions[0]
    
    for ver in listed_vers:
        if listed_vers[ver] == sorted(listed_vers.values())[-1]:
            return ver
