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
from lpms import conf
from lpms import out

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
        out.error("[makedirs] an error occured: %s" % target)
        lpms.catch_error(err)

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

def echo(target, content):
    try:
        f = open(target, 'a')
        f.write('%s\n' % content)
        f.close()
    except IOError as err:
        out.error("[echo] given content was not written to %s" % target)
        lpms.catch_error(err, stage=1)

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
            out.error("[cd] directory was not changed: %s" % trgt)
            lpms.catch_error(err, stage=1)

    if target is None:
        change(os.path.dirname(current))
    else:
        change(target)

def touch(path):
    if os.path.isfile(path):
        out.warn("%s is already exist" % path)
    f = open(path, 'w')
    f.close()

def system(cmd, show=True):
    if run_cmd(cmd, show) != 0:
        out.warn("command failed: %s" % out.color(cmd, "red"))
        return False
    return True

def run_cmd(cmd, show=True):
    stdout = None; stderr = None
    if (not lpms.getopt("--print-output") and not conf.LPMSConfig().print_output) or not show:
        stdout = subprocess.PIPE; stderr=subprocess.PIPE
    result = subprocess.Popen(cmd, shell=True, stdout=stdout, stderr=stderr)
    out, err = result.communicate()
    return result.returncode


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
            out.error("[copytree] an error occured while copying: %s -> %s" % (source, target))
            lpms.catch_error(err)
    else:
        lpms.catch_error("[copytree] %s does not exists" % source, stage=1)

def move(source, target):
    src = glob.glob(source)
    if len(src) == 0:
        lpms.catch_error("[move] %s is empty" % source)

    if len(target.split("/")) > 1 and not os.path.isdir(os.path.dirname(target)):
        makedirs(os.path.dirname(target))

    for path in src:
        if is_file(path) or is_link(path) or is_dir(path):
            try:
               shutil.move(path, target)
            except OSError as err:
                out.error("[move] an error occured while moving: %s -> %s" % (source, target))
                lpms.catch_error(err)
        else:
            lpms.catch_error("[move] file %s doesn\'t exists." % path)

def copy(source, target, sym = True):
    src= glob.glob(source)
    if len(src) == 0:
        lpms.catch_error("[copy] no file matched pattern %s." % source)

    if not os.path.exists(os.path.dirname(target)):
        makedirs(os.path.dirname(target))

    for path in src:
        if is_file(path) and not is_link(path):
            try:
                shutil.copy2(path, target)
            except IOError as err:
                out.error("[copy] an error occured while copying: %s -> %s" % (source, target))
                lpms.catch_error(err)

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
            lpms.catch_error('[copy] file %s does not exist.' % filePath)

def insinto(source, target, install_dir=None, target_file = '', sym = True):
    if install_dir is not None:
        target = os.path.join(install_dir, target)
    
    makedirs(target)

    if not target_file:
        src = glob.glob(source)
        if len(src) == 0:
            lpms.catch_error("[instinto] no file matched pattern %s." % source)

        for path in src:
            if os.access(path, os.F_OK):
                copy(path, os.path.join(target, os.path.basename(path)), sym)
    else:
        copy(source, os.path.join(target, target_file), sym)

def make_symlink(source, target):
    try:
        os.symlink(source, target)
    except OSError as err:
        out.error("[make_symlink] symlink not created: %s -> %s" % (target, source))
        lpms.catch_error(err)

def remove_file(pattern):
    src = glob.glob(pattern)
    if len(src) == 0:
        out.error("[remove_file] no file matched pattern: %s." % pattern)
        return False

    for path in src:
        if is_file(path) or is_link(path):
            try:
                os.unlink(path)
            except OSError:
                out.error("[remove_file] an error occured: %s" % path)
                lpms.catch_error(err)

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
            out.error("[remove_dir] an error occured while removing: %s" % source_dir)
            lpms.catch_error(err)
    elif is_file(source_dir):
        pass
    else:
        out.error("[remove_dir] directory %s doesn\'t exists." % source_dir)
        return False

def rename(source, target):
    try:
        os.rename(source, target)
    except OSError as err:
        out.error("an error occured while renaming: %s -> %s" % (source, target))
        lpms.catch_error(err)

def install_executable(sources, target):
    if not os.path.isdir(os.path.dirname(target)):
        makedirs(os.path.dirname(target))

    for source in sources:
        srcs = glob.glob(source)
        if len(srcs) == 0:
            lpms.catch_error("[install_executable] file not found: %s" % source)

        for src in srcs:
            if not system('install -m0755 -o root -g root %s %s' % (src, target)):
                out.error("[install_executable] %s could not installed to %s" % (src, target))
                return False

def install_readable(sources, target):
    if not os.path.isdir(os.path.dirname(target)):
        makedirs(os.path.dirname(target))

    for source in sources:
        srcs = glob.glob(source)
        if len(srcs) == 0:
            out.error("[install_readable] file not found: %s" % source)
            return False

        for src in srcs:
            if not system('install -m0644 %s %s' % (src, target)):
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

