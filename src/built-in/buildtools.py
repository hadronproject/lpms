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
import subprocess

import lpms
from lpms import out
from lpms import archive
from lpms import shelltools
from lpms.exceptions import BuildError
from lpms import conf as cfg
from lpms import constants as cst


def standard_extract():
    target = os.path.dirname(build_dir)
    for url in extract_plan:
        out.write("   %s %s\n" % (out.color(">", "green"), os.path.join(cfg.LPMSConfig().src_cache,\
                    os.path.basename(url))))        
        archive_path = os.path.join(cfg.LPMSConfig().src_cache, os.path.basename(url))
        try:
            partial = [atom.strip() for atom in partial.split(" ") 
                    if atom != "#"]
            archive.extract(str(archive_path), str(target), partial)
        except NameError:
            archive.extract(str(archive_path), str(target))

def standard_configure(*parameters):
    '''Runs standard configuration function'''
    return conf(*parameters)

def standard_install(parameters='', arg='install'):
    '''Runs standard installation function'''
    return linstall(parameters='', arg='install')

def standard_build(*parameters):
    '''Runs standard build function'''
    return make(*parameters)

def conf(*args, **kwargs):
    '''Runs configure script with standard and given parameters'''
    conf_command = './configure'
    if "run_dir" in kwargs:
        conf_command = os.path.join(kwargs["run_dir"], "configure")

    if os.access(conf_command, os.F_OK):
        if os.access(conf_command, os.X_OK):
            args = '%s \
                --prefix=/%s \
                --build=%s \
                --mandir=/%s \
                --infodir=/%s \
                --datadir=/%s \
                --sysconfdir=/%s \
                --localstatedir=/%s \
                --libexecdir=/%s \
                %s' % (conf_command, cst.prefix, \
                cfg.LPMSConfig().CHOST, cst.man, \
                cst.info, cst.data, \
                cst.conf, cst.localstate, cst.libexec, " ".join(args))
            args = " ".join([member for member in args.split(" ") if member != ""])
            out.notify("running %s" % args)
            if not system(args):
                lpms.terminate()
        else:
            #FIXME: bu bir hata mı yoksa yapilmasi gerekenler mi var?
            out.warn("configure script is not executable.")
    else:
        out.warn("no configure script found.")

def raw_configure(*parameters):
    '''Runs configure script with only given parameters'''
    out.notify("running ./configure %s" % " ".join(parameters))
    if not system("./configure %s" % " ".join(parameters)):
        lpms.terminate()

def make(*parameters, **kwargs):
    '''Runs standard build command with given parameters'''
    if "j" in kwargs:
        jobs = "-j"+str(kwargs["j"])
    else:
        jobs = cfg.LPMSConfig().MAKEOPTS

    out.notify("running make %s %s" % (str(jobs), " ".join(parameters)))
    if not system("make %s %s" % (str(jobs), " ".join(parameters))):
        raise BuildError("make failed")

def raw_install(parameters = '', arg='install'):
    '''Runs installation function with only given parameters'''
    out.notify("running make %s %s" % (parameters, arg))
    if not system("make %s %s" % (parameters, arg)):
        raise BuildError("raw_install failed.")
    else:
        # remove /usr/share/info/dir file if it exists
        dir_file = "%s/usr/share/info/dir" % install_dir
        if os.path.isfile(dir_file):
            shelltools.remove_file("%s/usr/share/info/dir" % install_dir)

def linstall(parameters='', arg='install'):
    '''Runs standard installation function with given parameters and commands'''
    args = 'make prefix=%(prefix)s/%(defaultprefix)s \
            datadir=%(prefix)s/%(data)s \
            infodir=%(prefix)s/%(info)s \
            localstatedir=%(prefix)s/%(localstate)s \
            mandir=%(prefix)s/%(man)s \
            sysconfdir=%(prefix)s/%(conf)s \
            %(parameters)s \
            %(argument)s' % {
                    'prefix': install_dir,
                    'defaultprefix': cst.prefix,
                    'man': cst.man,
                    'info': cst.info,
                    'localstate': cst.localstate,
                    'conf': cst.conf,
                    'data': cst.data,
                    'parameters': parameters,
                    'argument': arg,
                    }

    args = " ".join([member for member in args.split(" ") if member != ""])
    out.notify("running %s" % args) 
    if not system(args):
        raise BuildError("linstall failed.")
    else:
        # remove /usr/share/info/dir file if it exists
        dir_file = "%s/usr/share/info/dir" % install_dir
        if os.path.isfile(dir_file):
            shelltools.remove_file("%s/usr/share/info/dir" % install_dir)

def aclocal(*parameters):
    '''Runs aclocal with given parameters'''
    command = " ".join(parameters)
    out.notify("running aclocal %s" % command)
    if not system("aclocal %s" % command):
        raise BuildError("aclocal failed.")

def intltoolize(*parameters):
    '''Runs intltoolize with given parameters'''
    command = " ".join(parameters)
    out.notify("running intltoolize %s" % command)
    if not system("intltoolize %s" % command):
        raise BuildError("intltoolize failed.")

def libtoolize(*parameters):
    '''Runs libtoolize with given parameters'''
    command = " ".join(parameters)
    out.notify("running libtoolize %s" % command)
    if not system("libtoolize %s" % command):
        raise BuildError("libtoolize failed.")

def autoconf(*parameters):
    '''Runs autoconf with given parameters'''
    command = " ".join(parameters)
    out.notify("running autoconf %s" % command)
    if not system("autoconf %s" % command):
        raise BuildError("autoconf failed.")

def autoreconf(*parameters):
    '''Runs autoreconf with given parameters'''
    command = " ".join(parameters)
    out.notify("running autoreconf %s" % command)
    if not system("autoreconf %s" % command):
        raise BuildError("autoreconf failed.")

def automake(*parameters):
    '''Runs automake with given parameters'''
    command = " ".join(parameters)
    out.notify("running automake %s" % command)
    if not system("automake %s" % command):
        raise BuildError("automake failed.")

def autoheader(*parameters):
    '''Runs autoheader with given parameters'''
    command = " ".join(parameters)
    out.notify("running autoheader %s" % command)
    if not system("autoheader %s" % command):
        raise BuildError("autoheader failed.")

def installd(*params, **kwargs):
    '''Runs raw_install with standard parameters'''
    arg = kwargs.get("arg", "install")
    raw_install("DESTDIR=%s %s" % (install_dir, " ".join(params)), arg)
