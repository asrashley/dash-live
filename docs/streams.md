# Streams

## Introduction

The media files need to be uploaded once the dash server is running. The
[streams](http://localhost:5000/streams) page can be used to create a
stream entry. Clicking on the title of the stream on the
[streams](http://localhost:5000/streams) page will navigate to a page
that allows media files to be uploaded.

Each stream entry represents a playable media stream. Each stream
must have at least one video and one audio MP4 file. Typically each
stream will have multiple video files associated with it, one for
each available bitrate.

Once a stream entry has been created, media files can be uploaded
and indexed. See [media](./media.md) for more information about
the details of media files.

If there are encrypted media files, the key IDs (KID) and encryption key
need to be configured. The media index process will automatically add new
key entries for each KID found in the media file.

It is possible to omit the encryption key and just provide the KID.
In this case, the server will auto-generate the encryption key using
the [key generation algorithm provided by MicroSoft PlayReady](https://learn.microsoft.com/en-us/playready/specifications/playready-key-seed)
using the test key seed. Click on the `Edit` button for the appropriate KID
and then click the "Key is auto-computed?" check box.

Alternatively, the value of the key can be provided manually using the
"Key" input text field.

## Stream Properties

Each stream requires a `title` and `directory` value to be specified.
The `title` property sets the user-facing name of the stream. The
`directory` property sets the name of the directory that is used to
store media files, and also it used in the DASH URL for this stream.

The `Marlin LA URL` property sets the license URL value when using the
Marlin DRM system. In the future this option will probably be moved
into the `Stream defaults` settings.

The `PlayReady LA URL` property sets the license URL value when using the
PlayReady DRM system. In the future this option will probably be moved
into the `Stream defaults` settings.

### Timing reference

The `Timing reference` property is used to select which media file is
used as the reference when computing timecodes in the stream. This
option performs two different tasks depending upon whether the playback
mode is live-stream or on-demand.

When playback mode is on-demand, the `Timing reference` property is used
to set the duration of the on-demand stream.

When playback mode is live-stream, the `Timing reference` property is used
to calculate how many times the stream has looped. Imagine if the media
file chosen as the `Timing reference` was to be played in an endless loop,
starting at `availability start time`.

When joining this pseudo live stream, the server will calculate how many
times this reference file would have looped, and uses that to adjust all
other audio, video, and text components in the stream. This is required
because there might be small differences between the durations of the
various media files in the stream. For example, if the audio file is
2 milliseconds longer than the reference video file, it would not take
many loops for audio and video to become out of sync.

### Stream defaults

As described on the [/options](http://localhost:5000/options) page of the
site, there are a large number of CGI options that can be applied to modify
various aspects of the stream. The `Stream defaults` property allows providing
a set of values to pre-apply before applying any CGI parameters.

## Uploading and Indexing Media Files

The `Upload Media` section of the stream page can be used to add new audio,
video or text files to this stream. Once a file has been uploaded, it needs
to be indexed, so that the server can discover the details about every
segment in the file.

Upload the media files, one at a time. After uploading, each media file needs
to be indexed, using the "index" button beside each media item. The index process
finds each segment in the file and other information such as codecs, timescale and
duration.

## Automating Upload

The [dashlive.upload](../dashlive/upload.py) script can be used to automate the
installation of streams, files and keys. Firstly, go the `streams` page and click
the `Upload a stream` button. This will cause the server to generate a temporary
upload token and display this token on the HTML page.

This token can then be used for up to an hour for uploading media:

```sh
python -m dashlive.upload --token=abcddac2-61ea-4e1a-a1e3-5b502506e704 --host http://localhost:5000/ bbb.json
```

Where `bbb.json` is a JSON file that looks like this:

```json
{
    "keys": [{
            "computed": false,
            "key": "533a583a843436a536fbe2a5821c4b6c",
            "kid": "c001de8e567b5fcfbc22c565ed5bda24"
        }, {
            "computed": true,
            "kid": "1ab45440532c439994dc5c5ad9584bac"
        }
    ],
    "streams": [{
        "directory": "bbb",
        "title": "Big Buck Bunny",
        "marlin_la_url": "ms3://ms3.test.expressplay.com:8443/hms/ms3/rights/?b=...",
        "playready_la_url": "https://test.playready.microsoft.com/service/rightsmanager.asmx?cfg={cfgs}",
        "files": [
            "bbb_a1.mp4", "bbb_a1_enc.mp4", "bbb_a2.mp4", "bbb_a2_enc.mp4",
            "bbb_v1.mp4", "bbb_v1_enc.mp4", "bbb_v2.mp4", "bbb_v2_enc.mp4",
            "bbb_v3.mp4", "bbb_v3_enc.mp4", "bbb_v4.mp4", "bbb_v4_enc.mp4",
            "bbb_v5.mp4", "bbb_v5_enc.mp4", "bbb_v6.mp4", "bbb_v6_enc.mp4",
            "bbb_v7.mp4", "bbb_v7_enc.mp4"
        ],
        "timing_ref": "bbb_v1.mp4"
    }]
}
```

The [dashlive.upload](../dashlive/upload.py) script will upload all of the
keys, streams and files listed in the JSON file that don't already exist
on the server.

## Viewing Media File Details

Once a media file has been indexed, its details can be viewed by clicking
on the link on the filename. The `Media file` page provides a `View segments`
button that will show a list of every segment in the media file.

Each media file contains an initialization segment, that provides essential
information about the file. Each media file will contain multiple media
segments. Each media segment is self-contained, in that they can be decoded
without data from any other media segment.

The page showing the list of segments provides links for each segment. Clicking
one of these links will show all of the ISO BMFF boxes within that segment.

See the [Information technology – Coding of audio-visual objects – Part 12: ISO base media file format; ISO/IEC 14496-12:2008](https://standards.iso.org/ittf/PubliclyAvailableStandards/c051533_ISO_IEC_14496-12_2008.zip)
specification for more details.
