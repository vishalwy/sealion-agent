#!/bin/bash

# variable initialization
compressedFileName=tmp/Sealion-agent.tar.gz
compressedFileFolder=tmp/
folderPath=../sealion/
outputFile=../Release/SealionAgent.sh
installerFile=sealion_install.sh.in
ignoreFile=.tarignore

# make tmp directory
mkdir -p tmp

# compress file
echo "Sealion Packager: Compressing file..."
    tar -czf $compressedFileName $folderPath -X $ignoreFile --exclude-vcs --exclude-backups
echo "Sealion Packager: File successfully compressed"

echo "Sealion Packager: Generating installer..."
    sed \
        -e 's/binary=./binary=1/'\
            $installerFile >$outputFile
    echo "SEALION_TARFILE:" >>$outputFile
    cat $compressedFileName >>$outputFile
echo "Sealion Packager: Installer generated"

# delete tmp files
echo "Sealion Packager: Deleting temperory files..."
    rm -r $compressedFileFolder
    echo "Sealion Packager: Temprory files deleted"
echo "Sealion Packager: Done!!!"
