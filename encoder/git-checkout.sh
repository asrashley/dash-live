#!/bin/sh

die() {

        echo "${@}">&2
        exit 1
}

REPO="$1"
DIRNAME=$(basename --suffix=.git ${REPO})
GITSHA="$2"

echo "Cloning ${REPO} @ ${GITSHA}"
git clone \
    --config advice.detachedHead=false \
    --no-tags \
    ${REPO} || die "Failed to clone $REPO"
(cd $DIRNAME && git checkout ${GITSHA}) || die "Failed to check out ${GITSHA}"
