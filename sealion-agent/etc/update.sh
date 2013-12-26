#! /bin/bash

sleep 5
echo "Downloading update script..."

CURL_PROXY_VARIABLE=

if [[ "$7" == "-x" ]] ; then
    CURL_PROXY_VARIABLE="$7 $8"
fi

curl -s $CURL_PROXY_VARIABLE <download-agent-url> | bash /dev/stdin $@
if [ $? -ne 0 ] ; then
    echo "Service can't be updated" >&2
    exit 1
else
    echo "Service updated successfully" >&1
fi