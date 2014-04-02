#!/bin/bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

#config variables
API_URL="<api-url>"
DOWNLOAD_URL="<agent-download-url>"

#script variables
USAGE="Usage: curl -s $DOWNLOAD_URL | sudo bash /dev/stdin {-o <Organization token> [-c <Category name>] [-H <Host name>] [-x <Https proxy>] [-p <Python binary>] | -h for Help}"

#setup variables
INSTALL_PATH="/usr/local/sealion-agent"
TMP_FILE_PATH="/tmp/sealion-agent.XXXX"
TMP_DATA_FILE="/tmp/sealion-agent.response.XXXX"
PROXY=
AGENT_ID=
ORG_TOKEN=

log_output()
{
    OUTPUT=
    STREAM=1
    ST="O"

    case "$#" in
        "1")
            OUTPUT=$1
            ;;
        "2")
            OUTPUT=$1
            STREAM=$2
            ;;
    esac

    if [ "$OUTPUT" == "" ] ; then
        return 1
    fi

    if [ $STREAM -eq 2 ] ; then
        echo $OUTPUT >&2
        ST="E"
    else
        echo $OUTPUT >&1
    fi

    if [ "$UPDATE_LOG_FILE" == "" ] ; then
        if [ -w "$INSTALL_PATH/var/log" ] ; then
            UPDATE_LOG_FILE="$INSTALL_PATH/var/log/update.log"
        else
            UPDATE_LOG_FILE=" "
        fi
    fi

    if [ "$UPDATE_LOG_FILE" != " " ] ; then
        echo $(date +"%F %T,%3N - $ST: $OUTPUT") >>"$UPDATE_LOG_FILE"
    fi

    return 0
}

while getopts :i:o:c:H:x:p:a:r:v:h OPT ; do
    case "$OPT" in
        i)
            INSTALL_PATH=$OPTARG
            ;;
        x)
            PROXY="-x '$OPTARG'"
            ;;
        a)
            AGENT_ID=$OPTARG
            ;;
        o)
            ORG_TOKEN=$OPTARG
            ;;
        h)
            echo $USAGE
            exit 0
            ;;
        \?)
            echo "Invalid option '-$OPTARG'" >&2
            echo $USAGE
            exit 126
            ;;
        :)
            echo "Option '-$OPTARG' requires an argument" >&2
            echo $USAGE
            exit 125
            ;;
    esac
done

report_failure()
{
    curl -s PROXY -w "%{http_code}" -H "Content-Type: application/json" -X PUT -d "{\"reason\":\"$1\"}"  "$API_URL/orgs/$ORG_TOKEN/agents/$AGENT_ID/updatefail" >/dev/null 2>&1
}

TMP_DATA_FILE=$(mktemp -d $TMP_DATA_FILE)
log_output "Getting agent installer details..."
RET=$(curl -s $PROXY -w "%{http_code}" -H "Content-Type: application/json" "$API_URL/orgs/$ORG_TOKEN/agentVersion" -o "$TMP_DATA_FILE" 2>/dev/null)

if [[ $? -ne 0 || $RET -ne 200 ]] ; then
    log_output "Error: Failed to get agent installer details" 2
    rm -f $TMP_DATA_FILE
    exit 117
fi

DOWNLOAD_URL=$(cat $TMP_DATA_FILE)
rm -f $TMP_DATA_FILE
TMP_FILE_PATH=$(mktemp -d $TMP_FILE_PATH)
TMP_FILE_PATH=${TMP_FILE_PATH%/}
TMP_FILE_NAME="$TMP_FILE_PATH/sealion-agent.tar.gz"
log_output "Downloading agent installer..."
RET=$(curl -s $PROXY -w "%{http_code}" $DOWNLOAD_URL -o $TMP_FILE_NAME >/dev/null 2>&1)

if [ $? -ne 0 ] ; then
    log_output "Error: Failed to download agent installer" 2

    if [ $RET -eq 404 ] ; then
        report_failure 5
    fi

    if [[ -f "$INSTALL_PATH/bin/sealion-node" && -f "$INSTALL_PATH/etc/sealion" ]] ; then
        "$INSTALL_PATH/etc/sealion" start
    fi

    rm -rf $TMP_FILE_PATH
    exit 117
fi

tar -xf $TMP_FILE_NAME --directory="$TMP_FILE_PATH" >/dev/null 2>&1

if [ $? -ne 0 ] ; then
    log_output "Error: Failed to extract files" 2
    rm -rf $TMP_FILE_PATH
    exit 1
fi

$TMP_FILE_PATH/sealion-agent/install.sh "$@" -r curl
RET=$?

if [[ "$AGENT_ID" != "" && $RET -ne 0 ]] ; then
    report_failure $RET
    rm -rf $TMP_FILE_PATH

    if [[ -f "$INSTALL_PATH/bin/sealion-node" && -f "$INSTALL_PATH/etc/sealion" ]] ; then
        "$INSTALL_PATH/etc/sealion" start
    fi

    exit 123
fi

rm -rf $TMP_FILE_PATH
exit 0

