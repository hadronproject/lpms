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
import sys

import lpms
from lpms import conf

# color codes were borrowed from PiSi
colors = {
        'black'              : "\033[30m",
        'red'                : "\033[31m",
        'green'              : "\033[32m",
        'yellow'             : "\033[33m",
        'blue'               : "\033[34m",
        'purple'             : "\033[35m",
        'cyan'               : "\033[36m",
        'white'              : "\033[37m",
        'brightblack'        : "\033[01;30m",
        'brightred'          : "\033[01;31m",
        'brightgreen'        : "\033[01;32m",
        'brightyellow'       : "\033[01;33m",
        'brightblue'         : "\033[01;34m",
        'brightmagenta'      : "\033[01;35m",
        'brightcyan'         : "\033[01;36m",
        'brightwhite'        : "\033[01;37m",
        'underlineblack'     : "\033[04;30m",
        'underlinered'       : "\033[04;31m",
        'underlinegreen'     : "\033[04;32m",
        'underlineyellow'    : "\033[04;33m",
        'underlineblue'      : "\033[04;34m",
        'underlinemagenta'   : "\033[04;35m",
        'underlinecyan'      : "\033[04;36m",
        'underlinewhite'     : "\033[04;37m",
        'blinkingblack'      : "\033[05;30m",
        'blinkingred'        : "\033[05;31m",
        'blinkinggreen'      : "\033[05;32m",
        'blinkingyellow'     : "\033[05;33m",
        'blinkingblue'       : "\033[05;34m",
        'blinkingmagenta'    : "\033[05;35m",
        'blinkingcyan'       : "\033[05;36m",
        'blinkingwhite'      : "\033[05;37m",
        'backgroundblack'    : "\033[07;30m",
        'backgroundred'      : "\033[07;31m",
        'backgroundgreen'    : "\033[07;32m",
        'backgroundyellow'   : "\033[07;33m",
        'backgroundblue'     : "\033[07;34m",
        'backgroundmagenta'  : "\033[07;35m",
        'backgroundcyan'     : "\033[07;36m",
        'backgroundwhite'    : "\033[07;37m",
        'default'            : "\033[0m"
}

def scrub(string):
    p = re.compile('\033\[[0-9;]+m')
    return p.sub('', string)

def color(msg, cl):
    if lpms.getopt("--no-color") or lpms.getopt("-n") or not conf.LPMSConfig().colorize:
        return msg
    return colors[cl] + msg + colors['default']

def write(msg, log=True):
    sys.stdout.write(msg)

def normal(msg, log=False, ch=None):
    #lpms.logger.info(msg)
    if ch is None:
        ch = '\n'
    write(color(">> ", "brightgreen")+msg+ch)

def error(msg, log=False, ch=None):
    #lpms.logger.error(msg)
    if ch is None:
        ch = '\n'
    write(color("!! ", "brightred")+msg+ch)

def warn(msg, log=False, ch=None):
    #lpms.logger.warning(msg)
    if ch is None:
        ch = '\n'
    write(color("** ", "brightyellow")+msg+ch)

def green(msg):
    write(color(msg, "green"))

def red(msg):
    write(color(msg, "red"))

def brightred(msg):
    write(color(msg, "brightred"))

def brightgreen(msg):
    write(color(msg, "brightgreen"))

def yellow(msg):
    write(color(msg, "brightyellow"))

def brightwhite(msg):
    write(color(msg, "brightwhite"))

def warn_notify(msg):
    write(color(" * ", "brightyellow")+msg+"\n")

def notify(msg):
    write(color(" * ", "green")+msg+"\n")
