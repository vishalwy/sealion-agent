#!/bin/bash

DOWNLOAD_URL="<agent-download-url>"
TMP_FILE_PATH=$(mktemp -d /tmp/sealion-agent.XXXX)
TMP_FILE_PATH=${TMP_FILE_PATH%/}
TMP_FILE_NAME="$TMP_FILE_PATH/sealion-agent.tar.gz"
PROXY=

while getopts :i:o:c:H:x:p:h OPT ; do
    case "$OPT" in
        x)
            PROXY="-x '$OPTARG'"
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
    exit 117
fi

tar -xf $TMP_FILE_NAME --directory="$TMP_FILE_PATH" >/dev/null 2>&1

if [ $? -ne 0 ] ; then
    echo "Error: Failed to extract files." >&2
    exit 1
fi

$TMP_FILE_PATH/sealion-agent/install.sh "$@" 
rm -rf $TMP_FILE_PATH

