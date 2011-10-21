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

import lpms
from lpms import out
from lpms import news
from lpms import utils
from lpms import constants as cst

__version__ = "0.1"

class News(object):
    def __init__(self, command_line):
        self.command_line = command_line
        self.cursor = news.News()

    def usage(self):
        out.normal("news reader for lpms")
        out.write("Use 'list' command to list available messages. For reading these messages, use read <id>\n")

    def list_news(self):
        self.cursor.get_all_news()
        i = 0
        if not self.cursor.data:
            out.warn("no readable news.")
            return
        out.normal("readable messages listed:")
        for news in self.cursor.data:
            repo, metadata = news[:-1]
            out.write("[%s] \t %s\n" % (out.color(str(i), "green"), metadata["summary"]))
            i += 1

    def read_news(self, news_id):
        try:
            news_id = int(news_id)
            repo, metadata, message = self.cursor.data[news_id]
        except ValueError:
            out.error("invalid id: %s" % news_id)
            return
        except IndexError:
            out.error("message found not found with this id: %d" % news_id)
            return

        out.write(out.color("from", "green")+": "+metadata["from"]+"\n")
        out.write(out.color("summary", "green")+": "+metadata["summary"]+"\n")
        out.write(out.color("date", "green")+": "+metadata["date"]+"\n")
        out.write(out.color("priority", "green")+": "+metadata["priority"]+"\n")
        out.write(message+"\n")

    def main(self):
        if not self.command_line:
            out.error("no command given.")
            return

        for command in self.command_line:
            if command == "list":
                self.list_news()
                return
            elif command == "read":
                id_index = self.command_line.index(command) + 1
                try:
                    self.cursor.get_all_news()
                    news_id = self.command_line[id_index]
                    self.read_news(news_id)
                    return
                except IndexError:
                    out.error("you must give a index number!")
                    return
            elif command in ("--help", "-h"):
                self.usage()
                return
            elif command in ("--help", "-h"):
                out.write("lnews %s\n" % __version__)
                return
            else:
                out.error("invalid command: %s" % command)
                return
