#!/bin/bash

BASEDIR=$(readlink -f "$0")
BASEDIR=$(dirname $BASEDIR)
BASEDIR=${BASEDIR%/}
PID_FILE="$BASEDIR/../var/run/sealion.pid"
SERVICE_FILE="$BASEDIR/../etc/init.d/sealion"
LOG_FILE="$BASEDIR/../var/log/sealion.log"
ORIG_PID=$1

while true ; do
    sleep 60

    PID=$(cat $PID_FILE)

    if [[ $? -ne 0 || "$PID" != "$ORIG_PID" ]] ; then
        exit 0
    fi

    if [ ! -d "/proc/$PID" ] ; then
        echo $(date +"%Y-%m-%d %T,000 CRITICAL ERROR - sealion got terminated; resurrecting") >>$LOG_FILE
        $SERVICE_FILE start
        exit 0
    fi
done
