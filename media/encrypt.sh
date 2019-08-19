#!/bin/bash
KID='c001de8e567b5fcfbc22c565ed5bda24'
KEY='533a583a843436a536fbe2a5821c4b6c'
IV='c2b4b2f6ce549280'
#mp4encrypt --show-progress --method MPEG-CENC --key 1:${KEY}:${IV} --property 1:KID:${KID} ${1}.mp4 ${1}ENC.mp4
TEMPDIR="tmp-${1}"
mkdir ${TEMPDIR}
MP4Box -crypt drm.xml -fps 24 ${1}.mp4 -out ${TEMPDIR}/${1}-moov-enc.mp4
MP4Box -dash 4000 -frag 4000 -fps 24 -profile live -rap -out ${TEMPDIR}/${1}_enc ${TEMPDIR}/${1}-moov-enc.mp4
rm ${TEMPDIR}/${1}-moov-enc.mp4
seg="1"
OUTPUT="${1}ENC.mp4"
cp ${TEMPDIR}/${1}-moov-enc_dashinit.mp4 ${OUTPUT}
rm ${TEMPDIR}/${1}-moov-enc_dashinit.mp4
while [ -f ${TEMPDIR}/${1}-moov-enc_dash${seg}.m4s ]; do
    echo "${TEMPDIR}/${1}-moov-enc_dash${seg}.m4s"
    cat "${TEMPDIR}/${1}-moov-enc_dash${seg}.m4s" >> ${OUTPUT}
    rm "${TEMPDIR}/${1}-moov-enc_dash${seg}.m4s"
    seg=$(expr ${seg} + 1)
done
rm ${TEMPDIR}/*.mpd
rmdir ${TEMPDIR}
python gen_index.py -i ${OUTPUT}
 
