#!/bin/bash

BASEDIR=$(dirname $0)
BASEDIR=${BASEDIR%/}
BASEDIR="'$BASEDIR'"

if [ ! -f "$BASEDIR/sealion.py" ] ; then
    echo "Error: $BASEDIR is not a valid sealion directory"
    exit 1
fi

python $BASEDIR/sealion.py stop
python $BASEDIR/src/unregister.py

if [ $? -ne 0 ] ; then
    echo "Error: Failed to unregister agent"
    exit 1
fi

cd /
rm -rf $BASEDIR

if [ $? -ne 0 ] ; then
    echo "Error: Unable to remove files"
fi

