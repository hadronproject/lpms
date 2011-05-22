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
from lpms import conf as cfg
from lpms import constants as cst
from lpms import out
from lpms.exceptions import *
from lpms import shelltools


def standard_setup(*parameters):
    pass

def standard_configure(*parameters):
    return conf(*parameters)

def standard_install(parameters='', arg='install'):
    return linstall(parameters='', arg='install')

def standard_build(*parameters):
    return make(*parameters)

def conf(*args, **kwargs):
    conf_script = 'configure'
    if "run_dir" in kwargs:
        conf_script = os.path.join(kwargs["run_dir"], conf_script)

    if os.access(conf_script, os.F_OK):
        if os.access(conf_script, os.X_OK):
            args = 'sh %s \
                --prefix=/%s \
                --build=%s \
                --mandir=/%s \
                --infodir=/%s \
                --datadir=/%s \
                --sysconfdir=/%s \
                --localstatedir=/%s \
                --libexecdir=/%s \
                %s' % (conf_script, cst.prefix, \
                cfg.LPMSConfig().CHOST, cst.man, \
                cst.info, cst.data, \
                cst.conf, cst.localstate, cst.libexec, " ".join(args))
            args = " ".join([member for member in args.split(" ") if member != ""])
            if not shelltools.system(args):
                lpms.terminate()
        else:
            #FIXME: bu bir hata mı yoksa yapilmasi gerekenler mi var?
            out.warn("configure script is not executable.")
    else:
        out.warn("no configure script found.")

def raw_configure(*parameters):
    if not shelltools.system("./configure %s" % " ".join(parameters)):
        lpms.terminate()

def make(*parameters, **kwargs):
    if "j" in kwargs:
        jobs = "-j"+str(kwargs["j"])
    else:
        jobs = cfg.LPMSConfig().MAKEOPTS

    if not shelltools.system("make %s %s" % (str(jobs), " ".join(parameters))):
        lpms.catch_error("make failed.")

def raw_install(parameters = '', arg='install'):
    if not shelltools.system("make %s %s" % (parameters, arg)):
        lpms.catch_error("raw_install() function failed.")

def linstall(parameters='', arg='install'):
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
    if not shelltools.system(args):
        lpms.catch_error("listall failed.")

def aclocal(*parameters):
    if not shelltools.system("aclocal %s" % " ".join(parameters)):
        lpms.catch_error("aclocal failed.")

def libtoolize(*parameters):
    if not shelltools.system("libtoolize %s" % " ".join(parameters)):
        lpms.catch_error("libtoolize failed.")

def autoconf(*parameters):
    if not shelltools.system("autoconf %s" % " ".join(parameters)):
        lpms.catch_error("autoconf failed.")

def autoreconf(*parameters):
    if not shelltools.system("autoreconf %s" % " ".join(parameters)):
        lpms.catch_error("autoreconf failed.")

def automake(*parameters):
    if not shelltools.system("automake %s" % " ".join(parameters)):
        lpms.catch_error("automake failed.")

def autoheader(*parameters):
    if not shelltools.system("autoheader %s" % " ".join(parameters)):
        lpms.catch_error("autoheader failed.")

