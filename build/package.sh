#!/bin/bash

VERSION="2.0.0"

USAGE="Usage: $0 {-t prod|test | -a <api url> -u <update url> | -h}"

TEST_API_URL="https://api-test.sealion.com"
TEST_UPDATE_URL="http://test.sealion.com/sealion-agent.tar.gz"

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
BASEDIR=$(dirname $BASEDIR)
BASEDIR=${BASEDIR%/}
OUTPUT=sealion-agent
TARGET="bin/$TARGET"
rm -rf $BASEDIR/$TARGET >/dev/null 2>&1
mkdir -p $BASEDIR/$TARGET/$OUTPUT/agent

generate_scripts()
{
    INSTALLER=$BASEDIR/$TARGET/$OUTPUT/install.sh
    cp $BASEDIR/scripts/install.sh $INSTALLER
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
    cp $BASEDIR/scripts/uninstall.sh $BASEDIR/$TARGET/$OUTPUT/agent/
    chmod +x $BASEDIR/$TARGET/$OUTPUT/agent/uninstall.sh
    echo "Uninstaller generated"
    cp $BASEDIR/scripts/sealion $BASEDIR/$TARGET/$OUTPUT/agent/etc/conf.d
    chmod +x $BASEDIR/$TARGET/$OUTPUT/agent/etc/conf.d/sealion
    echo "Service script generated"
}

find $BASEDIR/../code/ -mindepth 1 -maxdepth 1 -type d ! -name 'etc' -exec cp -r {} $BASEDIR/$TARGET/$OUTPUT/agent \;
cp $BASEDIR/../code/* $BASEDIR/$TARGET/$OUTPUT/agent
cp -r $BASEDIR/etc $BASEDIR/$TARGET/$OUTPUT/agent
mkdir -p $BASEDIR/$TARGET/$OUTPUT/agent/etc/conf.d
generate_scripts
tar -zcvf $BASEDIR/$TARGET/$OUTPUT.tar.gz --exclude="*.pyc" --exclude="var" --exclude="*~" --exclude-backups --directory=$BASEDIR/$TARGET $OUTPUT/
rm -rf $BASEDIR/$TARGET/$OUTPUT

