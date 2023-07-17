FROM ubuntu:22.10
EXPOSE 5000
ENV HOME=/home/dash
ENV LOG_LEVEL="info"
RUN apt-get update && \
    apt-get -y -q --force-yes install \
    python3.11 \
    less \
    vim \
    curl \
    python3-pip
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY static/favicon.ico $HOME/dash-live/static/
COPY static/fonts/* $HOME/dash-live/static/fonts/
COPY static/img/* $HOME/dash-live/static/img/
COPY static/js/prod/* $HOME/dash-live/static/js/prod/
COPY static/js/dev/* $HOME/dash-live/static/js/dev/
COPY static/js/*.js $HOME/dash-live/static/js/
COPY lib/*.py $HOME/dash-live/lib/
COPY templates/*.mpd $HOME/dash-live/templates/
COPY templates/*.html $HOME/dash-live/templates/
COPY templates/drm/*.xml $HOME/dash-live/templates/drm/
COPY templates/events/*.xml $HOME/dash-live/templates/events/
COPY templates/media/*.html $HOME/dash-live/templates/media/
COPY templates/segment/*.xml $HOME/dash-live/templates/segment/
COPY templates/users/*.html $HOME/dash-live/templates/users/
COPY static/css/* $HOME/dash-live/static/css/
COPY runserver.sh $HOME/dash-live/
COPY dashlive/drm/*.py $HOME/dash-live/dashlive/drm/
COPY dashlive/mpeg/*.py $HOME/dash-live/dashlive/mpeg/
COPY dashlive/mpeg/dash/*.py $HOME/dash-live/dashlive/mpeg/dash/
COPY dashlive/scte35/*.py $HOME/dash-live/dashlive/scte35/
COPY dashlive/server/*.py $HOME/dash-live/dashlive/server/
COPY dashlive/server/events/*.py $HOME/dash-live/dashlive/server/events/
COPY dashlive/server/models/*.py $HOME/dash-live/dashlive/server/models/
COPY dashlive/server/requesthandler/*.py $HOME/dash-live/dashlive/server/requesthandler/
COPY dashlive/templates/*.py $HOME/dash-live/dashlive/templates/
COPY dashlive/testcase/*.py $HOME/dash-live/dashlive/testcase/
COPY dashlive/utils/*.py $HOME/dash-live/dashlive/utils/
COPY dashlive/utils/fio/*.py $HOME/dash-live/dashlive/utils/fio/
COPY *.py $HOME/dash-live/
RUN ln -s /usr/bin/python3 /usr/bin/python
WORKDIR /home/dash/dash-live
RUN ls dashlive
RUN python ./gen-settings.py
RUN python -m lesscpy static/css -o static/css/
ENTRYPOINT ["/home/dash/dash-live/runserver.sh"]
