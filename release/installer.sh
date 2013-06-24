#!/bin/bash
args=$@
TMP_FILE_PATH=/tmp/sealion-agent
TMP_FILE_NAME=$TMP_FILE_PATH"/sealion-agent.tmp"

mkdir -p $TMP_FILE_PATH
if [ $? -ne 0 ] ; then
    echo "Sealion-Agent Error: Can't create temporary directory"
    exit 1
fi

echo "Downloading the binary..."
curl -# https://agent.sealion.com/sealion.sh -o $TMP_FILE_NAME
bash $TMP_FILE_NAME $args
