#!/usr/bin/env bash

#This script is used to monitor SeaLion agent. It restarts the agent if it was killed.

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[ $? -eq 127 ] && exit 127' ERR  #exit in case command not found

if [ "$#" != "2" ]; then
    echo "Usage: $0 <PID> <Monit interval>"
    exit 1
fi

#change to base directory of the script
BASEDIR=$(readlink -f "$0")
BASEDIR=${BASEDIR%/*}
cd "$BASEDIR"

PID_FILE="../var/run/sealion.pid"  #pid file to be checked for
SERVICE_FILE="../etc/init.d/sealion"  #the service script to be used for restarting agent
LOG_FILE="../var/log/sealion.log"  #log file to be written
ORIG_PID=$1  #original pid of agent
INTERVAL=$2  #monitor interval

while true ; do
    #read the pid from pid file after monitor interval
    sleep $INTERVAL
    PID=$(cat $PID_FILE 2>/dev/null)

    #exit if pid file does not exist, or the pid is changed
    if [[ $? -ne 0 || "$PID" != "$ORIG_PID" ]] ; then
        exit 0
    fi

    #check the /proc to determine if the process exist, else restart the agent
    if [ ! -d "/proc/$PID" ] ; then
        echo $(date +"%F %T,%3N CRITICAL ERROR - sealion was terminated; Resurrecting.") >>$LOG_FILE
        $SERVICE_FILE start
        exit 0
    fi
done
