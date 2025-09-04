FROM debian:bookworm-slim
ENV HOME=/home/dash
ENV CI=1

RUN apt update \
    && apt -y -q --force-yes install \
    automake \
    build-essential \
    curl \
    git \
    nasm \
    pkg-config \
    libtool-bin \
    libfreetype-dev \
    libmp3lame-dev \
    libvorbis-dev \
    libvpx-dev \
    libx264-dev \
    libx265-dev

RUN mkdir -p ${HOME}/src
WORKDIR ${HOME}

RUN mkdir ${HOME}/bin
ENV PATH=${PATH}:${HOME}/bin
COPY encoder/git-checkout.sh ${HOME}/bin
RUN git-checkout.sh https://github.com/mstorsjo/fdk-aac.git d8e6b1a3aa606c450241632b64b703f21ea31ce3
RUN cd ${HOME}/fdk-aac \
    && ./autogen.sh \
    && ./configure --prefix=/usr \
    && make -j4 \
    && make install
# 08a81b090b2b8f8f7ec8847d1569eb2042ff1875 = release-8.0
RUN git-checkout.sh https://source.ffmpeg.org/ffmpeg.git 08a81b090b2b8f8f7ec8847d1569eb2042ff1875
RUN cd ${HOME}/ffmpeg \
    && ./configure --enable-gpl --enable-version3 --enable-nonfree \
    --enable-libx264 --enable-libx265 --enable-libvpx --enable-libfdk-aac \
    --enable-libmp3lame --enable-libvorbis --enable-shared --enable-libfreetype --prefix=/usr \
    && make -j4 \
    && make install
RUN git-checkout.sh https://github.com/gpac/gpac.git 1c4cf6e6376b8917215f6da8c90744497e5ee6b9
RUN cd ${HOME}/gpac \
    ./configure --prefix=/usr --strip --isomedia-only --enable-cecrypt \
    && make -j4 \
    && make install
COPY .python-version ${HOME}
ADD https://astral.sh/uv/0.8.13/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="${HOME}/.local/bin/:$PATH"
RUN uv python install
COPY pyproject.toml ${HOME}
COPY uv.lock ${HOME}
RUN cd ${HOME} && uv sync --locked
COPY dashlive $HOME/dash-live/dashlive
RUN uv run -m compileall -f -j 0 ${HOME}/dash-live/dashlive
COPY encoder/encoder.sh ${HOME}
RUN chmod a+rx ${HOME}/encoder.sh \
    && chmod -R a+rX-w ${HOME}/dash-live/dashlive \
    && chmod -R a+rwX ${HOME}/.cache/uv \
    && mkdir -p ${HOME}/.gpac
ENTRYPOINT ["/home/dash/encoder.sh"]
