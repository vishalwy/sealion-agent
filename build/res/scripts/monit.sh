#!/bin/bash

if [ "$#" != "2" ]; then
    exit 1
fi

BASEDIR=$(readlink -f "$0")
BASEDIR=$(dirname "$BASEDIR")
BASEDIR=${BASEDIR%/}
cd "$BASEDIR"
PID_FILE="../var/run/sealion.pid"
SERVICE_FILE="../etc/init.d/sealion"
LOG_FILE="../var/log/sealion.log"
ORIG_PID=$1
INTERVAL=$2

while true ; do
    sleep $INTERVAL
    PID=$(cat $PID_FILE 2>/dev/null)

    if [[ $? -ne 0 || "$PID" != "$ORIG_PID" ]] ; then
        exit 0
    fi

    if [ ! -d "/proc/$PID" ] ; then
        echo $(date +"%Y-%m-%d %T,000 CRITICAL ERROR - sealion got terminated; Resurrecting.") >>$LOG_FILE
        $SERVICE_FILE start
        exit 0
    fi
done
