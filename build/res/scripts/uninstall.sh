#!/usr/bin/env bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[ $? -eq 127 ] && exit 127' ERR  #exit in case command not found

#directory of the script
BASEDIR=$(readlink -f "$0")
BASEDIR=${BASEDIR%/*}

USER_NAME="sealion"  #username for the agent
cd "$BASEDIR"  #move to the script base dir so that all paths can be found

#validate current user
if [[ "$(id -u -n)" != "$USER_NAME" && $EUID -ne 0 ]] ; then
    echo "Error: You need to run this script as either root or $USER_NAME" >&2
    exit 1
fi

#use the service file to stop agent.
#service file may not be available if the user already removed the agent from the web interface
if [ -f "etc/init.d/sealion" ] ; then
    echo "Stopping agent..."
    etc/init.d/sealion stop
fi

#use unregister script to unregister the agent.
#the script may not be available if the user already removed the agent from the web interface
if [ -f "bin/unregister.py" ] ; then
    echo "Unregistering agent..."
    python bin/unregister.py >/dev/null 2>&1

    if [ $? -ne 0 ] ; then  #exit if unregistering the agent failed
        echo "Error: Failed to unregister agent" >&2
        exit 1
    fi
fi

#function to uninstall service
uninstall_service()
{
    #service file paths
    RC1_PATH=`find /etc/ -type d -name rc1.d`
    RC2_PATH=`find /etc/ -type d -name rc2.d`
    RC3_PATH=`find /etc/ -type d -name rc3.d`
    RC4_PATH=`find /etc/ -type d -name rc4.d`
    RC5_PATH=`find /etc/ -type d -name rc5.d`
    RC6_PATH=`find /etc/ -type d -name rc6.d`
    INIT_D_PATH=`find /etc/ -type d -name init.d`
    SYMLINK_PATHS=( K K S S S S K )

    RET=0

    #validate the paths
    if [[ -z $RC1_PATH || -z $RC2_PATH || -z $RC3_PATH || -z $RC4_PATH || -z $RC5_PATH || -z $RC6_PATH || -z $INIT_D_PATH ]] ; then
        echo "Error: Could not locate init.d/rc folders" >&2
        return 1
    else
        #remove all the service paths
        for (( i = 1 ; i < 7 ; i++ )) do
            VAR_NAME="RC"$i"_PATH"/${SYMLINK_PATHS[$i]}99sealion
            rm -f $VAR_NAME

            if [ $? -ne 0 ] ; then
                echo "Error: Failed to remove $VAR_NAME file" >&2
                RET=1
            fi
        done

        #remove service script
        rm -f $INIT_D_PATH/sealion
        
        if [ $? -ne 0 ] ; then
            echo "Error: Failed to remove $INIT_D_PATH/sealion file" >&2
            RET=1
        fi
    fi

    return $RET
}

if [[ $EUID -ne 0 ]]; then  #if not running as root user
    #we remove all the files except var/log and uninstall.sh. 
    #we wont be able to remove the user, group and service as it requires super privileges
    echo "Removing files except logs, README and uninstall.sh"
    find var -mindepth 1 -maxdepth 1 ! -name 'log' ! -name 'crash' -exec rm -rf {} \;
    find . -mindepth 1 -maxdepth 1 -type d ! -name 'var' -exec rm -rf {} \;
else
    #if install dir is the default install dir, then only we will remove user, group and service
    if [ "$BASEDIR" == "/usr/local/sealion-agent" ] ; then
        id $USER_NAME >/dev/null 2>&1

        #kill all the process and remove the user sealion
        if [ $? -eq 0 ] ; then
            pkill -KILL -u $USER_NAME
            userdel $USER_NAME
            echo "User $USER_NAME removed"
        fi

        id -g $USER_NAME >/dev/null 2>&1

        #remove the group
        if [ $? -eq 0 ] ; then
            groupdel $USER_NAME
            echo "Group $USER_NAME removed"
        fi

        uninstall_service  #uninstall the service

        if [ $? -ne 0 ] ; then
            echo "Service sealion removed"
        fi  
    fi

    echo "Removing files..."
    cd /
    rm -rf "$BASEDIR"
fi

echo "Sealion agent uninstalled successfully"
