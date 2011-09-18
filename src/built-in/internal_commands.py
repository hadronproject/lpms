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
import inspect

from lpms import utils
from lpms import out
from lpms import shelltools


def addflag(fn):
    def wrapped(flag):
        name = fn.__name__.split("_")[1].upper()
        result = get_env(name)+" "+fn(flag)
        os.environ[name] = result
        return result
    return wrapped

@addflag
def append_cflags(flag):
    return flag

@addflag
def append_cxxflags(flag):
    return flag

@addflag
def append_ldflags(flag):
    return flag

def append_config(option, positive, negative=None):
    if opt(option):
        config += positive+" "
    else:
        if negative is not None:
            config += negative+" "
            return

        if positive.startswith("--enable"):
            positive = positive.replace("--enable", "--disable")
            config += positive+" "
        elif positive.startswith("--with"):
            positive = positive.replace("--with", "--without")
            config += positive+" "

def binutils_cmd(command):
    try:
        host = os.environ['HOST']
    except KeyError:
        out.warn_notify("HOST value does not defined in environment.")
        return ''

    cmd = "%s-%s" % (host, command)

    if not shelltools.binary_isexists(cmd):
        out.warn_notify("%s not found." % cmd)
        return ''
    return cmd

def delflag(fn):
    def wrapped(flag):
        name = fn.__name__.split("_")[1].upper()
        result = " ".join(get_env(name).split(flag))
        os.environ[name] = result
        return result
    return wrapped

@delflag
def del_cflags(flag):
    return flag

@delflag
def del_cxxflags(flag):
    return flag

@delflag
def del_ldflags(flag):
    return flag

def insdoc(*sources):
    if slot != "0":
        target = prepare_target("/usr/share/doc/%s" % fullname)
    else:
        target = prepare_target("/usr/share/doc/%s" % name)

    shelltools.makedirs(target)
    return shelltools.install_readable(sources, target)

def insinfo(*sources):
    target = prepare_target("/usr/share/info")
    shelltools.makedirs(os.path.dirname(target))
    return shelltools.install_readable(sources, target)

def inslib(source, target='/usr/lib'):
    target = prepare_target(target)
    shelltools.makedirs(os.path.dirname(target))
    return shelltools.install_library(source, prepare_target(target), 0755)

def prepare_target(path):
    if path[0] == "/":
        return os.path.join(install_dir, "".join(list(path)[1:]))
    else:
        return os.path.join(install_dir, path)

# FIXME: Is this good?
#def gt(*libraries, env=False):
#    import __builtin__
#    __builtins__.update({"libraries": libraries})

def opt(option):
    return utils.opt(option, cmd_options, default_options, valid_opts)

def config_decide(option, secondary=None, appends=['--enable-', '--disable-']):
    result = []

    option = [o for o in option.split(" ") if o.strip().isalnum()]
    if secondary:
        secondary = [s for s in secondary.split(" ") if s.strip().isalnum()]

    #if len(option) > 1 and secondary and len(secondary) > 1:

    def secondary_add(keyword):
        if secondary is None:
            result.append(keyword+single_opt)
        else:
            for sec in secondary:
                result.append(keyword+sec)
 
    for single_opt in option:
        if not single_opt in options:
            out.warn_notify("%s is an invalid option." % single_opt)
            continue
        
        if opt(single_opt):
            secondary_add(appends[0])
        else:
            secondary_add(appends[1])

    return " ".join(result)

def config_enable(option, secondary=None):
    return config_decide(option, secondary)

def config_with(option, secondary=None):
    return config_decide(option, secondary, appends=['--with-', '--without-'])

def export(variable, value):
    os.environ[variable] = value

def get_env(value):
    return os.environ[value]

def makedirs(target):
    if inspect.stack()[1][3] == "install":
        shelltools.makedirs(prepare_target(target))
    else:
        shelltools.makedirs(target)

def touch(path):
    shelltools.touch(path)

def echo(content, target):
    shelltools.echo(content, target)

def isfile(path):
    return shelltools.is_file(path)

def isdir(path):
    return shelltools.is_dir(path)

def realpath(path):
    return shelltools.real_path(path)

def basename(path):
    return shelltools.basename(path)

def dirname(path):
    return shelltools.dirname(path)

def isempty(path):
    return shelltools.is_empty(path)

def ls(source):
    return shelltools.listdir(source)

def islink(source):
    return shelltools.is_link(source)

def isfile(source):
    return shelltools.is_file(source)

def isexists(source):
    return shelltools.is_exists(source)

def cd(target=None):
    shelltools.cd(target)

def copytree(source, target, sym=True):
    shelltools.copytree(source, prepare_target(target), sym)

def copy(source, target, sym=True):
    if current_stage == "install":
        shelltools.copy(source, prepare_target(target), sym)
    else:
        shelltools.copy(source, target, sym)

def move(source, target):
    shelltools.move(source, prepare_target(target))

def insinto(source, target, target_file='', sym=True):
    target = prepare_target(target)
    shelltools.makedirs(os.path.dirname(target))
    shelltools.insinto(source, target, install_dir, target_file, sym)

def insfile(source, target):
    target = prepare_target(target)
    shelltools.makedirs(os.path.dirname(target))
    return shelltools.install_readable([source], target)

def makesym(source, target):
    if current_stage == "install":
    #if inspect.stack()[1][3] == "install":
        target = prepare_target(target)
    if len(target.split("/")) > 1:
        shelltools.makedirs(os.path.dirname(target))
    shelltools.make_symlink(source, target)

def rename(source, target):
    shelltools.rename(prepare_target(source), 
                prepare_target(os.path.join(os.path.dirname(source), target)))

def rmfile(target):
    if current_stage == "install":
        target = prepare_target(target)
    src = glob.glob(target)
    if len(src) == 0:
        lpms.catch_error("no file matched pattern: %s" % target)
    
    for path in src:
        shelltools.remove_file(path)

def rmdir(target):
    if current_stage == "install":
        target = prepare_target(target)
    src = glob.glob(target)
    if len(src) == 0:
        lpms.catch_error("no directory matched pattern: %s" % target)
    
    for path in src:
        shelltools.remove_dir(path)

def setmod(*parameters):
    if not system('chmod %s' % " ".join(parameters)):
        lpms.terminate('setmod %s' % " ".join(parameters)+" failed.")

def setowner(*parameters):
    if not system('chown %s' % " ".join(parameters)):
        lpms.terminate('setowner %s' % " ".join(parameters)+" failed.")

def setgroup(*parameters):
    if not system('chgrp %s' % " ".join(parameters)):
        lpms.terminate('setgroup %s' % " ".join(parameters)+" failed.")

def sed(*parameters):
    if not system('sed %s' % " ".join(parameters)):
        lpms.terminate('sed %s' % " ".join(parameters)+" failed.")

def pwd():
    return os.getcwd()

def apply_patch(patches, level, reverse):
    for patch in patches:
        out.notify("applying patch %s" % out.color(basename(patch), "green"))
        ret = shelltools.system("patch --remove-empty-files --no-backup-if-mismatch %s -p%d -i \"%s\"" % 
                (reverse, level, patch), show=False)
        if not ret: return False

def patch(*args, **kwarg):
    level = 0; reverse = ""
    if "level" in kwarg:
        level = kwarg["level"]
    if "reverse" in kwarg and kwarg["reverse"]:
        reverse = "-R"

    if not args:
        patch_dir = os.path.join(cst.repos, repo, category, pkgname, cst.files_dir)
        if "location" in kwarg:
            patch_dir = kwarg.get("location")

        patches = glob.glob(patch_dir+"/*"+cst.patch_suffix)
        if not ptch:
            lpms.catch_error("no patch found in \'files\' directory.")
        if apply_patch(patches, level, reverse) is not None:
            lpms.catch_error("patch failed.")
        return 

    patches = []
    for patch_name in args:
        if repo != "local":
            src = os.path.join(cst.repos, repo, category, pkgname, cst.files_dir, patch_name)
            if "location" in kwarg:
                src = os.path.join(kwarg.get("location"), patch_name)
        else:
            # local repository feature is not in use.
            src = os.path.join(dirname(spec), cst.files_dir, patch_name)

        if patch_name.endswith(cst.patch_suffix):
            ptch = glob.glob(src)
            if not ptch:
                lpms.catch_error("%s not found!" % patch_name)
            patches.extend(ptch)
        else:
            if os.path.isdir(src):
                ptch = glob.glob(src+"/*")
                if not ptch:
                    lpms.catch_error("%s is an directory and it is not involve any files." % patch_name)
                patches.extend(ptch)
            elif os.path.isfile(src):
                ptch = glob.glob(src)
                if not ptch:
                    lpms.catch_error("%s not found." % patch_name)
                patches.extend(ptch)

    if apply_patch(patches, level, reverse) is not None:
        lpms.catch_error("patch failed.")

def insexe(source, target='/usr/bin'):
    target = prepare_target(target)
    shelltools.makedirs(os.path.dirname(target))
    return shelltools.install_executable([source], target)

def system(*cmd):
    result = shelltools.system(" ".join(cmd), stage = current_stage)
    if isinstance(result, bool):
        return result

    if len(result) == 2:
        if result[1]:
            logfile =  "%s/build.log" % dirname(dirname(build_dir))
            if isfile(logfile):
                shelltools.remove_file(logfile)
            echo(result[1],logfile)
            out.normal("for detalied output, view %s" % logfile)
        return result[0]
    return result

def joinpath(*args):
    return "/".join(args)

# output commands

def notify(msg):
    out.notify(msg)

def warn(msg):
    out.warn_notify(msg)

def error(msg):
    out.error(msg)

def write(msg):
    out.write(msg)

def color(msg, color):
    return out.color(msg, color)

