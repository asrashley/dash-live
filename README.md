Fake MPEG DASH Live profile end point
=====================================

A Google App Engine project that provides an end point for multiple MPEG DASH
manifests. These manifests are dynamically generated from templates of various
vendor's packaging output.

The principal use for this service is to test live DASH streams using
non-live, rights cleared material. In this case, it uses Big Buck Bunny
as the test file.

Installation
------------
Install the Python 2 Google App Engine (GAE)
 
https://cloud.google.com/appengine/docs/standard/python/download

Media Files
-----------
The application expects there to be 4 video MP4 files:

* V1.mp4
* V2.mp4
* V3.mp4
* V3enc.mp4

and two audio MP4 files:

* A1.mp4
* A2.mp4

These files need to have been encoded for DASH, with a MOOV and MOOF boxes
and each MOOF of a fixed duration.

The application needs an index for each media file, which it stores as a
Python file.

    cd media
    python gen_index.py -i V1.mp4
    python gen_index.py -i V2.mp4
    python gen_index.py -i V3.mp4
    python gen_index.py -i V3enc.mp4
    python gen_index.py -i A1.mp4
    python gen_index.py -i A2.mp4
    cd ..

The media files need to be uploaded once the dash server is running. Go to
http://localhost:9080/upload to upload the media files, one at a time.

Local development
-----------------
A settings.py needs to be created that contains 

    from utils import on_production_server

    cookie_secret='arandomstring'
    csrf_secret = 'arandomstring'
    DEBUG=not on_production_server
    sas_url=''
 
The cookie_secret and csrf_secret variables need to contain a randomly
generated block of ascii characters.

The CSS used by the application is compiled using lessc.

    cd static
    cd css
    compile
    cd ..
    cd ..

Use runserver.bat or runserver.sh depending upon whether you are developing
on Windows or Linux.

It will start an HTTP server on port 9080