#!/bin/bash

# variable initialization
COMPRESSED_FILE_NAME_i686=../../../release/sealion.com/sealion-agent-package_i686.tar.gz
COMPRESSED_FILE_NAME_x86_64=../../../release/sealion.com/sealion-agent-package_x86_64.tar.gz
FOLDER_PATH=*
IGNORE_FILE=../.tarignore
PACKAGE_FOLDER=sealion-agent-package
TAR_BUILD_PATH=tmp_build/$PACKAGE_FOLDER

# build 64-bit version first
mkdir -p $TAR_BUILD_PATH
cp -R ../../sealion-agent $TAR_BUILD_PATH
cp ./configure $TAR_BUILD_PATH

#URL changes for sealion.com
API_URL='https:\/\/api.sealion.com'
AGENT_URL='https:\/\/agent.sealion.com'
REGISTRATION_URL=$API_URL'\/agents'

sed 's/<registration-url>/'$REGISTRATION_URL'/' ./installer.in > $TAR_BUILD_PATH/installer.in

# make tmp directory
cd tmp_build

chmod +x $PACKAGE_FOLDER/configure

sed -i '6 s/<api-url>/'$API_URL'/;12 s/<socket-io-url>/'$API_URL'/' $PACKAGE_FOLDER/sealion-agent/etc/config/sealion-config.json
sed -i 's/<download-agent-url>/'$AGENT_URL'/' $PACKAGE_FOLDER/sealion-agent/etc/update.sh
sed -i 's/<api-url>/'$API_URL'/' $PACKAGE_FOLDER/sealion-agent/uninstall.sh

# compress file
echo "Sealion Packager: Compressing file..."
    tar -czf $COMPRESSED_FILE_NAME_x86_64 $FOLDER_PATH -X $IGNORE_FILE --exclude-vcs --exclude-backups
echo "Sealion Packager: File successfully compressed"

echo "Sealion Packager 64-bit: Done!!!"

cp -R ../../../sealion-agent-ia32/* $PACKAGE_FOLDER/sealion-agent/
sed -i '0,/BINARY_PLATFORM="x86_64"/{s/BINARY_PLATFORM="x86_64"/BINARY_PLATFORM="i686"/}' $PACKAGE_FOLDER/configure

#compress 32-bit file
echo "Sealion Packager: Compressing file..."
    tar -czf $COMPRESSED_FILE_NAME_i686 $FOLDER_PATH -X $IGNORE_FILE --exclude-vcs --exclude-backups
echo "Sealion Packager: File successfully compressed"
echo "Sealion Packager 32-bit: Done!!!"

cd ../
rm -rf tmp_build
