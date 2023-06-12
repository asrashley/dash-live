Simulated MPEG DASH service
===========================

A Google App Engine project that provides an end point for multiple MPEG DASH
manifests. These manifests are dynamically generated from templates of various
vendor's packaging output.

The principal use for this service is to test live DASH streams using
non-live, rights cleared material. In this case, it uses Big Buck Bunny
as the test file.

**This branch is feature frozen because Python 2 is no longer supported.**

Installation
------------
A settings.py needs to be created that contains

```python
from utils import on_production_server

cookie_secret = 'arandomstring'
csrf_secret = 'arandomstring'
DEBUG = not on_production_server
allowed_domains = "*"
```

The cookie_secret and csrf_secret variables need to contain a randomly
generated block of ascii characters. There is a gen_settings.py script
that can be used to auto-generate settings.py

The `allowed_domains` setting is optional. If it is missing, a default
list of domains that supports common JavaScript DASH libraries will be
used. An `allowed_domains` value of "*" tells the server to allow any
request from any domain.

### Running development server directly on the host machine
Install the Python 2 Google App Engine (GAE)

https://cloud.google.com/appengine/docs/standard/python/download

On Ubuntu, the following should install the Python GAE SDK:

```sh
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
sudo apt-get install apt-transport-https ca-certificates
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
sudo apt-get update && sudo apt-get install google-cloud-sdk
sudo apt-get install google-cloud-sdk-app-engine-python google-cloud-sdk-app-engine-python-extras google-cloud-sdk-datastore-emulator
```

Create a Python virtual environment and install the dependencies:

```sh
sudo python2 -m pip install virtualenv
virtualenv -p python2 virtenv
. ./virtenv/bin/activate
pip install -r requirements.txt
```

The CSS files need to be compiled:

```sh
(cd static/css/ && make)
```

Use runserver.bat or runserver.sh depending upon whether you are developing
on Windows or Linux.

It will start an HTTP server on port 9080

### Running development server using a Docker image
There is a dockerfile to create a Docker image that contains GAE and
all the other required packages to run the development server.

```sh
docker build -t dashlive -f sdk-dockerfile .
mkdir gaedata
```

The docker container can then be used by:

```sh
docker run -i -t -p 9080:80/tcp -p 9081:8080/tcp \
    -v gaedata:/home/dash/.gaedata dashlive
```

Note that this docker container runs the DEVELOPMENT ENVIRONMENT
and is NOT for use in a production environment! The above example
will use port 80 and 8080 on the Docker host to provide access to
the application (on port 80) and the GAE admin server (port 8080).

Media Files
-----------
The application expects there to be at least one video and one audio
MP4 file for each available stream. Each file belonging to a stream
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

These file needs to have been encoded for DASH, with a MOOV and MOOF boxes
and each MOOF of a fixed duration. In the src/media directory there is a
create_media.py Python script which gives an example of how to encode and
package the media files.

```sh
test -e "BigBuckBunny.mp4" || curl -o "BigBuckBunny.mp4" "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
python create_media.py -i "BigBuckBunny.mp4" -p bbb --kid '1ab45440532c439994dc5c5ad9584bac' -o bbb
```

The media files need to be uploaded once the dash server is running. Go to
http://localhost:9080/media to upload the media files, one at a time.
After uploading, each media file needs to be indexed, using the
"index" button beside each media item.

When running in development mode, the populate-db.py script can be used to
automate the installation of streams, files and keys

```sh
python populate-db.py --host http://localhost:9080/ bbb.json
```

Where bbb.json is a JSON file that looks like this:

```json
{
    "keys": [
        {
            "computed": false,
            "key": "533a583a843436a536fbe2a5821c4b6c",
            "kid": "c001de8e567b5fcfbc22c565ed5bda24"
        },
        {
            "computed": true,
            "kid": "1ab45440532c439994dc5c5ad9584bac"
        }
    ],
    "streams": [
        {
            "prefix": "bbb",
            "title": "Big Buck Bunny",
            "marlin_la_url": "ms3://ms3.test.expressplay.com:8443/hms/ms3/rights/?b=...",
            "playready_la_url": "https://test.playready.microsoft.com/service/rightsmanager.asmx?cfg={cfgs}"
        }
    ],
    "files": [
        "bbb_a1.mp4", "bbb_a1_enc.mp4", "bbb_a2.mp4", "bbb_a2_enc.mp4",
        "bbb_v1.mp4", "bbb_v1_enc.mp4", "bbb_v2.mp4", "bbb_v2_enc.mp4",
        "bbb_v3.mp4", "bbb_v3_enc.mp4", "bbb_v4.mp4", "bbb_v4_enc.mp4",
        "bbb_v5.mp4", "bbb_v5_enc.mp4", "bbb_v6.mp4", "bbb_v6_enc.mp4",
        "bbb_v7.mp4", "bbb_v7_enc.mp4"
    ]
}
```

The populate-db.py script will upload all of the keys, streams and
files listed in the JSON file that don't already exist on the
server.

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

Unit Tests
==========
To run all unit tests, which will take quite a long time (e.g. 45
minutes) to complete:

```sh
python ./runtests.py
```

It is also possible to run the set of tests for one area by providing
the name of the Python file containing the tests, without the tests/
prefix:

```sh
python ./runtests.py mp4_test.py
```

... which will run every test in the tests/mp4_test.py file.

To specify one or more tests within that test file, a list of test
functions can also be added to the runtests.py command line:

```sh
python ./runtests.py views_test.py test_inband_ping_pong_dash_events test_all_options_manifest_n
```

To run the unit tests inside a Docker container:

```sh
docker build -t dashlive -f sdk-dockerfile .
docker run --mount type=bind,source=`pwd`/tests,destination=/home/dash/dash-live/tests \
    -it --entrypoint /home/dash/dash-live/runtests.py dashlive
```

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
