#! /bin/bash

sleep 5
echo "Downloading update script..."
curl -s https://agent-rituparna.sealion.com | bash /dev/stdin $1 $2 $3 $4 $5 $6
if [ $? -ne 0 ] ; then
    echo "Service can't be updated" >&2
    exit 1
else
    echo "Service updated successfully" >&1
fi
