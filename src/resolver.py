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

# dependency resolver

def preprocessor(data):
    '''A function that preprocess dependency data which from database or build
    scripts. It returns a list and dictonary that contain dependencies and options'''
    # I know, the code is ugly, but works!
    optional = {}; opt = None; deps = []
    for line in data:
        if '(' in list(line):
            atom = line.split('(')
            if len(atom[1].split(')')) == 2:
                optional[atom[0]] = []
                optional[atom[0]].append(atom[1].split(')')[0])
            else:
                opt = atom[0]
                optional[opt] = [atom[1]]
        elif ')' in list(line):
            atom = line.split(')')
            optional[opt].append(atom[0])
        else:
            deps.append(line)
    return optional, deps

