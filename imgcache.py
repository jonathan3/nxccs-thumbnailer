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

import sys
sys.path.insert(0, 'boto.zip')

from google.appengine.api import images, urlfetch
from boto.s3.connection import S3Connection
from boto.exception import S3ResponseError
from boto.s3.key import Key
import logging, random, settings

conn = S3Connection(settings.get('aws_key'), settings.get('aws_secret_key'))

def cachetos3(urls, width=0, height=0):
    bucket_name = settings.get('s3_bucket_name')
    done = False
    count = 0
    
    # Download the image
    while done == False:
        try:
            fetch = urlfetch.fetch(urls[count])
            image_data = fetch.content
            try:
                # hideous thumbalizr API-specific hack that barely works, if at all
                if fetch.headers['x-thumbalizr-status'] == "QUEUED":
                    logging.debug("The thumbnail sent to Thumbalizr is queued. Skipping to next service.")
                    raise urlfetch.DownloadError
            except:
                pass
            
            done = True
        except urlfetch.DownloadError:
            count += 1
            done = False
        except IndexError:
            done = True
            return "http://imgur.com/LivtZ.png"
    
    # Create the filename
    bckt = conn.create_bucket(settings.get('s3_bucket_name'))
    key = Key(bckt)
    filename = "%s.png" % (''.join([random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for x in xrange(27)]))
    key.key = filename
    
    # Resize the image if a size is specified
    if width!=0 and height!=0:
        image_data = images.resize(str(image_data), width=int(width), height=int(height), output_encoding=images.PNG)
    
    # Upload it to Amazon S3 and set it to public
    key.set_contents_from_string(image_data, headers={'Content-Type': 'image/png'})
    key.set_acl('public-read')
    
    # Return the URL
    return "https://s3.amazonaws.com/%s/%s" % (bucket_name, filename)
