# Deployment options

## Running server using a Docker image

The [Dockerfile](../Dockerfile) can be used to create a Docker image
that contains all the required packages to run the server. It uses
nginx to serve static files and the Python Flask app to serve all other
HTTP requests.

To build using Docker's buildx tool:

```sh
docker buildx build --platform linux/amd64 -t dashlive:latest \
  --build-arg "GIT_SHA=$(git rev-list --abbrev-commit -1 HEAD)" --load .
```

or to use the older Docker build tool:

```sh
docker build -t dashlive:latest --build-arg "GIT_SHA=$(git rev-list --abbrev-commit -1 HEAD)" .
```

A directory is needed to contain the media and database files:

```sh
mkdir instance
```

The docker container can then be used by:

```sh
docker run -i -t \
    -v ${PWD}/instance:/home/dash/instance \
    -p 5000:80/tcp -e SERVER_NAME=`hostname -f` -e SERVER_PORT="5000" \
    -e USER_GID=`id -g` -e USER_UID=`id -u` \
    dashlive
```

The above example will use port 5000 on the Docker host to provide
access to the application (which uses port 80 inside the Docker
container). The are several environment variables that control the Docker
container at runtime:

|   Variable    | Description                                               |
| ------------- | --------------------------------------------------------- |
| `USER_UID`    | controls the user ID to use inside the Docker container   |
| `USER_GID`    | controls the group ID to use inside the Docker container  |
| `SERVER_NAME` | fully qualified hostname used to connect to the container |
| `SERVER_PORT` | the TCP port used to connect to the container             |


The service should now be available from:

[http://localhost:5000/]([http://localhost:5000/])

## Running the development server on host machine

Create a Python virtual environment and install the dependencies:

```sh
python3 -m venv virtenv
. ./virtenv/bin/activate
pip install -r requirements.txt
pip install -r dev-requirements.txt
```

It is recommended to use [nvm](https://github.com/nvm-sh/nvm) to make sure that
a compatible version of [Node.js](https://nodejs.org/en) is selected.

Select the version of Node specified by [.nvmrc](../.nvmrc):

```sh
nvm use
```

Install the required JavaScript libraries:

```sh
npm i
```

The CSS files need to be compiled:

```sh
npm run legacy-css
npm run main-css
```

To start the Python server:

```sh
python -m flask --app dashlive.server.app run --host=0.0.0.0 --debug
```

It will start an HTTP server on port 5000. There is no need to connect to
this server, but it will be used by the front-end server. Now that the Python
server has been started, the front-end can be started:

```sh
npm run start
```

You can now connect to the webpack development server:

[http://localhost:8765/]([http://localhost:8765/])

Changes to either the TypeScript code or the Python code will automatically
reload either the front-end or back-end.

## Running the development server using a Docker image

To run the development server, so that changes in the source code are
automatically re-loaded into the server, you can tell docker to use
the [runserver.sh](../runserver.sh) script as its entry point:

```sh
docker run -i -t  \
  -v instance:/home/dash/instance \
  --mount \
    type=bind,source=`pwd`/dashlive,destination=/home/dash/dash-live/dashlive \
  -p 9090:5000/tcp -e SERVER_NAME=`hostname -f` \
  -e USER_GID=`id -g` -e USER_UID=`id -u` \
  -e SERVER_NAME=`hostname -f` -e SERVER_PORT="9090" \
  --entrypoint=/home/dash/dash-live/runserver.sh \
  dashlive
```

Note that this causes the docker container to run the DEVELOPMENT
ENVIRONMENT and is NOT for use in a production environment! The
above example will use port 9090 on the Docker host to provide
access to the application (port 5000 inside the container).

The service should now be available at:

[http://localhost:9090/]([http://localhost:9090/])

If you only need to run the development version in a Docker container,
you can speed up the build process by telling docker to stop after
installing the app, before it installs the files used for normal usage.

```sh
docker build --tag=dashlive --target=dashlive .
```
