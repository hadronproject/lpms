# Copyright 2009 - 2012 Burak Sezer <purak@hadronproject.org>
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

from lpms.exceptions import ItemNotFound

class LCollect(object):
    def __init__(self, **kwargs):
        for kwarg in kwargs:
            if isinstance(kwargs[kwarg], basestring):
                setattr(self, kwarg, kwargs[kwarg].decode("UTF-8"))
            else:
                setattr(self, kwarg, kwargs[kwarg])
            
    def __setattr__(self, item, value):
        if isinstance(value, basestring):
            self.__dict__[item] = value.decode('UTF-8')
        else:
            self.__dict__[item] = value
        
    def __getattr__(self, item):
        if not item in self.__dict__:
            raise ItemNotFound("%s not found in LCollect object." % item)
        return self.__dict__[item]
    
    def __delattr__(self, item):
        if not item in self.__dict__:
            raise ItemNotFound("%s not found in LCollect object." % item)
        del self.__dict__[item]

    def get_raw_dict(self):
        return self.__dict__

class PackageItem(list):
    def get(self, index):
        return self[index]

    def add(self, item):
        if not item in self:
            self.append(item)

    def check_pk(self, pk):
        for element in self:
            if pk == element.pk:
                return self.index(element)

    def add_by_pk(self, item):
        for element in self:
            if element.pk == item.pk:
                return self.index(element)
        self.append(item)

    def length(self):
        return len(self)

    def get_raw_dict(self):
        return [i.__dict__ for i in self]


