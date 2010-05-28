#
# NXCCS Thumbnailer - get a thumbnail out of anything
# Copyright (C) 2010  736 Computing Services Limited
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import yaml

_stream = file("config.yaml", "r")
_config = yaml.load(_stream)

def get(option="all"):
    if option=="all":
        return _config
    else:
        return _config[option]

def urliser(*args, **kwargs):
    services_list = _config['screenshotters']
    url_list = []
    for item in services_list:
        uri = item['url']
        uri = uri.replace("{maxwidth}", str(kwargs['maxwidth']))
        uri = uri.replace("{maxheight}", str(kwargs['maxheight']))
        uri = uri.replace("{url}", str(kwargs['url']))
        url_list.append(uri)
    
    return url_list
