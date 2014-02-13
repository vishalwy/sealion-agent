#!/bin/bash

DOWNLOAD_URL="<agent-download-url>"
TMP_FILE_PATH=$(mktemp -d /tmp/sealion-agent.XXXX)
TMP_FILE_PATH=${TMP_FILE_PATH%/}
TMP_FILE_NAME="$TMP_FILE_PATH/sealion-agent.tar.gz"

echo "Downloading agent installer"
curl $DOWNLOAD_URL -o $TMP_FILE_NAME

if [ $? -ne 0 ] ; then
    echo "Error: Failed to download agent installer" >&2
    exit 117
fi

tar -xf $TMP_FILE_NAME --directory="$TMP_FILE_PATH/"

if [ $? -ne 0 ] ; then
    echo "Error: Failed to extract files" >&2
    exit 1
fi

$TMP_FILE_PATH/sealion-agent/install.sh "$@"
    
