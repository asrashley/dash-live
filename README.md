# Simulated MPEG DASH service

A Python application that provides an endpoint for multiple MPEG DASH
manifests. These manifests are dynamically generated from templates of various
vendor's packaging output.

The principal use for this service is to test live DASH streams using
non-live, rights cleared material.

## Installation

Python 3.11 or greater is required by this application.

A `dashlive/server/settings.py` needs to be created that contains

```python3
from os import environ
cookie_secret = 'arandomstring'
csrf_secret = 'arandomstring'
jwt_secret = 'arandomstring'
default_admin_username = 'admin'
default_admin_password = r'a.password'
allowed_domains = "*"
DEBUG = environ.get("LOG_LEVEL", "error").lower() == 'debug'
```

The `cookie_secret`, `csrf_secret` and `jwt_secret` variables need to contain
a randomly generated block of ascii characters. There is a
[gen_settings.py](./gen_settings.py) script that can be used to auto-generate
settings.py

The `allowed_domains` setting is optional. If it is missing, a default
list of domains that supports common JavaScript DASH libraries will be
used. An `allowed_domains` value of "*" tells the server to allow any
request from any domain.

### Running development server directly on the host machine

Create a Python virtual environment and install the dependencies:

```sh
python3 -m venv virtenv
. ./virtenv/bin/activate
pip install -r requirements.txt
```

The CSS files need to be compiled:

```sh
python -m lesscpy static/css -o static/css/
```

Use [runserver.bat](./runserver.bat) or [runserver.sh](./runserver.sh)
depending upon whether you are developing on Windows or Linux.

It will start an HTTP server on port 9080

### Running development server using a Docker image

There is a dockerfile to create a Docker image that contains
all the required packages to run the development server.

```sh
docker build -t dashlive .
mkdir instance
```

The docker container can then be used by:

```sh
docker run -i -t -p 5000:8080/tcp  \
    -v instance:/home/dash/instance dashlive
```

Note that this docker container runs the DEVELOPMENT ENVIRONMENT
and is NOT for use in a production environment! The above example
will use port 8080 on the Docker host to provide access to
the application (on port 5000).

The service should now be available from

[http://localhost:8080/]([http://localhost:8080/])

## Adding User Accounts

By default, the server will create a new admin account using the username
and password values defined in `dashlive/server/settings.py`. You will need
to use that username and password to log into the server and then change the
password. From the [users](http://localhost:8080/users) page can then be
used to add additional users to the system.

## Media Files

The application expects there to be at least one video and one audio
MP4 file for each available stream. Each file belonging to a stream
must be uploaded and associated with that stream. When the
file is parsed by the server it will auto-detect if the file is
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
and each MOOF of a fixed duration. There is a
[create_media.py](./dashlive/media/create_media.py)
Python script which gives an example of how to encode and package the media files.

```sh
test -e "BigBuckBunny.mp4" || curl -o "BigBuckBunny.mp4" "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
python -m dashlive.media.create_media -i "BigBuckBunny.mp4" -p bbb --kid '1ab45440532c439994dc5c5ad9584bac' -o bbb
```

The media files need to be uploaded once the dash server is running. Go to
[streams](http://localhost:8080/streams) to create a stream entry. Once the stream
has been created, click on the title of the stream to view a page that allows
media files to be uploaded.

Upload the media files, one at a time. After uploading, each media file needs
to be indexed, using the "index" button beside each media item. The index process
finds each segment in the file and other information such as codecs, timescale and
duration.

The [populate-db.py](./populate-db.py) script can be used to automate the installation
of streams, files and keys:

```sh
python populate-db.py --host http://localhost:8080/ bbb.json
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
            "directory": "bbb",
            "title": "Big Buck Bunny",
            "marlin_la_url": "ms3://ms3.test.expressplay.com:8443/hms/ms3/rights/?b=...",
            "playready_la_url": "https://test.playready.microsoft.com/service/rightsmanager.asmx?cfg={cfgs}"
			"files": [
				"bbb_a1.mp4", "bbb_a1_enc.mp4", "bbb_a2.mp4", "bbb_a2_enc.mp4",
				"bbb_v1.mp4", "bbb_v1_enc.mp4", "bbb_v2.mp4", "bbb_v2_enc.mp4",
				"bbb_v3.mp4", "bbb_v3_enc.mp4", "bbb_v4.mp4", "bbb_v4_enc.mp4",
				"bbb_v5.mp4", "bbb_v5_enc.mp4", "bbb_v6.mp4", "bbb_v6_enc.mp4",
				"bbb_v7.mp4", "bbb_v7_enc.mp4"
			]
        }
    ],
}
```

The [populate-db.py](./populate-db.py) script will upload all of the keys,
streams and files listed in the JSON file that don't already exist on the
server.

If there are encrypted streams, the key IDs (KID) and encryption key
need to be configured. The media index process will automatically add new
key entries for each KID found in the media file.

It is possible to omit the encryption key and just provide the KID.
In this case, the server will auto-generate the encryption key using
the key generation algorithm provided by MicroSoft PlayReady using
the test key seed. Click on the `Edit` button for the appropriate KID and
then click the "Key is auto-computed?" check box.

Alternatively, the value of the key can be provided manually using the
"Key" input text field.

### Viewing Media Details

Once a media file has been indexed, clicking on the name of one of the
uploaded files will show a page listing the information extracted from
the media file. Clicking on the `Number of Segments` link will show information
about each segment.

Clicking on the link for one of those segments will show every MP4 atom
that has been parsed from the file.

## Unit Tests

To run all unit tests, which will take quite a long time (e.g. 5
minutes) to complete:

```sh
python -m unittest
```

It is also possible to run the set of tests for one area by providing
the name of the Python file containing the tests:

```sh
python -m tests.test_mp4_test
```

... which will run every test in the [tests/test_mp4.py](./tests/test_mp4.py) file.

To specify one or more tests within that test file, a list of test
functions can also be added to the runtests.py command line:

```sh
python -m tests.test_views test_inband_ping_pong_dash_events test_all_options_manifest_n
```

To run the unit tests inside a Docker container:

```sh
docker build -t dashlive  .
docker run --mount type=bind,source=`pwd`/tests,destination=/home/dash/dash-live/tests \
    -it --entrypoint /home/dash/dash-live/runtests.py dashlive
```

## Migrating from Python 2 version

This version is incompatible with the previous Python 2
version. Migrating the Python 2 version requires complete re-creation
of the database and re-uploading media files.

The old version of this application has a `download-db.py` script that
can be used to extract all of the data from the old server. The
[populate-db.py](./populate-db.py) script from this version can be
used to take this extracted data and upload it to the new server. This
process should preserve all of the information between versions.

Using a checkout of the `python-2.7` branch to download the data from
a running Python 2 version of this app into a `tmp` directory:

```sh
python2 download-db.py --host http://localhost:9080/ tmp
```

Using a checkout of the main branch to upload this data to a new
server:

```sh
python3 populate-db.py --username=admin --password=mysecret \
    --host http://localhost:5000/ tmp/downloaded.json
```

## License
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
