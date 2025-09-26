# Media Files

## Media File Format

Each media file must contain one media track of type:

* audio,
* video, or
* text

Each media file must have been encoded as a fragmented MP4 file,
containing an initialization segment (that contains a `moov` box)
and one or more media segments (`moof` boxes).

Each media file can be encrypted using the DASH CENC `cenc` encryption
scheme. When the file is parsed by the server it will auto-detect if
the file is encrypted. It is recommended however to choose a naming
convention that makes it easier to tell which streams are encrypted
and which ones are in the clear. For example:

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

There is a [dashlive.media.create](../dashlive/media/create/__main__.py)
Python script which can be used to encode and package the media files. It needs at least
one file that is used as the source of audio and video. It should have a video resolution
that is at least as high as the highest quality video Representation you want in the DASH
stream. For example, if you use the HD profile setting, the source material should have a
video resoltion of 1280x720 or higher (e.g. 1920x1080).

Probably the easiest way to use `dashlive.media.create` is to create a Docker container that
can be built using this [Dockerfile](../encoder/Dockerfile). This container has all the required
libraries and applications for media encoding, encryption and DASH packaging.

```sh
docker buildx build -t dashlive/encoder:latest -f encoder/Dockerfile .
```

Once the `dashlive/encoder` container has been build, the [create-media.sh](../create-media.sh)
script can be used to start an encoding job within this container.

```sh
./create-media.sh --profile uhd --duration 30 --acodec eac3 -i ToS-4k-1920-Dolby.5.1.mp4 --subtitles Tears_Of_Steel_1080p.eng.srt --output ToS --prefix tears
```

If you would prefer to run the media creation script without using a Docker container,
`dashlive.media.create` can be used directly:

For example:

```sh
test -e "BigBuckBunny.mp4" || curl -o "BigBuckBunny.mp4" "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

python -m dashlive.media.create -i "BigBuckBunny.mp4" -p bbb --kid '1ab45440532c439994dc5c5ad9584bac' -o bbb
```

It will require that [ffmpeg](https://source.ffmpeg.org/ffmpeg), `ffprobe` and
[MP4Box](https://github.com/gpac/gpac/) have been compiled and are in your shell's `PATH`.

## Encoding Examples

### Single key for both audio and video adaptation sets

Example of creating a clear and encrypted version of Big Buck Bunny:

```sh
test -e "BigBuckBunny.mp4" || curl -o "BigBuckBunny.mp4" \
    "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

python -m dashlive.media.create -i "BigBuckBunny.mp4" -p bbb \
    --font /usr/share/fonts/truetype/freefont/FreeSansBold.ttf \
    --kid '1ab45440532c439994dc5c5ad9584bac' -o output
```

In the above example, only the Key ID (kid) is supplied but no key. When no key is supplied
this script will use the PlayReady key generation algorithm with the test key seed.

### Different keys for the audio and video adaptation sets

To use different keys for the audio and video adaptation sets, provide two KIDs (and keys)
on the command line.

```sh
test -e tearsofsteel.mp4 || curl -o tearsofsteel.mp4 \
    'http://profficialsite.origin.mediaservices.windows.net/aac2a25c-0dbc-46bd-be5f-68f3df1fc1f6/tearsofsteel_1080p_60s_24fps.6000kbps.1920x1080.h264-8b.2ch.128kbps.aac.mp4'

python -m dashlive.media.create -i "tearsofsteel.mp4" -p tears \
   --kid a2c786d0-f9ef-4cb3-b333-cd323a4284a5 \
   --kid db06a8fe-ec16-4de2-9228-2c71e9b856ab \
   -o tears
```

### Single audio adaptation set that contains 5.1 surround sound

In this example, the audio track is replaced with a 5.1 version before encoding:

```sh
test -e ToS-4k-1920.mov || curl -o ToS-4k-1920.mov http://ftp.nluug.nl/pub/graphics/blender/demo/movies/ToS/ToS-4k-1920.mov
test -e ToS-Dolby-5.1.ac3 || curl -o ToS-Dolby-5.1.ac3 'http://media.xiph.org/tearsofsteel/Surround-TOS_DVDSURROUND-Dolby%205.1.ac3'
ffmpeg -i ToS-4k-1920.mov -i ToS-Dolby-5.1.ac3 -c:v copy -c:a copy -map 0:v:0 -map 1:a:0 ToS-4k-1920-Dolby.5.1.mp4
```

This new `mp4` file is now used as the input to the encoding script:

```sh
python -m dashlive.media.create -d 61 -i ToS-4k-1920-Dolby.5.1.mp4 -p tears --channels 6 \
   --kid a2c786d0-f9ef-4cb3-b333-cd323a4284a5 db06a8fe-ec16-4de2-9228-2c71e9b856ab -o tears-v2
```

### Multiple audio adaptation sets

This example has a `role="main"` audio adaptation set that is stereo, using the AAC codec. It
also has an additional `role="alternate"` audio adaptation set that uses the EAC3 codec and
has 5.1 audio channels.

```sh
test -e ToS-4k-1920.mov || curl -o ToS-4k-1920.mov http://ftp.nluug.nl/pub/graphics/blender/demo/movies/ToS/ToS-4k-1920.mov
test -e ToS-Dolby-5.1.ac3 || curl -o ToS-Dolby-5.1.ac3 'http://media.xiph.org/tearsofsteel/Surround-TOS_DVDSURROUND-Dolby%205.1.ac3'

python -m dashlive.media.create -d 30 -i ToS-4k-1920.mov --audio ToS-Dolby-5.1.ac3 -p tears3 -o tears-v3
```
