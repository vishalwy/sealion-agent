#!/bin/bash

API_URL="<api-url>"
DOWNLOAD_URL="<agent-download-url>"
TMP_FILE_PATH=$(mktemp -d /tmp/sealion-agent.XXXX)
TMP_FILE_PATH=${TMP_FILE_PATH%/}
TMP_FILE_NAME="$TMP_FILE_PATH/sealion-agent.tar.gz"
PROXY=
AGENT_ID=
ORG_TOKEN=

while getopts :x:a: OPT ; do
    case "$OPT" in
        x)
            PROXY="-x '$OPTARG'"
            ;;
        a)
            AGENT_ID=$OPTARG
            ;;
        o)
            ORG_TOKEN=$OPTARG
            ;;
        \?)
            ;;
        :)
            ;;
    esac
done

echo "Downloading agent installer..."
curl -s $PROXY $DOWNLOAD_URL -o $TMP_FILE_NAME >/dev/null 2>&1

if [ $? -ne 0 ] ; then
    echo "Error: Failed to download agent installer." >&2
    rm -rf $TMP_FILE_PATH
    exit 117
fi

tar -xf $TMP_FILE_NAME --directory="$TMP_FILE_PATH" >/dev/null 2>&1

if [ $? -ne 0 ] ; then
    echo "Error: Failed to extract files." >&2
    rm -rf $TMP_FILE_PATH
    exit 1
fi

$TMP_FILE_PATH/sealion-agent/install.sh "$@"
RET=$?

if [[ "$AGENT_ID" != "" && $RET -gt 0 && $RET -lt 4 ]] ; then
    RET=`curl -s PROXY -w "%{http_code}" -H "Content-Type: application/json" -X PUT -d "{\"reason\":\"$RET\"}"  "$API_URL/orgs/$ORG_TOKEN/agents/$AGENT_ID/updatefail" >/dev/null 2>&1`
    rm -rf $TMP_FILE_PATH
    exit 123
fi

rm -rf $TMP_FILE_PATH
exit 0

