#!/usr/bin/env bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

#config variables
API_URL="<api-url>"
DOWNLOAD_URL="<agent-download-url>"

USAGE="Usage: curl -s $DOWNLOAD_URL | sudo bash /dev/stdin {-o <Organization token> [-c <Category name>] [-H <Host name>] [-x <Proxy address>] [-p <Python binary>] | -h for Help}"
USER_NAME="sealion"  #username for the agent
ORIG_URL_CALLER=$([ "$URL_CALLER" != "" ] && echo "$URL_CALLER" || echo "curl")  #command for api url calls
unset -v URL_CALLER  #reset url caller so that child scripts wont inherit it

#setup variables
INSTALL_PATH="/usr/local/sealion-agent"  #install directory for the agent
TMP_FILE_PATH="/tmp/sealion-agent.XXXX"  #template for the path where the agent installer will be downloaded
TMP_DATA_FILE="/tmp/sealion-agent.response.XXXX"  #temp file for api url response
PROXY=
AGENT_ID=
ORG_TOKEN=

#function to call api url using the url caller
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

#function to log the output in terminal as well as a file 
log_output()
{
    OUTPUT=
    STREAM=1
    ST="O"

    #set the variables based on the stream given
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

    #write to output/error stream
    if [ $STREAM -eq 2 ] ; then
        echo $OUTPUT >&2
        ST="E"
    else
        echo $OUTPUT >&1
    fi

    #if file path is not set, then it is the first time the function is called
    if [ "$UPDATE_LOG_FILE" == "" ] ; then
        #set the destination based on the existence of the update.log file
        DEST=$([ -f "$INSTALL_PATH/var/log/update.log" ] && echo "$INSTALL_PATH/var/log/update.log" || echo "$INSTALL_PATH/var/log")

        #if current user is sealion and destination is writable, then set the variable otherwise set the variable to a space
        if [[ "$(id -u -n)" == "$USER_NAME" && -w "$DEST" ]] ; then
            UPDATE_LOG_FILE="$INSTALL_PATH/var/log/update.log"
        else
            UPDATE_LOG_FILE=" "
        fi
    fi

    #write to the log file
    if [ "$UPDATE_LOG_FILE" != " " ] ; then
        echo $(date +"%F %T,%3N - $ST: $OUTPUT") >>"$UPDATE_LOG_FILE"
    fi

    return 0  #success
}

#function to continuously read from the input and log
read_and_log()
{
    OUTPUT_STREAM=1

    if [ "$1" == "2" ] ; then
        OUTPUT_STREAM=2
    fi

    #blocking read without a timeout
    while read -t 300 line; do 
        log_output "${line}" $OUTPUT_STREAM 
    done
}

#function to report failure reason so that server can send a mail to the user
report_failure()
{
    call_url -s $PROXY -H "Content-Type: application/json" -X PUT -d "{\"reason\":\"$1\"}"  "$API_URL/orgs/$ORG_TOKEN/agents/$AGENT_ID/updatefail" >/dev/null 2>&1
}

#function to perform command dependency check
check_dependency()
{
    #various commands required for installer and the agent
    WHICH_COMMANDS=("sed" "tar" "bash" "grep" "mktemp")
    MISSING_COMMANDS=()  #array to hold missing commands
    PADDING="      "  #padding for messages

    #loop through the commands and find the missing commands
    for COMMAND in "${WHICH_COMMANDS[@]}" ; do
        if [ "$(type -P $COMMAND 2>/dev/null)" == "" ] ; then
            MISSING_COMMANDS=(${MISSING_COMMANDS[@]} "$PADDING Cannot locate command '$COMMAND'")
        fi
    done

    #print out and exit if there are any commands missing
    if [ "${#MISSING_COMMANDS[@]}" != "0" ] ; then
        OUTPUT=$(echo -e "Error: Command dependency check failed\n$(IFS=$'\n'; echo "${MISSING_COMMANDS[*]}")")
        log_output "$OUTPUT" 2

        if [ "$AGENT_ID" != "" ] ; then
            report_failure 6
        fi
        
        exit 123
    fi
}

#parse command line options
while getopts :i:o:c:H:x:p:a:r:v:e:h OPT ; do
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

#set the install path
INSTALL_PATH=$(eval echo "$INSTALL_PATH")  #evaluate the path to resolve symbols like ~
INSTALL_PATH=$([[ "$INSTALL_PATH" != "" && ${INSTALL_PATH:0:1} != "/" ]] && echo "$(pwd)/$INSTALL_PATH" || echo "$INSTALL_PATH")  #absolute path
INSTALL_PATH=${INSTALL_PATH%/}  #remove / from the end

check_dependency  #perform command dependency check
TMP_DATA_FILE=$(mktemp "$TMP_DATA_FILE")  #create temp data file for api response
log_output "Getting agent installer details..."
SUB_URL=$([ "$AGENT_ID" != "" ] && echo "/agents/$AGENT_ID" || echo "")  #we need to include agent id also if this is an update

#call the url and get the response
RET=$(call_url -s $PROXY -w "%{http_code}" -H "Content-Type: application/json" "$API_URL/orgs/$ORG_TOKEN$SUB_URL/agentVersion" -o "$TMP_DATA_FILE" 2>&1)

#check the return value and status code
if [[ $? -ne 0 || "$RET" != "200" ]] ; then
    log_output "Error: Failed to get agent installer details; $RET" 2
    rm -f "$TMP_DATA_FILE"
    exit 117
fi

#read the agent version from the response and find the major version
VERSION=$(grep '"agentVersion"\s*:\s*"[^"]*"' "$TMP_DATA_FILE" -o | sed 's/"agentVersion"\s*:\s*"\([^"]*\)"/\1/')
MAJOR_VERSION=$(echo $VERSION | grep '^[0-9]\+' -o)

#read the download url from the response
TAR_DOWNLOAD_URL=$(grep '"agentDownloadURL"\s*:\s*"[^"]*"' "$TMP_DATA_FILE" -o | sed 's/"agentDownloadURL"\s*:\s*"\([^"]*\)"/\1/')

rm -f "$TMP_DATA_FILE"  #we no longer require it

#if the major version is less than 2, means it requesting for node agent
if [ $MAJOR_VERSION -le 2 ] ; then
    call_url -s $PROXY "$DOWNLOAD_URL/curl-install-node.sh" 2>/dev/null | bash /dev/stdin "$@" -t $TAR_DOWNLOAD_URL 1> >( read_and_log ) 2> >( read_and_log 2 )
    RET=$?
    sleep 2

    if [[ "$AGENT_ID" != "" && $RET -ne 0 ]] ; then
        report_failure $RET
    fi

    exit $RET
fi

#create directory for downloading agent installer
TMP_FILE_PATH=$(mktemp -d "$TMP_FILE_PATH")
TMP_FILE_PATH=${TMP_FILE_PATH%/}
TMP_FILE_NAME="$TMP_FILE_PATH/sealion-agent.tar.gz"

log_output "Downloading agent installer version $VERSION..."
RET=$(call_url -s $PROXY -w "%{http_code}" $TAR_DOWNLOAD_URL -o "$TMP_FILE_NAME" 2>&1)

#check return value and status code
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

#extract the agent installer tar
RET=$(tar -xf "$TMP_FILE_NAME" --directory="$TMP_FILE_PATH" 2>&1)

#check for tar extract failure 
if [ $? -ne 0 ] ; then
    log_output "Error: Failed to extract files; $RET" 2
    rm -rf "$TMP_FILE_PATH"
    exit 1
fi

#execute the installer script; be sure to call it via bash to avoid getting permission denied on temp folder where script execution is not allowed
bash "$TMP_FILE_PATH/sealion-agent/install.sh" "$@" -r curl  1> >( read_and_log ) 2> >( read_and_log 2 )
RET=$?
rm -rf "$TMP_FILE_PATH"  #remove temp file as we no longer need them

#check for failure and report any error
if [[ "$AGENT_ID" != "" && $RET -ne 0 ]] ; then
    report_failure $RET

    if [[ -f "$INSTALL_PATH/bin/sealion-node" && -f "$INSTALL_PATH/etc/sealion" ]] ; then
        "$INSTALL_PATH/etc/sealion" start
    fi

    exit 123
fi

exit 0

