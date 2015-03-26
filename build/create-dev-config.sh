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

    local USAGE="Usage: $0 [options]\nOptions:\n"
    USAGE+=" -o,\t--org-token <arg>  \tOrganization token to be used\n"
    USAGE+=" -c,\t--category <arg>   \tCategory name under which the server to be registered\n"
    USAGE+=" -H,\t--host-name <arg>  \tServer name to be used\n"
    USAGE+=" -x,\t--proxy <arg>      \tProxy server details\n"
    USAGE+=" -a,\t--api-url <arg>    \tAPI URL for the agent; default to 'https://api-test.sealion.com'\n"
    USAGE+=" -v,\t--version <arg>    \tAgent version to be used\n"
    USAGE+=" -h,\t--help             \tDisplay this information"
    echo -e "$USAGE"
    return 0
}

#script variables
ORG_TOKEN=
VERSION=
CATEGORY=
HOST_NAME=$(hostname)
PROXY=$https_proxy
NO_PROXY=$no_proxy
API_URL="https://api-test.sealion.com"

#script directory
BASEDIR=$(readlink -f "$0")
BASEDIR=${BASEDIR%/*}

source "$BASEDIR/res/scripts/opt-parse.sh"
opt_parse o:c:H:x:a:v:h "org-token= category= host-name= proxy= api-url= version= help" OPTIONS ARGS "$@"

if [ $? -ne 0 ] ; then
    echo "$OPTIONS" >&2
    usage
    exit 1
fi

for INDEX in "${!OPTIONS[@]}" ; do
    if [ $(( INDEX%2 )) -ne 0 ] ; then
        continue
    fi

    OPT_ARG=${OPTIONS[$(( INDEX+1 ))]}

    case "${OPTIONS[$INDEX]}" in
        o\org-token)
            ORG_TOKEN=$OPT_ARG
            ;;
        c|category)
            CATEGORY=$OPT_ARG
            ;;
        h|help)
            usage 1
            exit 0
            ;;
        H|host-name)
            HOST_NAME=$OPT_ARG
            ;;
        x|proxy)
            PROXY=$OPT_ARG
            ;;
        a|api-url)
            API_URL=$OPT_ARG
            ;;
        v|version)
            VERSION=$OPT_ARG
            ;;
    esac
done

#there should be an organization token
if [ "$ORG_TOKEN" == '' ] ; then
    echo "Please specify an organization token using '-o'" >&2
    usage
    exit 1
fi

#you need to specify agent version
if [ "$VERSION" == "" ] ; then
    echo "Please specify a version token using '-v'" >&2
    usage
    exit 1
fi

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
    VARS=("${VARS[@]}" "{\"https_proxy\": \"$PROXY\"}")
fi

#export no_proxy
if [ "$NO_PROXY" != "" ] ; then
    VARS=("${VARS[@]}" "{\"no_proxy\": \"$NO_PROXY\"}")
fi

#update config.json with proxy variables
CONFIG=$(IFS=', '; echo "${VARS[*]}")
[ "$CONFIG" != "" ] && "$BASEDIR/../code/bin/configure.py" -a "add" -k "env" -v "[$CONFIG]" "$BASEDIR/../code/etc/config.json"

#update config.json with logging level
"$BASEDIR/../code/bin/configure.py" -a "set" -k "logging:level" -v "\"debug\"" "$BASEDIR/../code/etc/config.json"

echo "Generated config files at $BASEDIR/../code/etc"

