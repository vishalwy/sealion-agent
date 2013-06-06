#!/bin/bash

# variable initialization

VERSION="-v"`cat version`
COMPRESSED_FILE_NAME=../build/tmp/sealion-agent.tar.gz
COMPRESSED_FILE_FOLDER=../build/tmp/
FOLDER_PATH=*
OUTPUT_FILE=../release/sealion.sh
INSTALLER_FILE=../build/sealion.sh.in
IGNORE_FILE=../build/.tarignore
TAG_NAME="SEALION_TARFILE:"

# make tmp directory
mkdir -p tmp

cd ../sealion-agent

# compress file
echo "Sealion Packager: Compressing file..."
    tar -czf $COMPRESSED_FILE_NAME $FOLDER_PATH -X $IGNORE_FILE --exclude-vcs --exclude-backups
echo "Sealion Packager: File successfully compressed"

echo "Sealion Packager: Generating installer..."
    cat $INSTALLER_FILE >$OUTPUT_FILE
    echo $TAG_NAME >>$OUTPUT_FILE
    cat $COMPRESSED_FILE_NAME >>$OUTPUT_FILE
echo "Sealion Packager: Installer generated"

echo "Sealion Packager: Deleting temperory files..."
    rm -rf $COMPRESSED_FILE_FOLDER
    echo "Sealion Packager: Temprory files deleted"
echo "Sealion Packager: Done!!!"
