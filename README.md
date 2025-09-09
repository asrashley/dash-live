# Simulated MPEG DASH service

A Python application that provides an endpoint for multiple MPEG DASH
manifests. These manifests are dynamically generated from templates of various
vendor's packaging output.

The principal use for this service is to test live DASH streams using
non-live, rights cleared material. There are a large number of configuration
options that can be applied to these streams and manifests, giving millions
of different combinations.

## Installation

Python v3.11 or greater and Node.js v20 or greater is required by this
application. It has been tested on both Linux and Windows operating systems.

A `.env` needs to be created that contains

```bash
FLASK_SECRET_KEY='arandomstring'
FLASK_DASH__CSRF_SECRET='arandomstring'
FLASK_DASH__DEFAULT_ADMIN_USERNAME='admin'
FLASK_DASH__DEFAULT_ADMIN_PASSWORD='secret'
FLASK_DASH__ALLOWED_DOMAINS='*'
```

The name of the `.env` file can be changed by setting the environment
variable `DASHLIVE_SETTINGS` to the filename to use to load the above
settings.

The `FLASK_SECRET_KEY`, `FLASK_DASH__CSRF_SECRET` variables need to contain
a randomly generated block of ascii characters. There is a
[gen_settings.py](./gen_settings.py) script that can be used to auto-generate
the `.env` file.

The `FLASK_DASH__ALLOWED_DOMAINS` setting is optional. It controls the HTTP
response header `Access-Control-Allow-Origin` that is used to control which
origins are allowed to make HTTP requests from JavaScript to this server.

If the `FLASK_DASH__ALLOWED_DOMAINS` is missing, a default list of domains
that supports common JavaScript DASH libraries will be used. An `allowed_domains`
value of "*" tells the server to allow any JavaScript request from any domain.

The `FLASK_DASH__DEFAULT_ADMIN_PASSWORD` setting controls the default password
to use for the admin user account when creating a new blank database.

## Running the development server directly on the host machine

Install the [uv package manager](https://docs.astral.sh/uv/getting-started/installation/)

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

or

```sh
sudo apt install pipx
pipx install uv
```

or Windows:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Create a Python virtual environment and install the dependencies.

If using Linux:

```sh
uv sync
. ./.venv/bin/activate
```

or Windows:

```powershell
uv sync
```

NOTE: If `uv sync` fails, you might need to install the Python virtual
environment tools:

```sh
sudo apt install python3.11 python3.11-venv python3.11-distutils
```

Install JavaScript libraries:

```sh
npm i
```

The CSS files need to be compiled:

```sh
npm run all-css
```

The front-end Typescript code needs to be compiled:

```sh
npm run build
```

To start the server:

```sh
./runserver.sh
```

or if using Windows:

```powershell
.\runserver.ps1
```

It will start an HTTP server on port 5000

See [docs/deploy.md](./docs/deploy.md) for more information on the various
options for deploying this service.

## Adding User Accounts

By default, the server will create a new admin account using the username
and password values defined in `.env`. You will need to use that username
and password to log into the server and then change the password. From the
[users](http://localhost:5000/users) page can then be used to add additional
users to the system.

See [docs/users.md](./docs/users.md) for more information about the user
authentication system.

## Streams

Each stream entry represents a playable audio/video stream. Each stream
must have at least one video and one audio MP4 file. Typically each
stream will have multiple video files associated with it, one for
each available bitrate.

See [docs/streams](./docs/streams.md) for more information about DASH
streams.

See [docs/media](./docs/media.md) for more information about media
file requirements and how to upload and download files from the server.

### Viewing Media Details

Once a media file has been indexed, clicking on the name of one of the
uploaded files will show a page listing the information extracted from
the media file. Clicking on the `Number of Segments` link will show information
about each segment.

Clicking on the link for one of those segments will show every MP4 atom
that has been parsed from the file.

## DASH Stream Validation

The [/validate](http://localhost:5000/validate/) page allows the checking
the validity of a DASH stream. It will inspect the contents of the DASH
manifest and all the requested segments in the stream. If it finds
any values that don't adhere to the DASH specification, they will be
logged in the output summary.

See [docs/validate](./docs/validate.md) for more information about the
DASH validator.

## Migrating from Python 2 version

This version is incompatible with the previous Python 2 version.
Migrating the Python 2 version requires complete re-creation of the
database and re-uploading media files.

The old [python-2.7](https://github.com/asrashley/dash-live/tree/python-2.7)
branch of this application has a
[download-db.py](https://github.com/asrashley/dash-live/blob/python-2.7/download-db.py)
script that can be used to extract all of the data from the old server.

Using a checkout of the `python-2.7` branch to download the data from
a running Python 2 version of this app into a `tmp` directory:

```sh
python2 download-db.py --host http://localhost:9080/ tmp
```

The [dashlive.upload](./dashlive/upload.py) script from this version can
be used to take this extracted data and upload it to the new server. This
process should preserve all of the information between versions.

Using a checkout of the main branch to upload this data to a new
server:

```sh
python3 -m dashlive.upload --username=admin --password=mysecret \
    --host http://localhost:5000/ tmp/downloaded.json
```

**The `Timing reference` property of each uploaded stream needs to be set before
the streams are playable**. After the media has been installed onto the server,
each stream needs to be modified to set the stream's timing reference.

From the streams list page (e.g. http://localhost:5000/streams) click on each
stream in turn and select one media file in the "stream timing reference" drop-down
selection. A live stream is synthesized by using static files and looping their
playback, starting from availabilityStartTime. The stream timing reference selects
the media file that is used when calculating when a live stream loops. This is
required as there might be a small difference in duration between video and audio
files within a stream. Those small differences can add up to significant audio/video
synchronization errors after the stream has looped many times. The stream timing
reference file is used to calculate the timing of the live stream, for all
adaptation sets within the stream.

## Testing

See [docs/testing](./docs/testing.md) for information about running the
unit tests and coverage reports. At the time of writing, there is almost 80%
test coverage of the Python code.

| statements | missing | excluded | branches | partial | coverage |
| --- | --- | --- | --- | --- | --- |
| 12484 | 2342 | 94 | 5216 | 741 | 79% |

The TypeScript front-end code has over 90% test coverage:

|           | % Stmts | % Branch | % Funcs | % Lines |
| --------- | ------- | -------- | ------- | ------- |
| All files |   96.56 |    93.94 |   99.58 |   96.56 |

## License

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

<http://www.apache.org/licenses/LICENSE-2.0>

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
