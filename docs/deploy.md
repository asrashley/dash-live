# Deployment options

## Running server using a Docker image

The [Dockerfile](./Dockerfile) can be used to create a Docker image
that contains all the required packages to run the server. It uses
nginx to serve static files and the Python Flask app to serve all other
HTTP requests.

```sh
docker build -t dashlive .
mkdir instance
```

The docker container can then be used by:

```sh
docker run -i -t \
    -v ${PWD}/instance:/home/dash/instance \
    -p 5000:80/tcp -e SERVER_NAME=`hostname -f` \
    -e USER_GID=`id -g` -e USER_UID=`id -u` \
    dashlive
```

The above example will use port 5000 on the Docker host to provide
access to the application (which uses port 80 inside the Docker
container). The environment variable `USER_UID` controls the user
ID to use inside the Docker container. `USER_GID` controls the group
ID to use inside the Docker container.

The service should now be available from:

[http://localhost:5000/]([http://localhost:5000/])

## Running development server using a Docker image

To run the development server, so that changes in the source code are
automatically re-loaded into the server, you can tell docker to use
the [runserver.sh](./runserver.sh) script as its entry point:

```sh
docker run -i -t  \
  -v instance:/home/dash/instance \
  --mount \
    type=bind,source=`pwd`/dashlive,destination=/home/dash/dash-live/dashlive \
  -p 9090:5000/tcp -e SERVER_NAME=`hostname -f` \
  -e USER_GID=`id -g` -e USER_UID=`id -u` \
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
docker build --tag=dashlive --target=base .
```
