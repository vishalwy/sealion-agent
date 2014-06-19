#!/bin/bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

#script variables
USAGE="Usage: $0 {-v <version> [-d <domain>]} | -h"

#config variables
DEFAULT_DOMAIN="sealion.com"
DOMAIN=$DEFAULT_DOMAIN
VERSION=

while getopts :d:v:h OPT ; do
    case "$OPT" in
        d)
            DOMAIN=$OPTARG
            ;;
        v)
            VERSION=$OPTARG
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

VERSION="$(echo "$VERSION" | sed -e 's/^\s*//' -e 's/\s*$//')"
DOMAIN="$(echo "$DOMAIN" | sed -e 's/^\s*//' -e 's/\s*$//')"
TARGET=$DOMAIN

if [ "$VERSION" == "" ] ; then
    echo "Please specify a valid version for the build"
    echo $USAGE
    exit 1
fi

if [ "$DOMAIN" != "$DEFAULT_DOMAIN" ] ; then
    DOMAIN="-$DOMAIN"
else
    DOMAIN=".$DOMAIN"
fi

API_URL="https://api$DOMAIN"
AGENT_URL="https://agent$DOMAIN"

BASEDIR=$(readlink -f "$0")
BASEDIR=$(dirname "$BASEDIR")
BASEDIR=${BASEDIR%/}
OUTPUT="sealion-agent"
TARGET="bin/$TARGET"
cd "$BASEDIR"
rm -rf $TARGET >/dev/null 2>&1
mkdir -p $TARGET/$OUTPUT/agent
chmod +x $TARGET/$OUTPUT

generate_scripts()
{
    cp res/scripts/uninstall.sh $TARGET/$OUTPUT/agent/
    chmod +x $TARGET/$OUTPUT/agent/uninstall.sh
    echo "Uninstaller generated"
    cp res/scripts/curlike.py $TARGET/$OUTPUT/agent/bin/
    chmod +x $TARGET/$OUTPUT/agent/bin/curlike.py
    echo "Update script generated"
    cp res/scripts/unregister.py $TARGET/$OUTPUT/agent/bin/
    chmod +x $TARGET/$OUTPUT/agent/bin/unregister.py
    echo "Unregister script generated"
    cp res/scripts/monit.sh $TARGET/$OUTPUT/agent/bin/
    chmod +x $TARGET/$OUTPUT/agent/bin/monit.sh
    echo "Monit script generated"
    cp res/scripts/sealion $TARGET/$OUTPUT/agent/etc/init.d
    chmod +x $TARGET/$OUTPUT/agent/etc/init.d/sealion
    echo "Service script generated"
    cp res/scripts/check_dependency.py $TARGET/$OUTPUT/agent/bin/
    URL="$(echo "$API_URL" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(^api\_url\s*=\s*\)\(\"[^\"]\+\"\)/\1\"$URL\"/'"
    eval sed "$ARGS" $TARGET/$OUTPUT/agent/bin/check_dependency.py
    chmod +x $TARGET/$OUTPUT/agent/bin/check_dependency.py
    echo "Dependency script generated"
    INSTALLER=$TARGET/$OUTPUT/install.sh
    CURL_INSTALLER=$TARGET/curl-install.sh
    CURL_INSTALLER_NODE=$TARGET/curl-install-node.sh
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
    cp res/scripts/curl-install-node.sh $CURL_INSTALLER_NODE
    eval sed "$ARGS" $CURL_INSTALLER_NODE
    URL="$(echo "$API_URL/agents" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(^REGISTRATION\_URL=\)\(\"[^\"]\+\"\)/\1\"$URL\"/'"
    eval sed "$ARGS" $CURL_INSTALLER_NODE
    chmod +x $CURL_INSTALLER_NODE
    echo "Curl installer for node generated"
    cp res/README $TARGET/$OUTPUT/agent
    DATE="$(echo "$(date +"%F %T")" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    REVISION=$(git rev-parse --short=10 HEAD 2>/dev/null)

    if [ "$REVISION" != "" ] ; then
        REVISION="- $REVISION"
    fi

    sed -i "1iSeaLion Agent $VERSION - $DATE $REVISION" $TARGET/$OUTPUT/agent/README
    echo "Generated README"
}

find ../code/ -mindepth 1 -maxdepth 1 -type d -regextype sed ! -regex '.*/\(\(etc\)\|\(tmp\)\|\(bin\)\|\(var\)\)' -exec cp -r {} $TARGET/$OUTPUT/agent \;
cp -r res/etc $TARGET/$OUTPUT/agent
mkdir -p $TARGET/$OUTPUT/agent/etc/init.d
mkdir -p $TARGET/$OUTPUT/agent/bin
generate_scripts

if [ "$DOMAIN"  != "$DEFAULT_DOMAIN" ] ; then
    sed -i 's/\("level"\s*:\s*\)"[^"]\+"/\1"debug"/' "$TARGET/$OUTPUT/agent/etc/config.json"
    echo "Setting agent logging level to 'debug'"
fi

tar -zcvf "$TARGET/$OUTPUT-$VERSION-noarch.tar.gz" --exclude="*.pyc" --exclude="__pycache__" --exclude="*~" --exclude-vcs --exclude-backups --directory=$TARGET $OUTPUT/
rm -rf $TARGET/$OUTPUT

