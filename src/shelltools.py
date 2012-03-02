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
import sys
import glob
import shutil
import time
import subprocess

import lpms 
from lpms import out
from lpms import conf
from lpms import exceptions
from lpms import constants as cst

def binary_isexists(binary):
    path = os.environ['PATH'].split(':')
    for directory in path:
        if os.path.exists(os.path.join(directory, binary)):
            return True
    return False

def makedirs(target):
    try:
        if not os.access(target, os.F_OK):
            os.makedirs(target)
    except OSError as err:
        raise exceptions.BuiltinError("[makedirs] an error occured: %s" % target)

def is_link(source):
    return os.path.islink(source)

def is_file(source):
    return os.path.isfile(source)

def is_exists(source):
    return os.path.exists(source)

def is_dir(source):
    return os.path.isdir(source)

def real_path(path):
    return os.path.realpath(path)

def is_empty(path):
    return os.path.getsize(path) == 0

def basename(path):
    return os.path.basename(path)

def dirname(path):
    return os.path.dirname(path)

def echo(content, target):
    mode = "a"
    if not os.path.isfile(target):
        mode = "w"

    try:
        with open(target, mode) as _file:
            _file.write('%s\n' % content)
    except IOError as err:
        raise exceptions.BuiltinError("[echo] given content was not written to %s" % target)

def listdir(source):
    if os.path.isdir(source):
        return os.listdir(source)
    else:
        return glob.glob(source)

# FIXME: exception?
def cd(target=None):
    current = os.getcwd()
    def change(trgt):
        try:
            os.chdir(trgt)
        except OSError as err:
            raise exceptions.BuiltinError("[cd] directory was not changed: %s" % trgt)

    if target is None:
        change(os.path.dirname(current))
    else:
        change(target)

def touch(path):
    if os.path.isfile(path):
        out.warn("%s is already exist" % path)
        return
    open(path, 'w').close()

def system(cmd, show=False, stage=None, sandbox=None):
    cfg = conf.LPMSConfig()
    if sandbox is None:
        sandbox = True if cfg.sandbox else False
        # override 'sandbox' variable if the user wants to modifiy from cli
        if lpms.getopt('--enable-sandbox'): 
            sandbox = True
        elif lpms.getopt('--disable-sandbox'):
            sandbox = False
    if lpms.getopt("--verbose"):
        ret, output, err = run_cmd(cmd, True)
    elif (not cfg.print_output or lpms.getopt("--quiet")) \
            and not show:
                ret, output, err = run_cmd(cmd, show=False, enable_sandbox=sandbox)
    else:
        ret, output, err = run_cmd(cmd, show=True, enable_sandbox=sandbox)

    if ret != 0:
        if not conf.LPMSConfig().print_output or lpms.getopt("--quiet"): 
            out.brightred("\n>> error messages:\n")
            out.write(err)
        out.warn("command failed: %s" % out.color(cmd, "red"))
        if stage and output and err:
            return False, output+err
        return False
    return True

def run_cmd(cmd, show=True, enable_sandbox=True):
    stdout = None; stderr = None
    if enable_sandbox:
        # FIXME: getopt should not do this.
        # the verbosity of messages, defaults to 1
        # 1 - error
        # 2 - warning
        # 3 - normal
        # 4 - verbose
        # 5 - debug
        # 6 - crazy debug
        log_level = lpms.getopt("--sandbox-log-level", like=True)
        if log_level is None:
            log_level = "1"
        if not log_level in ('1', '2', '3', '4', '5', '6'):
            out.warn("%s is an invalid sandbox log level." % log_level)
        cmd = "%s --config=%s --log-level=%s --log-file=%s -- %s" % (cst.sandbox_app, cst.sandbox_config, \
                log_level, cst.sandbox_log, cmd)
    if not show:
        stdout = subprocess.PIPE; stderr=subprocess.PIPE
    result = subprocess.Popen(cmd, shell=True, stdout=stdout, stderr=stderr)
    output, err = result.communicate()
    return result.returncode, output, err


def copytree(source, target, sym=True):
    if is_dir(source):
        if os.path.exists(target):
            if is_dir(target):
                copytree(source, os.path.join(target, os.path.basename(source.strip('/'))))
                return
            else:
                copytree(source, os.path.join(target, os.path.basename(source)))
                return
        try:
            shutil.copytree(source, target, sym)
        except OSError as err:
            raise exceptions.BuiltinError("[copytree] an error occured while copying: %s -> %s" % (source, target))
    else:
        raise exceptions.BuiltinError("[copytree] %s does not exists" % source, stage=1)

def move(source, target):
    src = glob.glob(source)
    if len(src) == 0:
        raise exceptions.BuiltinError("[move] %s is empty" % source)

    if len(target.split("/")) > 1 and not os.path.isdir(os.path.dirname(target)):
        makedirs(os.path.dirname(target))

    for path in src:
        if is_file(path) or is_link(path) or is_dir(path):
            try:
               shutil.move(path, target)
            except OSError as err:
                raise exceptions.BuiltinError("[move] an error occured while moving: %s -> %s" % (source, target))
        else:
            raise exceptions.BuiltinError("[move] file %s doesn\'t exists." % path)

def copy(source, target, sym = True):
    src= glob.glob(source)
    if len(src) == 0:
        raise exceptions.BuiltinError("[copy] no file matched pattern %s." % source)

    if len(target.split("/")) > 1 and not os.path.exists(os.path.dirname(target)):
        makedirs(os.path.dirname(target))

    for path in src:
        if is_file(path) and not is_link(path):
            try:
                shutil.copy2(path, target)
            except IOError as err:
                raise exceptions.BuiltinError("[copy] an error occured while copying: %s -> %s" % (source, target))

        elif is_link(path) and sym:
            if is_dir(target):
                os.symlink(os.readlink(path), os.path.join(target, os.path.basename(path)))
            else:
                if is_file(target):
                    os.remove(target)
                os.symlink(os.readlink(path), target)
        elif is_link(path) and not sym:
            if is_dir(path):
                copytree(path, target)
            else:
                shutil.copy2(path, target)
        elif is_dir(path):
            copytree(path, target, sym)
        else:
            raise exceptions.BuiltinError('[copy] file %s does not exist.' % filePath)

def insinto(source, target, install_dir=None, target_file = '', sym = True):
    if install_dir is not None:
        target = os.path.join(install_dir, target)
    
    makedirs(target)

    if not target_file:
        src = glob.glob(source)
        if len(src) == 0:
            raise exceptions.BuiltinError("[instinto] no file matched pattern %s." % source)

        for path in src:
            if os.access(path, os.F_OK):
                copy(path, os.path.join(target, os.path.basename(path)), sym)
    else:
        copy(source, os.path.join(target, target_file), sym)

def make_symlink(source, target):
    try:
        os.symlink(source, target)
    except OSError as err:
        raise exceptions.BuiltinError("[make_symlink] symlink not created: %s -> %s" % (target, source))

def remove_file(pattern):
    src = glob.glob(pattern)
    if len(src) == 0:
        out.error("[remove_file] no file matched pattern: %s." % pattern)
        return False

    for path in src:
        if is_link(path):
            try:
                os.unlink(path)
            except OSError as err:
                raise exceptions.BuiltinError("[remove_file] an error occured: %s" % path)
        elif is_file(path):
            try:
                os.remove(path)
            except OSError as err:
                raise exceptions.BuiltinError("[remove_file] an error occured: %s" % path)
        elif not is_dir(path):
            out.error("[remove_file] file %s doesn\'t exists." % path)
            return False

def remove_dir(source_dir):
    if is_link(source_dir):
        os.unlink(source_dir)
        return

    if is_dir(source_dir):
        try:
            # rmtree gets string
            shutil.rmtree(str(source_dir))
        except OSError as err:
            raise exceptions.BuiltinError("[remove_dir] an error occured while removing: %s" % source_dir)
    elif is_file(source_dir):
        pass
    else:
        out.error("[remove_dir] directory %s doesn\'t exists." % source_dir)
        return False

def rename(source, target):
    try:
        os.rename(source, target)
    except OSError as err:
        raise exceptions.BuiltinError("an error occured while renaming: %s -> %s" % (source, target))

def install_executable(sources, target):
    if not os.path.isdir(os.path.dirname(target)):
        makedirs(os.path.dirname(target))

    for source in sources:
        srcs = glob.glob(source)
        if len(srcs) == 0:
            raise exceptions.BuiltinError("[install_executable] file not found: %s" % source)

        for src in srcs:
            if not system('install -m0755 -o root -g root %s %s' % (src, target)):
                out.error("[install_executable] %s could not installed to %s" % (src, target))
                return False

def install_readable(sources, target):
    #FIXME: Does the function create target directory?
    # what if target value is a file(insfile)??

    for source in sources:
        srcs = glob.glob(source)
        if len(srcs) == 0:
            out.error("[install_readable] file not found: %s" % source)
            return False

        for src in srcs:
            if not system('install -m0644 "%s" %s' % (src, target)):
                out.error("[install_readable] %s could not installed to %s." % (src, target))
                return False

def install_library(source, target, permission = 0644):
    if not os.path.isdir(os.path.dirname(target)):
        makedirs(os.path.dirname(target))
    
    if os.path.islink(source):
        os.symlink(os.path.realpath(source), os.path.join(target, source))
    else:
        if not system('install -m0%o %s %s' % (permission, source, target)):
            out.error("[install_library] %s could not installed to %s." % (src, target))
            return False

def set_id(path, uid, gid):
    os.chown(path, uid, gid)

def set_mod(path, mod):
    os.chmod(path, mod)

