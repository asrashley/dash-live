#!/bin/bash
function die() {
  echo $*
  exit 1
}

USER_GID=$(id -g)
USER_UID=$(id -u)

volumes=""
next_arg=""
for arg in $*
do
    if [ ! -z "${next_arg}" ]; then
        if [ "${next_arg}" == "output" ]; then
            if [ ! -d "${arg}" ]; then
                mkdir -p ${arg} || die "Failed to create directory ${arg}"
            fi
        elif [ ! -f "${arg}" ]; then
            echo "Failed to find ${next_arg} file ${arg}"
            exit 1
        fi
        fname=$(readlink -f "${arg}")
        if [ "${next_arg}" == "output" ]; then
            volumes="${volumes} -v ${fname}:${arg}"
        else
            volumes="${volumes} -v ${fname}:${arg}:ro"
        fi
        next_arg=""
        continue
    fi
    case "${arg}" in
        "-o"|"--output")
            next_arg="output"
        ;;
        "--subtitles")
            next_arg="subtitles"
        ;;
        "--input"|"-i")
            next_arg="input"
        ;;
    esac
done

set -x
docker run ${volumes} \
    -e USER_GID=${USER_GID} -e USER_UID=${USER_UID} \
    -t dashlive/encoder:latest $*