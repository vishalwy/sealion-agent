#!/bin/bash

# variable initialization
VERSION="-v"`cat version`
COMPRESSED_FILE_NAME=../release/sealion.com/sealion-agent.tar.gz
COMPRESSED_FILE_FOLDER=../release/sealion.com/
FOLDER_PATH=*
IGNORE_FILE=../build/.tarignore

# make tmp directory
cd ../sealion-agent

#URL changes for test.sealion.com
API_URL='https:\/\/api.sealion.com'
AGENT_DOWNLOAD_URL='https:\/\/s3.amazonaws.com\/sealion.com\/sealion-agent.tar.gz'
AGENT_URL='https:\/\/agent.sealion.com'
REGISTRATION_URL=$API_URL'\/agents'

sed 's/<base-agent-url>/'$AGENT_URL'/; s/<registration-url>/'$REGISTRATION_URL'/; s/<tar-file-url>/'$AGENT_DOWNLOAD_URL'/' ../build/installer.sh > ../release/sealion.com/installer.sh
sed -i '6 s/<api-url>/'$API_URL'/;12 s/<socket-io-url>/'$API_URL'/' ./etc/config/sealion-config.json
sed -i 's/<download-agent-url>/'$AGENT_URL'/' ./etc/update.sh
sed -i 's/<api-url>/'$API_URL'/' ./uninstall.sh

# compress file
echo "Sealion Packager: Compressing file..."
    tar -czf $COMPRESSED_FILE_NAME $FOLDER_PATH -X $IGNORE_FILE --exclude-vcs --exclude-backups
echo "Sealion Packager: File successfully compressed"

sed -i '6 s/'$API_URL'/<api-url>/;12 s/'$API_URL'/<socket-io-url>/' ./etc/config/sealion-config.json
sed -i 's/'$AGENT_URL'/<download-agent-url>/' ./etc/update.sh
sed -i 's/'$API_URL'/<api-url>/' ./uninstall.sh
echo "Sealion Packager: Done!!!"
