#!/bin/bash

# variable initialization
VERSION="-v"`cat version`
COMPRESSED_FILE_NAME=../build/tmp/sealion-agent.tar.gz
COMPRESSED_FILE_FOLDER=../build/tmp/
FOLDER_PATH=*
OUTPUT_FILE=../release/test.sealion.com/sealion.sh
INSTALLER_FILE=../build/sealion.sh.in
IGNORE_FILE=../build/.tarignore
TAG_NAME="SEALION_TARFILE:"


# make tmp directory
mkdir -p tmp

cd ../sealion-agent

#URL changes for test.sealion.com
API_URL='https:\/\/api-test.sealion.com'
AGENT_URL='https:\/\/agent-test.sealion.com'
REGISTRATION_URL='https:\/\/api-test.sealion.com\/agents'

sed 's/<base-agent-url>/'$AGENT_URL'/' ../release/installer.sh > ../release/test.sealion.com/installer.sh
sed -i 's/<registration-url>/'$REGISTRATION_URL'/' $INSTALLER_FILE
sed -i '6 s/<api-url>/'$API_URL'/;12 s/<socket-io-url>/'$API_URL'/' ./etc/config/sealion-config.json
sed -i 's/<base-agent-url>/'$AGENT_URL'/' ./etc/update.sh

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

sed -i 's/'$REGISTRATION_URL'/<registration-url>/' $INSTALLER_FILE
sed -i '6 s/'$API_URL'/<api-url>/;12 s/'$API_URL'/<socket-io-url>/' ./etc/config/sealion-config.json
sed -i 's/'$AGENT_URL'/<base-agent-url>/' ./etc/update.sh
