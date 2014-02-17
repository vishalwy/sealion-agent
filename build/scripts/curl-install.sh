#!/bin/bash

DOWNLOAD_URL="<agent-download-url>"
TMP_FILE_PATH=$(mktemp -d /tmp/sealion-agent.XXXX)
TMP_FILE_PATH=${TMP_FILE_PATH%/}
TMP_FILE_NAME="$TMP_FILE_PATH/sealion-agent.tar.gz"
PROXY_HTTP=$http_proxy
PROXY_HTTPS=$https_proxy
PROXY_IGNORE=$no_proxy
CURL_PROXY=$PROXY_HTTPS

if [ $CURL_PROXY == "" ]

echo "Downloading agent installer"
curl -s $DOWNLOAD_URL -o $TMP_FILE_NAME >/dev/null 2>&1

if [ $? -ne 0 ] ; then
    echo "Error: Failed to download agent installer" >&2
    exit 117
fi

tar -xf $TMP_FILE_NAME --directory="$TMP_FILE_PATH/" >/dev/null 2>&1

if [ $? -ne 0 ] ; then
    echo "Error: Failed to extract files" >&2
    exit 1
fi

$TMP_FILE_PATH/sealion-agent/install.sh "$@" -x "$PROXY"


if [[ $CMD_LINE_HAS_PROXY -eq 0 && "$PROXY" != "" ]] ; then
    $TMP_FILE_PATH/sealion-agent/install.sh "$@" -x "$PROXY"
else
    $TMP_FILE_PATH/sealion-agent/install.sh "$@" 
fi

