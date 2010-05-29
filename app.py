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

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import memcache, urlfetch
from Crypto.Hash import MD5
import re, oembed, urllib2, logging, imgcache, urlparse, settings

try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        try:
            import django.utils.simplejson as json
        except ImportError:
            raise ImportError("Need a json library")


class API(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = get_mimetype(self.request.get('format'))
        self.response.out.write(api(self))
    def post(self):
        self.response.headers['Content-Type'] = get_mimetype(self.request.get('format'))
        self.response.out.write(api(self))

# ugly hack
def get_mimetype(format):
    if format == "json":
        return 'application/json'
    else:
        return 'text/plain'

def generate_response(thumbnail_url="", width=0, height=0, format="plaintext", callback="", request=None):
    if format.lower() == "json":
        json_response = json.dumps({
            'type': 'photo',
            'version': '1.0',
            'provider_name': settings.get('provider_name'),
            'provider_url': settings.get('provider_url'),
            'cache_age': settings.get('suggested_cache_time'),
            'url': str(thumbnail_url),
            'height': height,
            'width': width,
        })

        if callback != "":
            logging.debug("Response format is JSONP (callback: %s).\nResponse: %s" % (callback, json_response))
            json_response = "%s(%s);" % (callback, json_response)
        else:
            logging.debug("Response format is JSON.\nResponse: %s" % json_response)
        return json_response
    elif format.lower() == "plaintext":
        logging.debug("Response format is Plaintext. Response: %s" % thumbnail_url)
        return thumbnail_url
    elif format.lower() == "redirect":
        # not implemented yet
        logging.debug("Response format is a 302 redirect to URL: %s" % thumbnail_url)
        return thumbnail_url
        
def is_mimetype_an_image(url):
    IMAGE_MIMETYPES = ['image/gif', 'image/jpeg', 'image/png']
    
    # Send a HEAD request to check the content-type
    response = urlfetch.fetch(url, method=urlfetch.HEAD, headers={"User-Agent": "Mozilla/5.0 NXCCS Thumbnailer"})
    content_type = response.headers['Content-Type'].split('; ')
    
    # Now compare the mimetype of the response against
    # our list of acceptable image mimetypes
    for mimetype in IMAGE_MIMETYPES:
        if content_type[0] == mimetype:
            return True
    
    return False

def does_url_exist(url):
    try:
        response = urlfetch.fetch(url, method=urlfetch.HEAD, headers={"User-Agent": "Mozilla/5.0 NXCCS Thumbnailer"})
    except:
        return False
    
    if response.status_code != 200 and response.status_code != 301 and response.status_code != 302:
        return False
    else:
        return True

def api(request):
    url =       request.request.get('url')
    format =    request.request.get('format')
    maxwidth =  request.request.get('maxwidth')
    maxheight = request.request.get('maxheight')
    callback =  request.request.get('callback')
    
    if format == "": format = "plaintext"
    if maxwidth == "": maxwidth = 320
    if maxheight == "": maxheight = 240
    
    maxwidth = int(maxwidth)
    maxheight = int(maxheight)
    
    #logging.debug("URL: %s - Format: %s - Size: %s x %s - Callback: %s" % (url, format, maxwidth, maxheight, callback))
    
    got_image = False
    needs_scale = False
    abort = False
    
    if url == "":
        request.error(404)
        return False
        
    # Check if we've already cached this request
    hashed_url = str(MD5.new(url).hexdigest())
    thumbnail = memcache.get(key=hashed_url)
    if not thumbnail:
        logging.debug("Thumbnail not found in memcache. Continuing.")
        got_image = False
    else:
        logging.debug("Using memcached response.")
        got_image = True
        return generate_response(thumbnail, maxwidth, maxheight, format, callback)
    
    # Then check if it exists
    if not does_url_exist(url):
        # Abort! Abort!
        logging.debug("URL does not exist. Aborting.")
        
        request.error(404)
        return False
    
    # Check if the URL returns an image mimetype
    if is_mimetype_an_image(url) == True:
        needs_scale = True
        got_image = True
        logging.debug("Mimetype of given URL matches image mimetypes. Image needs scaling.")
    else:
        got_image = False
        logging.debug("Mimetype of given URL is not an image. Continuing onto oEmbed tests.")
    
    # Check if the sizes are within the limits and enforce them
    if maxwidth!="" and maxheight!="":
        if maxwidth>640: maxwidth=640
        if maxheight>640: maxheight=640
    
    # oEmbed request
    oembed_request = oembed.get_oembed(url, maxwidth=maxwidth, maxheight=maxheight)
    if oembed_request != None:
        do_oembed = True
    else:
        logging.debug("oEmbed service doesn't like this URL. Skipping oEmbed.")
        do_oembed = False
    
    # Check to see if they provide a thumbnail
    if got_image == False and do_oembed == True:
        try:
            thumbnail = oembed_request['thumbnail_url']
            thumbnail_width = oembed_request['thumbnail_width']
            thumbnail_height = oembed_request['thumbnail_height']
            got_image = True
            do_oembed = False
        except KeyError:
            logging.debug("oEmbed response doesn't provide a thumbnail.")
            got_image = False
            do_oembed = True
    
    if got_image == False and do_oembed == True:
        # Then see if they return an image anyway (we can always
        # scale it)
        try:
            thumbnail = oembed_request['url']
            thumbnail_width = oembed_request['width']
            thumbnail_height = oembed_request['height']
            got_image = True
            if thumbnail_width>maxwidth and thumbnail_height>maxheight:
                needs_scale = True
        except KeyError:
            logging.debug("oEmbed response isn't an image.")
            got_image = False
    
    # Now check if we've got an image, and if we do, whether
    # it needs scaling.
    if got_image == False:
        logging.error("We don't have an image. Let's fall back to a page screenshot.")
        thumb_urls = settings.urliser(url=thumbnail, maxwidth=maxwidth, maxheight=maxheight)
        
        # Most free services don't allow custom sizes larger than 200x200
        if maxwidth>200: maxwidth=200
        if maxheight>200: maxheight=200
        
        thumbnail = imgcache.cachetos3(thumb_urls, maxwidth, maxheight)
        memcache.set(key=hashed_url, value=thumbnail, time=604800)
        return generate_response(thumbnail, maxwidth, maxheight, format, callback)
    elif got_image == True:
        if needs_scale == True:
            logging.debug("The image needs scaling to thumbnail size first.")
            thumbnail = imgcache.cachetos3([url,], maxwidth, maxheight)
            memcache.set(key=hashed_url, value=thumbnail, time=604800)
            return generate_response(thumbnail, maxwidth, maxheight, format, callback)
        else:
            logging.debug("We can return an image URL now.")
            memcache.set(key=hashed_url, value=thumbnail, time=604800)
            return generate_response(thumbnail, maxwidth, maxheight, format, callback)

urls = [
    ('/api', API),
]

application = webapp.WSGIApplication(urls, debug=True)

def main(): run_wsgi_app(application)
if __name__ == "__main__": main()
