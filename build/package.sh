#!/bin/bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

#script variables
USAGE="Usage: $0 {[-s <sub domain>] [-v <version>]} | -h"

#config variables
SUBDOMAIN=
API_URL="https://api.sealion.com"
AGENT_URL="https://agent.sealion.com"
TARGET="sealion.com"
VERSION="3.0.0"

while getopts :s:v:h OPT ; do
    case "$OPT" in
        s)
            SUBDOMAIN=$OPTARG
            ;;
        h)
            echo $USAGE
            exit 0
            ;;
        \?)
            echo "Invalid option -$OPTARG" >&2
            echo $USAGE
            exit 126
            ;;
        :)
            echo "Option $OPTARG requires an argument." >&2
            echo $USAGE
            exit 125
            ;;
    esac
done

SUBDOMAIN="$(echo "$SUBDOMAIN" | sed -e 's/^\s*//' -e 's/\s*$//')"

if [ "$SUBDOMAIN" != "" ] ; then
    API_URL="https://api-$SUBDOMAIN.sealion.com"
    AGENT_URL="https://agent-$SUBDOMAIN.sealion.com"
    TARGET="$SUBDOMAIN.sealion.com"
fi

BASEDIR=$(readlink -f "$0")
BASEDIR=$(dirname "$BASEDIR")
BASEDIR=${BASEDIR%/}
OUTPUT=sealion-agent
TARGET="bin/$TARGET"
cd "$BASEDIR"
rm -rf $TARGET >/dev/null 2>&1
mkdir -p $TARGET/$OUTPUT/agent

generate_scripts()
{
    cp res/scripts/uninstall.sh $TARGET/$OUTPUT/agent/
    chmod +x $TARGET/$OUTPUT/agent/uninstall.sh
    echo "Uninstaller generated"
    cp res/scripts/monit.sh $TARGET/$OUTPUT/agent/bin/
    chmod +x $TARGET/$OUTPUT/agent/bin/monit.sh
    echo "Monit script generated"
    cp res/scripts/sealion $TARGET/$OUTPUT/agent/etc/init.d
    chmod +x $TARGET/$OUTPUT/agent/etc/init.d/sealion
    echo "Service script generated"
    INSTALLER=$TARGET/$OUTPUT/install.sh
    CURL_INSTALLER=$TARGET/curl-install.sh
    cp res/scripts/install.sh $INSTALLER
    URL="$(echo "$API_URL" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(^API\_URL=\)\(\"[^\"]\+\"\)/\1\"$URL\"/'"
    eval sed "$ARGS" $INSTALLER
    ARGS="-i 's/\(^VERSION=\)\(\"[^\"]\+\"\)/\1\"$VERSION\"/'"
    eval sed "$ARGS" $INSTALLER
    chmod +x $INSTALLER
    echo "Installer generated"
    cp res/scripts/curl-install.sh $CURL_INSTALLER
    URL="$(echo "$API_URL" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(^API\_URL=\)\(\"[^\"]\+\"\)/\1\"$URL\"/'"
    eval sed "$ARGS" $CURL_INSTALLER
    URL="$(echo "$AGENT_URL" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(^DOWNLOAD\_URL=\)\(\"[^\"]\+\"\)/\1\"$URL\"/'"
    eval sed "$ARGS" $CURL_INSTALLER    
    chmod +x $CURL_INSTALLER
    echo "Curl installer generated"
    cp res/README $TARGET/$OUTPUT/agent
    DATE="$(echo "$(date +"%F %T")" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    REVISION=$(git rev-parse --short=10 HEAD 2>/dev/null)

    if [ "$REVISION" != "" ] ; then
        REVISION="- $REVISION"
    fi

    sed -i "1iSeaLion Agent $VERSION - $DATE $REVISION" $TARGET/$OUTPUT/agent/README
    echo "Generated README"
}

find ../code/ -mindepth 1 -maxdepth 1 -type d ! -name 'etc' -exec cp -r {} $TARGET/$OUTPUT/agent \;
cp -r res/etc $TARGET/$OUTPUT/agent
mkdir -p $TARGET/$OUTPUT/agent/etc/init.d
mkdir -p $TARGET/$OUTPUT/agent/bin
generate_scripts
tar -zcvf $TARGET/$OUTPUT.tar.gz --exclude="*.pyc" --exclude="var" --exclude="__pycache__" --exclude="*~" --exclude-vcs --exclude-backups --directory=$TARGET $OUTPUT/
rm -rf $TARGET/$OUTPUT

