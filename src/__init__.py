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
import logging
import inspect

from lpms import out
from lpms import constants as cst

def terminate(msg=None):
    if msg is not None:
        sys.stdout.write(out.color(msg, "brightred")+'\n')
    raise SystemExit(0)

def getopt(opt):
    if opt in sys.argv:
        return True

# FIXME-1: The following is an ungodly hack. Fuck it, remove it, re-write it!
# FIXME-2: improve this for detalied debug output.
def catch_error(err, stage=0):
    backtree = inspect.stack()
    for i in backtree: 
        if len(i[1].split("interpreter.py")) > 1:
            for x in backtree:
                if x[-1] is None and x[-2] is None:
                    out.brightred("\n>> internal error:\n")
                    index = backtree.index(x)+1
                    out.write(" "+out.color(x[3]+" ("+"line "+str(backtree[index][2])+")", "red")+": "+str(err)+'\n\n')
                    terminate()
    print(err)
    terminate()


def init_logging():
    logger = None
    if os.access(cst.logfile, os.W_OK):
        logger = logging.getLogger(__name__)
        hdlr = logging.FileHandler(cst.logfile)
        formatter = logging.Formatter('%(created)f %(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr)
        logger.setLevel(logging.INFO)
    return logger

# lpms uses utf-8 encoding as default
reload(sys)
sys.setdefaultencoding('utf-8')

# initialize logging feature
logger = init_logging()
