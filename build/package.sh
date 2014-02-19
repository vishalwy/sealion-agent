#!/bin/bash

VERSION="2.0.0"

USAGE="Usage: $0 {-t prod|test | -a <api url> -u <update url> | -h}"

TEST_API_URL="https://api-test.sealion.com"
TEST_UPDATE_URL="https://agent-test.sealion.com/sealion-agent.tar.gz"

PROD_API_URL="https://api.sealion.com"
PROD_UPDATE_URL="https://s3.amazonaws.com/sealion.com/sealion-agent.tar.gz"

API_URL=
UPDATE_URL=
TARGET="custom"

check_conflict()
{
    if [[ "$API_URL" != "" && "$UPDATE_URL" != "" ]] ; then
        echo "You cannot specify multiple targets or urls"
        exit 1
    fi
}

set_target()
{
    check_conflict
    TARGET=$1
    API_URL=$2
    UPDATE_URL=$3
}

while getopts :a:u:t:h OPT ; do
    case "$OPT" in
        a)
            check_conflict
            API_URL=$OPTARG
            ;;
        u)
            check_conflict
            UPDATE_URL=$OPTARG
            ;;
        h)
            echo $USAGE
            exit 0
            ;;
        t)
            if [ "$OPTARG" == "prod" ] ; then
                set_target "prod" $PROD_API_URL $PROD_UPDATE_URL
            elif [ "$OPTARG" == "test" ] ; then
                set_target "test" $TEST_API_URL $TEST_UPDATE_URL
            else
                echo "Invalid argument for option -$OPTARG." >&2    
                exit 1
            fi
            ;;
        \?)
            echo "Invalid option -$OPTARG" >&2
            exit 126
            ;;
        :)
            echo "Option $OPTARG requires an argument." >&2
            exit 125
            ;;
    esac
done

if [[ "$API_URL" == "" || "$UPDATE_URL" == "" ]] ; then
    echo "Please specify valid target or urls"
    echo $USAGE
    exit 1
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
    cp scripts/uninstall.sh $TARGET/$OUTPUT/agent/
    chmod +x $TARGET/$OUTPUT/agent/uninstall.sh
    echo "Uninstaller generated"
    cp scripts/monit.sh $TARGET/$OUTPUT/agent/bin/
    chmod +x $TARGET/$OUTPUT/agent/bin/monit.sh
    echo "Monit script generated"
    cp scripts/sealion $TARGET/$OUTPUT/agent/etc/init.d
    chmod +x $TARGET/$OUTPUT/agent/etc/init.d/sealion
    echo "Service script generated"
    INSTALLER=$TARGET/$OUTPUT/install.sh
    CURL_INSTALLER=$TARGET/curl-install.sh
    cp scripts/install.sh $INSTALLER
    URL="$(echo "$API_URL" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(^API\_URL=\)\(\"[^\"]\+\"\)/\1\"$URL\"/'"
    eval sed "$ARGS" $INSTALLER
    URL="$(echo "$UPDATE_URL" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(^UPDATE\_URL=\)\(\"[^\"]\+\"\)/\1\"$URL\"/'"
    eval sed "$ARGS" $INSTALLER
    ARGS="-i 's/\(^VERSION=\)\(\"[^\"]\+\"\)/\1\"$VERSION\"/'"
    eval sed "$ARGS" $INSTALLER
    chmod +x $INSTALLER
    echo "Installer generated"
    cp scripts/curl-install.sh $CURL_INSTALLER
    ARGS="-i 's/\(^DOWNLOAD\_URL=\)\(\"[^\"]\+\"\)/\1\"$URL\"/'"
    eval sed "$ARGS" $CURL_INSTALLER    
    chmod +x $CURL_INSTALLER
    echo "Curl installer generated"
}

find ../code/ -mindepth 1 -maxdepth 1 -type d ! -name 'etc' -exec cp -r {} $TARGET/$OUTPUT/agent \;
cp ../code/* $TARGET/$OUTPUT/agent
cp -r etc $TARGET/$OUTPUT/agent
mkdir -p $TARGET/$OUTPUT/agent/etc/init.d
mkdir -p $TARGET/$OUTPUT/agent/bin
generate_scripts
tar -zcvf $TARGET/$OUTPUT.tar.gz --exclude="*.pyc" --exclude="var" --exclude="*~" --exclude-backups --directory=$TARGET $OUTPUT/
rm -rf $TARGET/$OUTPUT

