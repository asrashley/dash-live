#
# Build client app
#
FROM node:22 AS clientbuild
ENV HOME=/home/dash
ENV CI=1
ARG GIT_SHA="-----"
RUN mkdir -p ${HOME}/static/html
WORKDIR ${HOME}
COPY *.js ${HOME}/
COPY *.json ${HOME}/
COPY frontend ${HOME}/frontend
COPY static/css ${HOME}/static/css
COPY patches ${HOME}/patches
RUN npm ci
RUN GIT_SHA=${GIT_SHA} npm run build
RUN npm run all-css
RUN tar czf ${HOME}/front-end.tar.gz static/html static/css
#
# Build Python server container
#
FROM python:3.11 as dashlive
EXPOSE 5000
ARG DEFAULT_PASSWORD=""
ARG PROXY_DEPTH="1"
ENV HOME=/home/dash
ENV FLASK_INSTANCE_PATH=/home/dash/instance
ENV LOG_LEVEL="info"
ENV VIRTUAL_ENV="/home/dash/.venv"
RUN apt-get update && \
    apt-get -y -q --force-yes install \
    less \
    vim \
    curl \
    python3-pip \
    python3-venv
COPY requirements.txt $HOME/dash-live/
COPY dev-requirements.txt $HOME/dash-live/
COPY deploy/create_virtenv.sh $HOME/dash-live/
RUN chmod +x $HOME/dash-live/create_virtenv.sh \
    && $HOME/dash-live/create_virtenv.sh
COPY static $HOME/dash-live/static
RUN rm -rf $HOME/dash-live/static/html $HOME/dash-live/static/css
COPY templates $HOME/dash-live/templates
COPY runserver.sh $HOME/dash-live/
COPY alembic.ini $HOME/dash-live/
COPY alembic $HOME/dash-live/alembic
COPY dashlive $HOME/dash-live/dashlive
COPY *.py $HOME/dash-live/
RUN mkdir $HOME/instance
RUN ln -s /usr/bin/python3 /usr/bin/python
WORKDIR /home/dash/dash-live
RUN python ./gen-settings.py --password=${DEFAULT_PASSWORD} --proxy-depth=${PROXY_DEPTH}
COPY deploy/runtests.sh $HOME/dash-live/
RUN chmod +x $HOME/dash-live/*.sh
COPY --from=clientbuild ${HOME}/front-end.tar.gz ${HOME}
RUN cd ${HOME}/dash-live \
    && tar -xzf ${HOME}/front-end.tar.gz \
    && rm ${HOME}/front-end.tar.gz
RUN python -m compileall -f -j 0 /home/dash/dash-live/dashlive
ENTRYPOINT ["/home/dash/dash-live/runserver.sh"]
#
# build container to serve HTTP requests
#
FROM dashlive AS dashlive-nginx
EXPOSE 80
ENV SERVER_NAME="_"
ENV SERVER_PORT="80"
ENV USER_GID=""
RUN apt-get -y -q --force-yes install nginx
RUN rm /etc/nginx/sites-enabled/default
COPY deploy/*.py $HOME/dash-live/
COPY deploy/start-server.sh $HOME/dash-live/
COPY deploy/dashlive.conf /etc/nginx/sites-available/
COPY deploy/x_forwarded_proto.conf /etc/nginx/conf.d/
COPY deploy/proxy_params /etc/nginx/
COPY deploy/mime.types /etc/nginx/
RUN echo "client_max_body_size 1024M;" > /etc/nginx/conf.d/maxsize.conf
RUN ln -s /etc/nginx/sites-available/dashlive.conf /etc/nginx/sites-enabled/dashlive.conf
RUN chmod +x $HOME/dash-live/*.sh
RUN chown www-data:www-data $HOME/instance
RUN echo "server_name _;" > /etc/nginx/snippets/server_name.conf
VOLUME [ "/home/dash/instance" ]
STOPSIGNAL SIGQUIT
ENTRYPOINT ["/home/dash/dash-live/start-server.sh"]

