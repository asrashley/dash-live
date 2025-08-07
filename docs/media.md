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

There is a [create_media.py](../dashlive/media/create.py)
Python script which gives an example of how to encode and package the media files.

For example:

```sh
test -e "BigBuckBunny.mp4" || curl -o "BigBuckBunny.mp4" "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
python -m dashlive.media.create -i "BigBuckBunny.mp4" -p bbb --kid '1ab45440532c439994dc5c5ad9584bac' -o bbb
```
