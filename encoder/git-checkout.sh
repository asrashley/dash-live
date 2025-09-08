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
    --config user.email="noreply@local" \
    --config user.name="Docker Container" \
    --no-tags \
    ${REPO} || die "Failed to clone $REPO"
(cd $DIRNAME && git checkout ${GITSHA}) || die "Failed to check out ${GITSHA}"
(cd $DIRNAME && git switch -c dashlive) || die "Failed to create dashlive branch"

if [ -d patches/${DIRNAME} ]; then
    for patch in patches/${DIRNAME}/*.patch
    do
        am=$(readlink -f ${patch})
        (cd $DIRNAME && git am ${am}) || die "Failed to apply patch ${patch}"
    done
fi
