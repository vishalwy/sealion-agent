#!/usr/bin/env bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[ $? -eq 127 ] && exit 127' ERR  #exit in case command not found

usage()
{
    if [ "$1" != "1" ] ; then
        echo "Run '$0 --help' for more information"
        return 0
    fi

    local USAGE="Usage: $0 [options] <version>\nOptions:\n"
    USAGE+=" -d,\t--domain <arg> \tDomain for which the tarball to be generated; default to 'sealion.com'\n"
    USAGE+=" -h,\t--help         \tDisplay this information"
    echo -e "$USAGE"
    return 0
}

#config variables
DEFAULT_DOMAIN="sealion.com"
DOMAIN=$DEFAULT_DOMAIN
VERSION=

#directory of the script
BASEDIR=$(readlink -f "$0")
BASEDIR=${BASEDIR%/*}

source "$BASEDIR/res/scripts/opt-parse.sh"
opt_parse d:v:h "domain= help" OPTIONS ARGS "$@"

if [ $? -ne 0 ] ; then
    echo "$OPTIONS" >&2
    usage
    exit 125
fi

for INDEX in "${!OPTIONS[@]}" ; do
    if [ $(( INDEX%2 )) -ne 0 ] ; then
        continue
    fi

    OPT_ARG=${OPTIONS[$(( INDEX+1 ))]}

    case "${OPTIONS[$INDEX]}" in
        d|domain)
            DOMAIN=$OPT_ARG
            ;;
        h|help)
            usage 1
            exit 0
            ;;
    esac
done

for ARG in "${ARGS[@]}" ; do
    VERSION=$ARG
done

VERSION="$(echo "$VERSION" | sed -e 's/^\s*//' -e 's/\s*$//')"
DOMAIN="$(echo "$DOMAIN" | sed -e 's/^\s*//' -e 's/\s*$//')"
TARGET=$DOMAIN

#you need to specify the version
if [ "$VERSION" == "" ] ; then
    echo "Please specify a valid version for the build"
    usage
    exit 1
fi

#if domain is sealion.com then api url is api.sealion.com
#if domain is something lik test.sealion.com then api url is api-test.sealion.com
#agent download url also follows this naming convention
if [ "$DOMAIN" != "$DEFAULT_DOMAIN" ] ; then
    DOMAIN="-$DOMAIN"
else
    DOMAIN=".$DOMAIN"
fi

API_URL="https://api$DOMAIN"
AGENT_URL="https://agent$DOMAIN"
OUTPUT="sealion-agent"
ORIG_DOMAIN="$TARGET"
TARGET="bin/$TARGET"

#move to current dir so that all the paths are available
cd "$BASEDIR"

#cleanup and recreate the output directories
rm -rf $TARGET >/dev/null 2>&1
mkdir -p $TARGET/$OUTPUT/agent
chmod +x $TARGET/$OUTPUT

#function to generate various scripts
generate_scripts()
{
    cp res/scripts/sealion $TARGET/$OUTPUT/agent/etc/init.d
    chmod +x $TARGET/$OUTPUT/agent/etc/init.d/sealion
    echo "Service script generated"
    cp res/scripts/uninstall.sh $TARGET/$OUTPUT/agent/
    chmod +x $TARGET/$OUTPUT/agent/uninstall.sh
    echo "Uninstaller generated"
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
    DATE="$(echo "$(date +"%F %T %Z")" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    REVISION=$(git rev-parse --short=10 HEAD 2>/dev/null)

    if [ "$REVISION" != "" ] ; then
        REVISION="- $REVISION"
    fi

    #add version, date and git revision at the top ReADME
    sed -i "1iSeaLion Agent $VERSION - $DATE $REVISION" $TARGET/$OUTPUT/agent/README

    echo "README generated"
}

#copy the src directories to output
find ../code/ -mindepth 1 -maxdepth 1 -type d -regextype sed -regex '.*/\(\(lib\)\|\(opt\)\|\(src\)\|\(bin\)\)' -exec cp -r {} $TARGET/$OUTPUT/agent \;

cp -r res/etc $TARGET/$OUTPUT/agent  #copy etc folder from res
mkdir -p $TARGET/$OUTPUT/agent/etc/init.d  #make init.d folder
generate_scripts  #generate scripts

#if domain is not sealion.com, then set the logging level to debug
if [ "$ORIG_DOMAIN"  != "$DEFAULT_DOMAIN" ] ; then
    "$TARGET/$OUTPUT/agent/bin/configure.py" -a "set" -k "logging:level" -v "\"debug\"" "$TARGET/$OUTPUT/agent/etc/config.json"
    echo "Agent logging level set to 'debug'"
fi

#generate tar in the output directory and cleanup temp folderes created
echo "Generating $TARGET/$OUTPUT-$VERSION-noarch.tar.gz..."
tar -zcvf "$TARGET/$OUTPUT-$VERSION-noarch.tar.gz" --exclude="*.pyc" --exclude="__pycache__" --exclude="*~" --exclude-vcs --exclude-backups --directory=$TARGET $OUTPUT/ | (while read LINE; do echo "    $LINE"; done)
rm -rf $TARGET/$OUTPUT

