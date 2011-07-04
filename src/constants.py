# Copyright 2009 - 2011 Burak Sezer <burak.sezer@linux.org.tr>
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

import sys

environmental_files = ('builtins.py', 'buildtools.py')

root = "/"
xmlfile_suffix = ".xml"
lpms_path = "/usr/lib/python%s.%s/site-packages/lpms" % (sys.version_info[0], sys.version_info[1])
logfile = "/var/log/lpms.log"
user_dir = "/etc/lpms.user"
sets_dir = "sets"
user_sets_dir = user_dir+"/"+sets_dir
repo_conf = "/etc/lpms/repo.conf"
configure_pending_file = "var/tmp/configure_pending.lpms"
merge_conf_file = "var/tmp/merge_conf_file.lpms"
repo_file = "info/repo.conf"
repo_info = "info"
categories = "categories.xml"
files_dir = "files"
patch_suffix = ".patch"
repos = "/var/lib/lpms"
config_dir = "/etc/lpms"
db_path = "/var/db/lpms"
filesdb = "filesdb"
repositorydb_path = "/var/db/lpms/repositorydb.db"
installdb_path = "/var/db/lpms/installdb.db"
spec_suffix = ".py"
sandbox_file = "sandbox.conf"
spec_dir = "/usr/lpms"
config_file = "lpms.conf"
distfiles = "/usr/portage/distfiles"
extract_dir = "/var/tmp/lpms/"
resume_file = extract_dir+"/"+"resume"

doc = 'usr/share/doc'
sbin = 'usr/sbin'
man = 'usr/share/man'
info = 'usr/share/info'
data = 'usr/share'
conf = 'etc'
localstate = 'var'
libexec = 'usr/libexec'
prefix = 'usr'
