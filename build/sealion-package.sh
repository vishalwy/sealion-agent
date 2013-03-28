#!/bin/bash

# variable initialization
VERSION="-v"`cat version`
COMPRESSED_FILE_NAME=tmp/sealion-agent.tar.gz
COMPRESSED_FILE_FOLDER=tmp/
FOLDER_PATH=../sealion-agent/
OUTPUT_FILE=../release/sealion-agent$VERSION.sh
INSTALLER_FILE=sealion-install.sh.in
IGNORE_FILE=.tarignore
TAG_NAME="SEALION_TARFILE:"

# make tmp directory
mkdir -p tmp

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
    rm -r $COMPRESSED_FILE_FOLDER
    echo "Sealion Packager: Temprory files deleted"
echo "Sealion Packager: Done!!!"
