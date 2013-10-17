#!/bin/bash

# variable initialization
COMPRESSED_FILE_NAME_i686=../../../release/sealion.com/sealion-agent-package_i686.tar.gz
COMPRESSED_FILE_NAME_x86_64=../../../release/sealion.com/sealion-agent-package_x86_64.tar.gz
FOLDER_PATH=*
IGNORE_FILE=../.tarignore

# build 64-bit version first
mkdir -p tmp_build/sealion-agent-package_x86_64
cp -R ../../sealion-agent tmp_build/sealion-agent-package_x86_64
cp ./configure tmp_build/sealion-agent-package_x86_64

#URL changes for sealion.com
API_URL='https:\/\/api.sealion.com'
AGENT_URL='https:\/\/agent.sealion.com'
REGISTRATION_URL=$API_URL'\/agents'

sed 's/<registration-url>/'$REGISTRATION_URL'/' ./Makefile.in > tmp_build/sealion-agent-package_x86_64/Makefile.in

# make tmp directory
cd tmp_build

chmod +x ./sealion-agent-package_x86_64/configure

sed -i '6 s/<api-url>/'$API_URL'/;12 s/<socket-io-url>/'$API_URL'/' ./sealion-agent-package_x86_64/sealion-agent/etc/config/sealion-config.json
sed -i 's/<download-agent-url>/'$AGENT_URL'/' ./sealion-agent-package_x86_64/sealion-agent/etc/update.sh
sed -i 's/<api-url>/'$API_URL'/' ./sealion-agent-package_x86_64/sealion-agent/uninstall.sh

# compress file
echo "Sealion Packager: Compressing file..."
    tar -czf $COMPRESSED_FILE_NAME_x86_64 $FOLDER_PATH -X $IGNORE_FILE --exclude-vcs --exclude-backups
echo "Sealion Packager: File successfully compressed"

echo "Sealion Packager 64-bit: Done!!!"

# build 64-bit version first
#cd ../../

#cp -R ../sealion-agent-ia32/* tmp_build/sealion-agent/

#cd tmp_build/sealion-agent
# compress file
#echo "Sealion Packager: Compressing file..."
#    tar -czf $COMPRESSED_FILE_NAME_i686 $FOLDER_PATH -X $IGNORE_FILE --exclude-vcs --exclude-backups
#echo "Sealion Packager: File successfully compressed"

cd ../
rm -r tmp_build

#echo "Sealion Packager 32-bit: Done!!!"
