#!/bin/bash

API_URL="<api-url>"
DOWNLOAD_URL="<agent-download-url>"
TMP_FILE_PATH=$(mktemp -d /tmp/sealion-agent.XXXX)
TMP_FILE_PATH=${TMP_FILE_PATH%/}
TMP_FILE_NAME="$TMP_FILE_PATH/sealion-agent.tar.gz"
USAGE="Usage: curl -s $DOWNLOAD_URL {-o <Organization token> [-c <Category name>] [-H <Host name>] [-x <Https proxy>] [-p <Python binary>] | -h for Help}"
INSTALL_PATH="/usr/local/sealion-agent"
PROXY=
AGENT_ID=
ORG_TOKEN=

log_output()
{
    OUTPUT=
    STREAM=1
    ST="I"

    case "$#" in
        "1")
            OUTPUT=$1
            ;;
        "2")
            OUTPUT=$1
            STREAM=$2
            ;;
    esac

    if [ "$OUTPUT" == "" ]
        return 1
    fi

    if [ $STREAM -eq 2 ] ; then
        echo $OUTPUT >&2
        ST="E"
    else
        echo $OUTPUT >&1
    fi

    if [[ -d "$INSTALL_PATH/var/log" ]] ; then
        echo "$(date): $ST: $OUTPUT" >>"$INSTALL_PATH/var/log/update.log"
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
            log_output $USAGE
            exit 0
            ;;
        \?)
            log_output "Invalid option '-$OPTARG'" 2
            log_output $USAGE
            exit 126
            ;;
        :)
            log_output "Option '-$OPTARG' requires an argument" 2
            log_output $USAGE
            exit 125
            ;;
    esac
done

log_output "Downloading agent installer..."
curl -s $PROXY $DOWNLOAD_URL -o $TMP_FILE_NAME >/dev/null 2>&1

if [ $? -ne 0 ] ; then
    log_output "Error: Failed to download agent installer" 2
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
    RET=`curl -s PROXY -w "%{http_code}" -H "Content-Type: application/json" -X PUT -d "{\"reason\":\"$RET\"}"  "$API_URL/orgs/$ORG_TOKEN/agents/$AGENT_ID/updatefail" >/dev/null 2>&1`
    rm -rf $TMP_FILE_PATH

    if [[ -f "$INSTALL_PATH/bin/sealion-node" && -f "$INSTALL_PATH/etc/sealion" ]] ; then
        "$INSTALL_PATH/etc/sealion" start
    fi

    exit 123
fi

rm -rf $TMP_FILE_PATH
exit 0

