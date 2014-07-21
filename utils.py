import math, os

from google.appengine.api import apiproxy_stub_map


def toIsoDateTime(value):
    #TODO: check if value has a time zone
    return value.isoformat()+'Z'

def toIsoDuration(secs):
    """ Convert a time (in seconds) to an ISO8601 duration.
     @param {number} secs the duration to convert, in seconds 
     @returns {string} an ISO8601 formatted version of the duration
     """
    if isinstance(secs,str):
        secs = float(secs)
    hrs = math.floor(secs/3600)
    rv=['PT']
    secs %= 3600
    mins = math.floor(secs/60)
    secs %= 60
    if hrs:
        rv.append('%dH'%hrs)
    if hrs or mins:
        rv.append('%dM'%mins)        
    if secs:
        rv.append('%fS'%secs)
    return ''.join(rv)


#
# The following code is from djangoappengine/utils.py
#
have_appserver = bool(apiproxy_stub_map.apiproxy.GetStub('datastore_v3'))

on_production_server = have_appserver and \
    not os.environ.get('SERVER_SOFTWARE', '').lower().startswith('devel')
    
