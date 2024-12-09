FROM python:3.11 as base
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
RUN chmod +x $HOME/dash-live/create_virtenv.sh
RUN $HOME/dash-live/create_virtenv.sh
COPY static $HOME/dash-live/static
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
RUN echo "#!/bin/bash" > $HOME/dash-live/lesscpy.sh
RUN echo "source $HOME/.venv/bin/activate && python -m lesscpy static/css -o static/css/" >> $HOME/dash-live/lesscpy.sh
COPY deploy/runtests.sh $HOME/dash-live/
RUN chmod +x $HOME/dash-live/*.sh
RUN $HOME/dash-live/lesscpy.sh
RUN python -m compileall -f -j 0 /home/dash/dash-live/dashlive
ENTRYPOINT ["/home/dash/dash-live/runserver.sh"]

FROM base as dashlive-nginx
EXPOSE 80
ENV SERVER_NAME="_"
ENV USER_GID=""
RUN apt-get -y -q --force-yes install nginx
RUN rm /etc/nginx/sites-enabled/default
COPY deploy/application.py $HOME/dash-live/
COPY deploy/start-server.sh $HOME/dash-live/
COPY deploy/dashlive.conf /etc/nginx/sites-available/
COPY deploy/x_forwarded_proto.conf /etc/nginx/conf.d/
COPY deploy/proxy_params /etc/nginx/
RUN echo "client_max_body_size 1024M;" > /etc/nginx/conf.d/maxsize.conf
RUN ln -s /etc/nginx/sites-available/dashlive.conf /etc/nginx/sites-enabled/dashlive.conf
RUN chmod +x $HOME/dash-live/*.sh
RUN chown www-data:www-data $HOME/instance
RUN echo "server_name _;" > /etc/nginx/snippets/server_name.conf
STOPSIGNAL SIGQUIT
ENTRYPOINT ["/home/dash/dash-live/start-server.sh"]

