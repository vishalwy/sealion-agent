#!/bin/bash

TEST_API_URL="https://api-test.sealion.com"
TEST_UPDATE_URL="http://test.sealion.com/sealion-agent.tar.gz"

PROD_API_URL="https://api.sealion.com"
PROD_UPDATE_URL="http://api.sealion.com/sealion-agent.tar.gz"

API_URL=
UPDATE_URL=
TARGET=0

check_conflict()
{
    if [[ $TARGET -eq 1 || "$API_URL" != "" || "$UPDATE_URL" != "" ]] ; then
        echo "You cannot specify multiple targets or urls"
        exit 1
    fi
}

set_target()
{
    check_conflict
    API_URL=$1
    UPDATE_URL=$2
    TARGET=1
}

while getopts a:u:t: OPT ; do
    case "$OPT" in
        a)
            check_conflict
            API_URL=$OPTARG
            ;;
        u)
            check_conflict
            UPDATE_URL=$OPTARG
            ;;
        t)
            if [ "$OPTARG" == "prod" ] ; then
                set_target $PROD_API_URL $PROD_UPDATE_URL
            elif [ "$OPTARG" == "test" ] ; then
                set_target $TEST_API_URL $TEST_UPDATE_URL
            else
                echo "Invalid argument for option -$OPTARG." >&2    
                exit 1
            fi
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
    echo "Please specify valid target or urls"
    exit 1
fi

BASEDIR=$(dirname $0)
OUTPUT=sealion-agent

rm -rf $BASEDIR/bin >/dev/null 2>&1
mkdir -p $BASEDIR/bin/$OUTPUT/agent
find $BASEDIR/../code/ -mindepth 1 -maxdepth 1 -type d ! -name 'etc' -exec cp -r {} $BASEDIR/bin/$OUTPUT/agent \;
cp -r $BASEDIR/etc $BASEDIR/bin/$OUTPUT/agent
$BASEDIR/configure.sh -a $API_URL -u $UPDATE_URL
tar -zcvf $BASEDIR/bin/$OUTPUT.tar.gz --exclude="*.pyc" --exclude="var" --exclude="*~" --exclude-backups --directory=$BASEDIR/bin $OUTPUT/
rm -rf $BASEDIR/bin/$OUTPUT

