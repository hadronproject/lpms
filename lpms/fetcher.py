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


# get standart python libraries
import os
import sys
import time
import urllib2
import urlparse
import subprocess

# get lpms functions
import lpms
from lpms import out
from lpms import constants
from lpms import shelltools
from lpms import conf
from lpms import utils

# simple file downloader for lpms 
# based on http://stackoverflow.com/questions/2028517/python-urllib2-progress-hook

# TODO LIST: 
# 1-add resume support
# 2-show estimated time and download speed

# URLfether only works with url, url must be came as a list

config = conf.LPMSConfig()

class URLFetcher:
    def __init__(self):
        self.chunk_size = 8192
        self.begining  = time.time()
        
    def estimated_time(self, current_size, total_size, time):
        # odun, great job! :p
        if current_size == 0:
            current_size = 1
        elapsed  = (total_size*(time/current_size)-time)        
        # 1 = >> hour
        # 2 = >> minute
        # 3 = >> second
        return "[%.2d:%.2d:%.2d]" % ((elapsed/3600), ((elapsed%3600/60)), (elapsed%60))
    
    def fetcher_ui(self, bytes_so_far, total_size, filename):
        # our ui :) no progress bar or others...
        sys.stdout.write(
                "\r%s %s/%s (%0.2f%%) %s" %(
                    out.color(filename, "brightwhite"),
                    str(bytes_so_far/1024) + "kb", 
                    str(total_size/1024) + "kb", 
                    round((float(bytes_so_far) / total_size)*100, 2), 
                    self.estimated_time((bytes_so_far/1024), (total_size/1024), (time.time()-self.begining)))
                )

        if bytes_so_far >= total_size:
            sys.stdout.write('\n')
        sys.stdout.flush()

    def download(self, url, location=None, report_hook=None):
        # ui.debug("URL: "+str(url))
        try:
            response = urllib2.urlopen(url)
        except urllib2.URLError, e:
            out.error("%s cannot be downloaded" % out.color(url, "brightwhite"))
            return False
        except urllib2.HTTPError, e:
            out.error("%s cannot be downloaded" % out.color(url, "brightwhite"))
            return False

        filename = urlparse.urlparse(url, "file")[2].split("/")[-1]
        #ui.debug("File name: "+ fileName)
        if location is None:
            localfile = os.path.join(config.src_cache, filename)
        else:
            localfile = os.path.join(location, filename)
        #ui.debug("Destination: "+localFile)
        partfile = localfile + ".part"
        total_size = int(response.info().getheader('Content-Length').strip())
        bytes_so_far = 0
        
        file = open(partfile, "wb")
        
        while True:
            chunk = response.read(self.chunksize)
            bytes_so_far += len(chunk)
            if not chunk:
                break
            if report_hook:
                report_hook(bytes_so_far, total_size, filename)	
                file.write(chunk)
                
        file.flush()
        file.close()
        
        if os.stat(str(partfile)).st_size == 0:
            os.remove(partfile)
        move(partfile, localfile)
        return bytes_so_far
    
    # use external program to retrieve package sources
    
    def external_fetcher(self, command, download_plan, location):
        # run command
        def fetch(command, download_plan, location):
            #current = os.getcwd()
            if location is not None:
                os.chdir(location)
            else:
                os.chdir(config.src_cache)
            for url in download_plan:
                localfile = os.path.basename(url)
                partfile  = localfile+".part"
                output = shelltools.system(command+" "+partfile+" "+url, show=True, sandbox=False)
                if not output:
                    out.error(url+" cannot be downloaded")
                    return False
                else:
                    shelltools.move(partfile, localfile)
            #os.chdir(current)
            return True

        # parse fetch command
        realcommand = command.split(" ")[0]
        isexist = False
        if realcommand.startswith("/"):
            if not os.path.isfile(realcommand):
                out.error(out.color("EXTERNAL FETCH COMMAND: ", "red")+realcommand+" not found!")
                lpms.terminate()
            return fetch(command, download_plan, location)
        else:
            for syspath in os.environ["PATH"].split(":"):
                if os.path.isfile(os.path.join(syspath, realcommand)):
                    # this is no good
                    isexist = True
                    return fetch(command, download_plan, location)
            if not isexist:
                out.error(out.color("EXTERNAL FETCH COMMAND: ", "red")+realcommand+" not found!")
                lpms.terminate()

    # download_plan is a list that must contain urls
    def run(self, download_plan, location=None):
        # this is no good!
        if config.external_fetcher:
            return self.external_fetcher(config.fetch_command, download_plan, location)
        else:
            for url in download_plan:
                return self.download(url, location, report_hook=self.fetcher_ui)

