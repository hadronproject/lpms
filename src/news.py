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
import cPickle as pickle

from lpms import out
from lpms import utils
from lpms import shelltools
from lpms import constants as cst

from collections import OrderedDict

metadata_keys = ('from', 'summary', 'date', 'priority')

class News(object):
    def __init__(self):
        self.news_read_file = os.path.join(cst.repos, cst.news_read)
        self.valid_repos = utils.valid_repos()
        self.data = []

    def import_repo_news(self, repo):
        '''Imports news of given repository'''
        my_news_dir = os.path.join(cst.repos, repo, cst.news_dir)
        if not os.path.isdir(my_news_dir):
            return
        
        for news in os.listdir(my_news_dir):
            local = utils.import_script(os.path.join(my_news_dir, news))
            try:
                metadata = utils.metadata_parser(local["metadata"], keys=metadata_keys)
            except IndexError:
                out.warn("Syntax errors found in %s" % os.path.join(my_news_dir, news))
                continue
            self.data.append((repo, metadata, local["message"]))

    def get_all_news(self):
        '''Collects available news'''
        for repo in self.valid_repos:
            self.import_repo_news(repo)

    def mark_as_read(self, item):
        if not os.path.isfile(self.news_read_file):
            with open(self.news_read_file, "wb") as raw_data:
                pickle.dump([item], raw_data)
        else:
            with open(self.news_read_file, "rb") as raw_data:
                data = pickle.load(raw_data)
                if not item in data:
                    data.append(item)
            shelltools.remove_file(self.news_read_file)
            with open(self.news_read_file, "wb") as raw_data:
                if not item in data:
                    data.append(item)
                pickle.dump(data, raw_data)

    def get_read_items(self):
        result = []
        if not os.path.isfile(self.news_read_file):
            return result
        with open(self.news_read_file, "rb") as raw_data:
            result = pickle.load(raw_data)
        return result
