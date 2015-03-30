#!/usr/bin/env bash

#This script is used to monitor SeaLion agent. It restarts the agent if it was killed.

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found
PATH="${PATH}:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"  #common paths found in various linux distros

#get base directory of the script
script_base_dir=$(readlink -f "$0")
script_base_dir=${script_base_dir%/*}

if [ "$#" != "2" ] ; then
    echo "Usage: ${0} <Process ID> <Monit interval>"
    exit 1
fi

cd "$script_base_dir"  #change to base directory of the script
pid_file="../var/run/sealion.pid"  #pid file to be checked for
service_file="../etc/init.d/sealion"  #the service script to be used for restarting agent
log_file="../var/log/sealion.log"  #log file to be written
orig_pid=$1  #original pid of agent
interval=$2  #monitor interval

#infinate loop
while [[ 1 ]] ; do
    #read the pid from pid file after monitor interval
    sleep $interval
    pid=$(cat $pid_file 2>/dev/null)

    #exit if pid file does not exist, or the pid is changed
    if [[ $? -ne 0 || "$pid" != "$orig_pid" ]] ; then
        exit 0
    fi

    #check the /proc to determine if the process exist, else restart the agent
    if [ ! -d "/proc/$pid" ] ; then
        echo $(date +"%F %T,%3N CRITICAL ERROR - sealion was terminated; Resurrecting.") >>"$log_file"
        $service_file start
        exit 0
    fi
done
