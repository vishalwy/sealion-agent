#!/bin/bash

VERSION="2.0.0"

#config variables
API_URL=
UPDATE_URL=

BASEDIR=$(dirname $0)

while getopts a:u: OPT ; do
    case "$OPT" in
        a)
            API_URL=$OPTARG
            ;;
        u)
            UPDATE_URL=$OPTARG
            ;;
        \?)
            echo "Invalid argument -$OPTARG" >&2
            exit 126
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            exit 125
            ;;
    esac
done

if [[ "$API_URL" == "" || "$UPDATE_URL" == "" ]] ; then
    echo "Missing arguments"
    exit 1
fi

mkdir -p $BASEDIR/bin/sealion-agent
TARGET=$BASEDIR/bin/sealion-agent/installer.sh
cp $BASEDIR/scripts/installer.sh.in $TARGET
API_URL="$(echo "$API_URL" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
ARGS="-i 's/\(^API\_URL=\)\(\"[^\"]\+\"\)/\1\"$API_URL\"/'"
eval sed "$ARGS" $TARGET
UPDATE_URL="$(echo "$UPDATE_URL" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
ARGS="-i 's/\(^UPDATE\_URL=\)\(\"[^\"]\+\"\)/\1\"$UPDATE_URL\"/'"
eval sed "$ARGS" $TARGET
ARGS="-i 's/\(^VERSION=\)\(\"[^\"]\+\"\)/\1\"$VERSION\"/'"
eval sed "$ARGS" $TARGET
echo "Installer generated at $TARGET"



