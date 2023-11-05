FROM python:3.11 as base
EXPOSE 5000
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
COPY deploy/create_virtenv.sh $HOME/dash-live/
RUN chmod +x $HOME/dash-live/create_virtenv.sh
RUN $HOME/dash-live/create_virtenv.sh
COPY static/favicon.ico $HOME/dash-live/static/
COPY static/fonts/* $HOME/dash-live/static/fonts/
COPY static/img/* $HOME/dash-live/static/img/
COPY static/js/*.js $HOME/dash-live/static/js/
COPY static/js/dev/* $HOME/dash-live/static/js/dev/
COPY static/js/legacy/* $HOME/dash-live/static/js/legacy/
COPY static/js/prod/* $HOME/dash-live/static/js/prod/
COPY templates/manifests/*.mpd $HOME/dash-live/templates/manifests/
COPY templates/*.html $HOME/dash-live/templates/
COPY templates/drm/*.xml $HOME/dash-live/templates/drm/
COPY templates/events/*.xml $HOME/dash-live/templates/events/
COPY templates/media/*.html $HOME/dash-live/templates/media/
COPY templates/segment/*.xml $HOME/dash-live/templates/segment/
COPY templates/users/*.html $HOME/dash-live/templates/users/
COPY static/css/* $HOME/dash-live/static/css/
COPY runserver.sh $HOME/dash-live/
COPY alembic.ini $HOME/dash-live/
COPY alembic/*.py $HOME/dash-live/alembic/
COPY alembic/versions/*.py $HOME/dash-live/alembic/versions/
COPY dashlive/*.py $HOME/dash-live/dashlive/
COPY dashlive/components/*.py $HOME/dash-live/dashlive/components/
COPY dashlive/drm/*.py $HOME/dash-live/dashlive/drm/
COPY dashlive/management/*.py $HOME/dash-live/dashlive/management/
COPY dashlive/media/*.py $HOME/dash-live/dashlive/media/
COPY dashlive/mpeg/*.py $HOME/dash-live/dashlive/mpeg/
COPY dashlive/mpeg/dash/*.py $HOME/dash-live/dashlive/mpeg/dash/
COPY dashlive/mpeg/dash/validator/*.py $HOME/dash-live/dashlive/mpeg/dash/validator/
COPY dashlive/scte35/*.py $HOME/dash-live/dashlive/scte35/
COPY dashlive/server/*.py $HOME/dash-live/dashlive/server/
COPY dashlive/server/events/*.py $HOME/dash-live/dashlive/server/events/
COPY dashlive/server/models/*.py $HOME/dash-live/dashlive/server/models/
COPY dashlive/server/options/*.py $HOME/dash-live/dashlive/server/options/
COPY dashlive/server/requesthandler/*.py $HOME/dash-live/dashlive/server/requesthandler/
COPY dashlive/utils/*.py $HOME/dash-live/dashlive/utils/
COPY dashlive/utils/fio/*.py $HOME/dash-live/dashlive/utils/fio/
COPY *.py $HOME/dash-live/
RUN mkdir $HOME/instance
RUN ln -s /usr/bin/python3 /usr/bin/python
WORKDIR /home/dash/dash-live
RUN python ./gen-settings.py
RUN echo "#!/bin/bash" > $HOME/dash-live/lesscpy.sh
RUN echo "source $HOME/.venv/bin/activate && python -m lesscpy static/css -o static/css/" >> $HOME/dash-live/lesscpy.sh
RUN chmod +x $HOME/dash-live/lesscpy.sh
RUN $HOME/dash-live/lesscpy.sh
ENTRYPOINT ["/home/dash/dash-live/runserver.sh"]

FROM base as dashlive-nginx
EXPOSE 80
ENV SERVER_NAME="_"
ENV USER_GID=""
RUN apt-get -y -q --force-yes install nginx
RUN rm /etc/nginx/sites-enabled/default
COPY deploy/application.py $HOME/dash-live/
COPY deploy/start-uwsgi.sh $HOME/dash-live/
COPY deploy/dashlive.conf /etc/nginx/sites-available/
COPY deploy/dash.ini /etc/uwsgi/sites/
RUN echo "client_max_body_size 1024M;" > /etc/nginx/conf.d/maxsize.conf
RUN ln -s /etc/nginx/sites-available/dashlive.conf /etc/nginx/sites-enabled/dashlive.conf
RUN chmod +x $HOME/dash-live/*.sh
RUN chown www-data:www-data $HOME/instance
RUN echo "server_name _;" > /etc/nginx/snippets/server_name.conf
STOPSIGNAL SIGQUIT
ENTRYPOINT ["/home/dash/dash-live/start-uwsgi.sh"]

