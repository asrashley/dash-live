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

There is a dockerfile to create a Docker image that contains GAE and
all the other required packages.

	sudo apt install node-less
    (cd static/css/ && make)
    docker build -t dashlive -f sdk-dockerfile .
    mkdir gaedata

The docker container can then be used by:

    docker run -i -t -p 9080:80/tcp -p 9081:8080/tcp \
    -v gaedata:/home/dash/.gaedata dashlive

Note that this docker container runs the DEVELOPMENT ENVIRONMENT
and is NOT for use in a production environment! The above example
will use port 80 and 8080 on the Docker host to provide access to
the application (port 80) and the GAE admin server (port 8080).

Media Files
-----------
The application expects there to be at least one video and one audio
MP4 files for each available stream. Each file belonging to a stream
must have the same filename prefix followed by an underscore. When the
stream is parsed by the server it will auto-detect if the stream is
encrypted. It is recommended however to choose a naming convention
that makes it easier to tell which streams are encrypted and which
ones are in the clear. For example:

* bbb_a1.mp4
* bbb_a1_enc.mp4
* bbb_a2.mp4
* bbb_a2_enc.mp4
* bbb_v1.mp4
* bbb_v1_enc.mp4 
* bbb_v2.mp4
* bbb_v2_enc.mp4
* bbb_v3.mp4
* bbb_v3_enc.mp4
* bbb_v4.mp4
* bbb_v4_enc.mp4
* bbb_v5.mp4
* bbb_v5_enc.mp4
* bbb_v6.mp4
* bbb_v6_enc.mp4
* bbb_v7.mp4
* bbb_v7_enc.mp4

These files need to have been encoded for DASH, with a MOOV and MOOF boxes
and each MOOF of a fixed duration. In the media directory there is an
encode.sh shell script which gives an example of how to encode and
package the media files.

The media files need to be uploaded once the dash server is running. Go to
http://localhost:9080/media to upload the media files, one at a time.
After uploading, each media file needs to be indexed, using the
"index" button beside each media item.

Once this has been done, you can add the stream to the list of
available streams http://localhost:9080/media using the "add" button
in the "Streams" table. The prefix must be the filename prefix used 
when creating the media. In the above example, the prefix would be
"bbb".

If there are encrypted streams, the key IDs (KID) and encryption key
need to be added. It is possible to omit the encryption key and just
provide the KID. In this case, the server will auto-generate the
encryption key using the key generation algorithm provided by
MicroSoft PlayReady using the test key seed.

Local development
-----------------
A settings.py needs to be created that contains 

    from utils import on_production_server

    cookie_secret='arandomstring'
    csrf_secret = 'arandomstring'
    DEBUG=not on_production_server
    sas_url=''
 
The cookie_secret and csrf_secret variables need to contain a randomly
generated block of ascii characters. There is a gen_settings.py script
that can be used to auto-generate settings.py

The CSS used by the application is compiled using lessc.

    (cd static/css && make)

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
