Simulated MPEG DASH service
===========================

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

On Ubuntu, the following should install the Python GAE SDK:

    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
	sudo apt-get install apt-transport-https ca-certificates
	curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
	sudo apt-get update && sudo apt-get install google-cloud-sdk
    sudo apt-get install google-cloud-sdk-app-engine-python google-cloud-sdk-app-engine-python-extras google-cloud-sdk-datastore-emulator

The CSS files need to be compiled:

	sudo apt install node-less
    (cd static/css/ && make)

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

License
=======
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
