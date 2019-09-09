#!/bin/bash

#
# Encode a video file in to a DASH stream at multiple bitrates
#
set +x
VIDDIR=${HOME}/Downloads

#
# The source video file - this can be any format that FFMPEG supports
SRCFILE=BigBuckBunny.mp4
#
# The prefix to use for destination files
DESTFILE=bbb

#
# The directory to place the encoded files
DESTDIR=${HOME}/src/GoogleWebApps/dash-live/media/${DESTFILE}

#
# Duration of each segment (in seconds)
SEGMENT_DURATION=4

#
# Number of frames per second
FRAMERATE=24

#
# Duration of a segment (in frames)
FRAME_SEGMENT_DURATION=`expr $SEGMENT_DURATION '*' $FRAMERATE`

#
# The MP4 timescale to use for video
TIMESCALE=`expr $FRAMERATE '*' 10`

#
# The total duration of the final DASH stream (in seconds)
DURATION=`python -c "print(int(((9*60 + 56.45)//${SEGMENT_DURATION})*${SEGMENT_DURATION}))"`

#
# ffmpeg was compile with the following options:
# ./configure --enable-gpl --enable-version3 --enable-nonfree --enable-libx264 --enable-libvorbis --enable-libvpx

# encode(width,height,bitrate)
encode () {
    echo "${1}x${2} ${3}Kbps"
    if [ ! -d ${DESTDIR}/$3 ]; then
	mkdir ${DESTDIR}/$3
    fi
    PROFILE="baseline"
    CODECS="avc1.42001f mp4a. 40.2"
    CBR=`expr $3 \* 10 / 12`
    MINRATE=`expr $3 \* 10 / 14`
    LEVEL=3.1
    # BUFSIZE is set to 75% of VBV limit
    BUFSIZE="10500k"
    BUFSIZE="14000k"
    if [ $1 -gt 640 ]; then
	PROFILE="main"
	CODECS="avc1.64001f mp4a.40.2"
    fi
    if [ $2 -gt 720 ]; then
	PROFILE="high"
	CODECS="avc1.640028 mp4a.40.2"
	LEVEL=4.0
	# BUFSIZE is set to 75% of VBV limit
	BUFSIZE="18750k"
	BUFSIZE="25000k"
    fi
    local -i keyframe
    keyframe=0
    KEYFRAMES=""
    while [ ${keyframe} -lt ${DURATION} ]; do
    	if [ ! -z "${KEYFRAMES}" ]; then
	       KEYFRAMES+=","
	   fi
	   KEYFRAMES+="${keyframe}"
	   keyframe+=${SEGMENT_DURATION}
    done
    #[in]yadif=deint=interlaced,
    #/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
    #-f stream_segment -reference_stream v:0 -segment_time ${SEGMENT_DURATION} -segment_start_number 1 -individual_header_trailer 1 -segment_format mp4
    if [ ! -f ${DESTDIR}/$3/${DESTFILE}.mp4 ]; then
       # Encode the stream and check key frames are in the correct place
       (cd ${DESTDIR}/$3 && ffmpeg -ss 5 -ec deblock \
	       -i ${VIDDIR}/${SRCFILE} \
	       -vf drawtext='fontfile=/usr/share/fonts/truetype/freefont/FreeSansBold.ttf:fontsize=48:text='${3}'Kbps:x=(w-tw)/2:y=h-(2*lh):fontcolor=white:box=1:boxcolor=0x000000@0.7' \
               -video_track_timescale ${TIMESCALE} \
	       -map 0:v:0 -map 0:a:0 -map 0:a:0 \
	       -codec:v libx264 -profile:v $PROFILE -level:v ${LEVEL} -field_order progressive -bufsize ${BUFSIZE} -maxrate ${3}k -minrate ${MINRATE}k -b:v ${CBR}k -pix_fmt yuv420p -s "${1}x${2}" -x264opts keyint=${FRAME_SEGMENT_DURATION}:videoformat=pal -flags +cgop+global_header -flags2 -local_header -g ${FRAME_SEGMENT_DURATION}  -sc_threshold 0  \
	       -force_key_frames ${KEYFRAMES}  \
	       -codec:a:0 aac -b:a:0 96k -ac:a:0 2 -strict -2 \
               -codec:a:1 eac3 -b:a:1 320k -ac:a:1 6 \
	       -y -t $DURATION -threads 0 "${DESTFILE}.mp4") \
       && ffprobe -show_frames -print_format compact "${DESTDIR}/$3/${DESTFILE}.mp4" | awk -F '|' '($2 == "media_type=video") { \
    if ($4 == "key_frame=1") { \
        print i; \
        if((i%'${FRAME_SEGMENT_DURATION}')!=0) { \
            print "Error"; \
            exit(1); \
        } \
    } \
    ++i; \
} \
END { exit(0); }'
    fi
}

# encode(bitrate,bitrate,...)
package () {
    if [ -d ${DESTDIR}/dash ]; then
        rm ${DESTDIR}/dash/*.m??
    else
        mkdir ${DESTDIR}/dash
    fi
    FILES=""
    for bitrate in $*; do
        FILES="${DESTDIR}/${bitrate}/${DESTFILE}.mp4#video ${FILES}"
    done
    # Add AAC audio track
    FILES="${FILES} ${DESTDIR}/${1}/${DESTFILE}.mp4#trackID=2:role=main"
    # Add E-AC3 audio track
    FILES="${FILES} ${DESTDIR}/${1}/${DESTFILE}.mp4#trackID=3:role=alternate"
    echo $FILES
    (cd ${DESTDIR} && MP4Box -dash `expr ${SEGMENT_DURATION} '*' 1000` -frag `expr ${SEGMENT_DURATION} '*' 1000` -rap -frag-rap -single-file -profile dashavc264:live -profile-ext "urn:dvb:dash:profile:dvbdash:2014" -bs-switching inband -segment-ext m4s -segment-name 'dash_$RepresentationID$_$number%03d$' -out dash/manifest $FILES)
    rm ${DESTDIR}/${DESTFILE}_[1-9].mp4
    for repr in 1 2 3 4 5 6 7 8 9; do
        if [ -f ${DESTDIR}/dash/dash_${repr}_.mp4 ]; then
            (cd ${DESTDIR}/dash && cat dash_${repr}_.mp4 dash_${repr}_*.m4s >${DESTDIR}/${DESTFILE}_${repr}.mp4)
            (cd ${DESTDIR}/dash && rm dash_${repr}_.mp4 dash_${repr}_*.m4s )
        elif [ -f ${DESTDIR}/dash/manifest_set1_init.mp4 -a -f ${DESTDIR}/dash/dash_${repr}_001.m4s ]; then
            (cd ${DESTDIR}/dash && cat manifest_set1_init.mp4 dash_${repr}_*.m4s >${DESTDIR}/${DESTFILE}_${repr}.mp4)
            (cd ${DESTDIR}/dash && rm dash_${repr}_*.m4s )
        fi
    done
}

if [ ! -d ${DESTDIR} ] ; then
    mkdir ${DESTDIR}
fi
if [ ! -f ${VIDDIR}/${SRCFILE} ]; then
    curl -o ${VIDDIR}/${SRCFILE} "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
fi

#  352x288 700kbps
encode 384 216 230
encode 512 288 450
encode 640 360 690
encode 768 432 800
encode 1024 576 1250
encode 1280 720 2204
encode 1920 1080 3600

package 230 450 690 800 1250 2204 3600

