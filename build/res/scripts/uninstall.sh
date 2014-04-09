#!/bin/bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

BASEDIR=$(readlink -f "$0")
BASEDIR=$(dirname "$BASEDIR")
BASEDIR=${BASEDIR%/}
USER_NAME="sealion"

log_output()
{
    OUTPUT=
    STREAM=1
    ST="O"

    case "$#" in
        "1")
            OUTPUT=$1
            ;;
        "2")
            OUTPUT=$1
            STREAM=$2
            ;;
    esac

    if [ "$OUTPUT" == "" ] ; then
        return 1
    fi

    if [ $STREAM -eq 2 ] ; then
        echo $OUTPUT >&2
        ST="E"
    else
        echo $OUTPUT >&1
    fi

    if [ "$UPDATE_LOG_FILE" == "" ] ; then
        if [ -w "var/log" ] ; then
            UPDATE_LOG_FILE="var/log/update.log"
        else
            UPDATE_LOG_FILE=" "
        fi
    fi

    if [ "$UPDATE_LOG_FILE" != " " ] ; then
        echo $(date +"%F %T,%3N - $ST: $OUTPUT") >>"$UPDATE_LOG_FILE"
    fi

    return 0
}

cd "$BASEDIR"
trap "kill -9 0 >/dev/null 2>&1" EXIT

if [[ "$(id -u -n)" != "$USER_NAME" && $EUID -ne 0 ]] ; then
    echo "Error: You need to run this script as either root or $USER_NAME" >&2
    exit 1
fi

if [ -f "etc/init.d/sealion" ] ; then
    log_output "Stopping agent..."
    etc/init.d/sealion stop 1> >( while read line; do log_output "${line}"; done ) 2> >( while read line; do log_output "${line}" 2; done )
fi

if [ -f "src/unregister.py" ] ; then
    log_output "Unregistering agent..."
    python src/unregister.py >/dev/null 2>&1

    if [ $? -ne 0 ] ; then
        log_output "Error: Failed to unregister agent" 2
        exit 1
    fi
fi

uninstall_service()
{
    RC1_PATH=`find /etc/ -type d -name rc1.d`
    RC2_PATH=`find /etc/ -type d -name rc2.d`
    RC3_PATH=`find /etc/ -type d -name rc3.d`
    RC4_PATH=`find /etc/ -type d -name rc4.d`
    RC5_PATH=`find /etc/ -type d -name rc5.d`
    RC6_PATH=`find /etc/ -type d -name rc6.d`
    INIT_D_PATH=`find /etc/ -type d -name init.d`
    SYMLINK_PATHS=( K K S S S S K )
    RET=0

    if [[ -z $RC1_PATH || -z $RC2_PATH || -z $RC3_PATH || -z $RC4_PATH || -z $RC5_PATH || -z $RC6_PATH || -z $INIT_D_PATH ]] ; then
        log_output "Error: Could not locate init.d/rc folders" 2
        return 1
    else
        for (( i = 1 ; i < 7 ; i++ )) do
            VAR_NAME="RC"$i"_PATH"/${SYMLINK_PATHS[$i]}99sealion
            rm -f $VAR_NAME

            if [ $? -ne 0 ] ; then
                log_output "Error: Failed to remove $VAR_NAME file" 2
                RET=1
            fi
        done

        rm -f $INIT_D_PATH/sealion
        
        if [ $? -ne 0 ] ; then
            log_output "Error: Failed to remove $INIT_D_PATH/sealion file" 2
            RET=1
        fi
    fi

    return $RET
}

if [[ $EUID -ne 0 ]]; then
    log_output "Removing files except logs and uninstall.sh"
    find var -mindepth 1 -maxdepth 1 ! -name 'log' ! -name 'crash' -exec rm -rf {} \;
    find . -mindepth 1 -maxdepth 1 -type d ! -name 'var' -exec rm -rf {} \;
else
    if [ "$BASEDIR" == "/usr/local/sealion-agent" ] ; then
        id $USER_NAME >/dev/null 2>&1

        if [ $? -eq 0 ] ; then
            pkill -KILL -u $USER_NAME
            userdel $USER_NAME
            log_output "User $USER_NAME removed"
        fi

        id -g $USER_NAME >/dev/null 2>&1

        if [ $? -eq 0 ] ; then
            groupdel $USER_NAME
            log_output "Group $USER_NAME removed"
        fi

        uninstall_service

        if [ $? -ne 0 ] ; then
            log_output "Service sealion removed"
        fi  
    fi

    log_output "Removing files..."
    cd /
    rm -rf "$BASEDIR"
fi

log_output "Sealion agent uninstalled successfully"
