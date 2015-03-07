#!/usr/bin/env bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

#script variables
USAGE="Usage: $0 {-o <Organization token> -v <Agent version> [-c <Category name>] [-H <Host name>] [-x <Proxy address>] [-a <API URL>] | -h for Help}"
ORG_TOKEN=
VERSION=
CATEGORY=
HOST_NAME=$(hostname)
PROXY=$https_proxy
NO_PROXY=$no_proxy
API_URL="https://api-test.sealion.com"

#parse command line options
while getopts :o:c:H:x:a:r:v:h OPT ; do
    case "$OPT" in
        o)
            ORG_TOKEN=$OPTARG
            ;;
        c)
            CATEGORY=$OPTARG
            ;;
        h)
            echo $USAGE
            exit 0
            ;;
        H)
            HOST_NAME=$OPTARG
            ;;
        x)
            PROXY=$OPTARG
            ;;
        a)
            API_URL=$OPTARG
            ;;
        v)
            VERSION=$OPTARG
            ;;
        \?)
            echo "Invalid option '-$OPTARG'" >&2
            echo $USAGE
            exit 1
            ;;
        :)
            echo "Option '-$OPTARG' requires an argument" >&2
            echo $USAGE
            exit 1
            ;;
    esac
done

#you need to specify organization token
if [ "$ORG_TOKEN" == "" ] ; then
    echo "Missing option '-o'" >&2
    echo $USAGE
    exit 1
fi

#you need to specify agent version
if [ "$VERSION" == "" ] ; then
    echo "Missing option '-v'" >&2
    echo $USAGE
    exit 1
fi

#script directory
BASEDIR=$(readlink -f "$0")
BASEDIR=${BASEDIR%/*}

#copy etc from res to code
cp -r "$BASEDIR/res/etc" "$BASEDIR/../code/"

#agent.json config
CONFIG="\"orgToken\": \"$ORG_TOKEN\", \"apiUrl\": \"$API_URL\", \"agentVersion\": \"$VERSION\", \"name\": \"$HOST_NAME\", \"ref\": \"$REF\""

#add category if specified
if [ "$CATEGORY" != "" ] ; then
    CONFIG="$CONFIG, \"category\": \"$CATEGORY\""
fi

"$BASEDIR/../code/bin/configure.py" -a "set" -k "" -v "{$CONFIG}" -n "$BASEDIR/../code/etc/agent.json"  #set the configuration
VARS=()  #array to hold proxy vars

#export https_proxy
if [ "$PROXY" != "" ] ; then
    VARS=(${VARS[@]} "{\"https_proxy\": \"$PROXY\"}")
fi

#export no_proxy
if [ "$NO_PROXY" != "" ] ; then
    VARS=(${VARS[@]} "{\"no_proxy\": \"$NO_PROXY\"}")
fi

#update config.json with proxy variables
CONFIG=$(IFS=$', '; echo "${VARS[*]}")
[ "$CONFIG" != "" ] && "$BASEDIR/../code/bin/configure.py" -a "add" -k "env" -v "[$CONFIG]" "$BASEDIR/../code/etc/config.json"

#update config.json with logging level
"$BASEDIR/../code/bin/configure.py" -a "set" -k "logging:level" -v "\"debug\"" "$BASEDIR/../code/etc/config.json"

echo "Generated config files at $BASEDIR/../code/etc"

