#!/usr/bin/env bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

#config variables
API_URL="<api-url>"
DOWNLOAD_URL="<agent-download-url>"

#script variables
USAGE="Usage: curl -s $DOWNLOAD_URL | sudo bash /dev/stdin {-o <Organization token> [-c <Category name>] [-H <Host name>] [-x <Proxy address>] [-p <Python binary>] | -h for Help}"
USER_NAME="sealion"
ORIG_URL_CALLER=$([ "$URL_CALLER" != "" ] && echo "$URL_CALLER" || echo "curl")
unset -v URL_CALLER

#setup variables
INSTALL_PATH="/usr/local/sealion-agent"
TMP_FILE_PATH="/tmp/sealion-agent.XXXX"
TMP_DATA_FILE="/tmp/sealion-agent.response.XXXX"
PROXY=
AGENT_ID=
ORG_TOKEN=

call_url()
{
    ARGS=("$@")
    PARAMS=""

    for ARG in "${ARGS[@]}" ; do
        ARG=${ARG//\"/\\\"}
        PARAMS="$PARAMS \"$ARG\""
    done

    bash -c "$ORIG_URL_CALLER $PARAMS"
    return $?
}

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
        DEST=$([ -f "$INSTALL_PATH/var/log/update.log" ] && echo "$INSTALL_PATH/var/log/update.log" || echo "$INSTALL_PATH/var/log")

        if [[ "$(id -u -n)" == "$USER_NAME" && -w "$DEST" ]] ; then
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

read_and_log()
{
    OUTPUT_STREAM=1

    if [ "$1" == "2" ] ; then
        OUTPUT_STREAM=2
    fi

    while read -t 300 line; do 
        log_output "${line}" $OUTPUT_STREAM 
    done
}

report_failure()
{
    call_url -s $PROXY -H "Content-Type: application/json" -X PUT -d "{\"reason\":\"$1\"}"  "$API_URL/orgs/$ORG_TOKEN/agents/$AGENT_ID/updatefail" >/dev/null 2>&1
}

check_dependency()
{
    WHICH_COMMANDS=("sed" "tar" "bash" "grep" "mktemp")
    MISSING_COMMANDS=""
    PADDING="      "

    for COMMAND in "${WHICH_COMMANDS[@]}" ; do
        if [ "$(type -P $COMMAND 2>/dev/null)" == "" ] ; then
            MISSING_COMMANDS=$([ "$MISSING_COMMANDS" != "" ] && echo "$MISSING_COMMANDS\n$PADDING Cannot locate command '$COMMAND'" || echo "$PADDING Cannot locate command '$COMMAND'")
        fi
    done

    if [ "$MISSING_COMMANDS" != "" ] ; then
        OUTPUT=$(echo -e "Error: Command dependency check failed\n$MISSING_COMMANDS")
        log_output "$OUTPUT" 2

        if [ "$AGENT_ID" != "" ] ; then
            report_failure 6
        fi
        
        exit 123
    fi
}

while getopts :i:o:c:H:x:p:a:r:v:h OPT ; do
    case "$OPT" in
        i)
            INSTALL_PATH=$OPTARG
            ;;
        x)
            PROXY="-x $OPTARG"
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

INSTALL_PATH=$(eval echo "$INSTALL_PATH")

if [[ "$INSTALL_PATH" != "" && ${INSTALL_PATH:0:1} != "/" ]] ; then
    INSTALL_PATH="$(pwd)/$INSTALL_PATH"
fi

INSTALL_PATH=${INSTALL_PATH%/}
check_dependency
TMP_DATA_FILE=$(mktemp "$TMP_DATA_FILE")
log_output "Getting agent installer details..."
SUB_URL=$([ "$AGENT_ID" != "" ] && echo "/agents/$AGENT_ID" || echo "")
RET=$(call_url -s $PROXY -w "%{http_code}" -H "Content-Type: application/json" "$API_URL/orgs/$ORG_TOKEN$SUB_URL/agentVersion" -o "$TMP_DATA_FILE" 2>&1)

if [[ $? -ne 0 || "$RET" != "200" ]] ; then
    log_output "Error: Failed to get agent installer details; $RET" 2
    rm -f "$TMP_DATA_FILE"
    exit 117
fi

VERSION=$(grep '"agentVersion"\s*:\s*"[^"]*"' "$TMP_DATA_FILE" -o | sed 's/"agentVersion"\s*:\s*"\([^"]*\)"/\1/')
MAJOR_VERSION=$(echo $VERSION | grep '^[0-9]\+' -o)
TAR_DOWNLOAD_URL=$(grep '"agentDownloadURL"\s*:\s*"[^"]*"' "$TMP_DATA_FILE" -o | sed 's/"agentDownloadURL"\s*:\s*"\([^"]*\)"/\1/')

if [ $MAJOR_VERSION -le 2 ] ; then
    call_url -s $PROXY "$DOWNLOAD_URL/curl-install-node.sh" 2>/dev/null | bash /dev/stdin "$@" -t $TAR_DOWNLOAD_URL 1> >( read_and_log ) 2> >( read_and_log 2 )
    RET=$?
    rm -f "$TMP_DATA_FILE"
    sleep 2

    if [[ "$AGENT_ID" != "" && $RET -ne 0 ]] ; then
        report_failure $RET
    fi

    exit $RET
fi

rm -f "$TMP_DATA_FILE"
TMP_FILE_PATH=$(mktemp -d "$TMP_FILE_PATH")
TMP_FILE_PATH=${TMP_FILE_PATH%/}
TMP_FILE_NAME="$TMP_FILE_PATH/sealion-agent.tar.gz"
log_output "Downloading agent installer version $VERSION..."
RET=$(call_url -s $PROXY -w "%{http_code}" $TAR_DOWNLOAD_URL -o "$TMP_FILE_NAME" 2>&1)

if [[ $? -ne 0 || "$RET" == "404" ]] ; then
    log_output "Error: Failed to download agent installer; $RET" 2

    if [ "$RET" == "404" ] ; then
        report_failure 5
    fi
    
    if [[ -f "$INSTALL_PATH/bin/sealion-node" && -f "$INSTALL_PATH/etc/sealion" ]] ; then
        "$INSTALL_PATH/etc/sealion" start
    fi

    rm -rf "$TMP_FILE_PATH"
    exit 117
fi

RET=$(tar -xf "$TMP_FILE_NAME" --directory="$TMP_FILE_PATH" 2>&1)

if [ $? -ne 0 ] ; then
    log_output "Error: Failed to extract files; $RET" 2
    rm -rf "$TMP_FILE_PATH"
    exit 1
fi

bash "$TMP_FILE_PATH/sealion-agent/install.sh" "$@" -r curl  1> >( read_and_log ) 2> >( read_and_log 2 )
RET=$?

if [[ "$AGENT_ID" != "" && $RET -ne 0 ]] ; then
    report_failure $RET
    rm -rf "$TMP_FILE_PATH"

    if [[ -f "$INSTALL_PATH/bin/sealion-node" && -f "$INSTALL_PATH/etc/sealion" ]] ; then
        "$INSTALL_PATH/etc/sealion" start
    fi

    exit 123
fi

rm -rf "$TMP_FILE_PATH"
exit 0

