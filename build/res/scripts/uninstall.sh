#!/bin/bash

BASEDIR=$(readlink -f "$0")
BASEDIR=$(dirname "$BASEDIR")
BASEDIR=${BASEDIR%/}
USER_NAME="sealion"
cd "$BASEDIR"

if [[ "$(id -u -n)" != "$USER_NAME" && $EUID -ne 0 ]] ; then
    echo "Error: You need to run this script as either root or $USER_NAME" >&2
    exit 1
fi

if [ -f "etc/init.d/sealion" ] ; then
    echo "Stopping agent..."
    etc/init.d/sealion stop
fi

if [ -f "src/unregister.py" ] ; then
    echo "Unregistering agent..."
    python src/unregister.py >/dev/null 2>&1

    if [ $? -ne 0 ] ; then
        echo "Error: Failed to unregister agent." >&2
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
        echo "Error: Could not locate init.d/rc folders" >&2
        return 1
    else
        for (( i = 1 ; i < 7 ; i++ )) do
            VAR_NAME="RC"$i"_PATH"/${SYMLINK_PATHS[$i]}99sealion
            rm -f $VAR_NAME

            if [ $? -ne 0 ] ; then
                echo "Error: Failed to remove $VAR_NAME file." >&2
                RET=1
            fi
        done

        rm -f $INIT_D_PATH/sealion
        
        if [ $? -ne 0 ] ; then
            echo "Error: Failed to remove $INIT_D_PATH/sealion file." >&2
            RET=1
        fi
    fi

    return $RET
}

if [[ $EUID -ne 0 ]]; then
    echo "Removing files except logs and uninstall.sh."
    find var -mindepth 1 -maxdepth 1 -type d ! -name 'log' -exec rm -rf {} \;
    find . -mindepth 1 -maxdepth 1 -type d ! -name 'var' -exec rm -rf {} \;
else
    if [ "$BASEDIR" == "/usr/local/sealion-agent" ] ; then
        id $USER_NAME >/dev/null 2>&1

        if [ $? -eq 0 ] ; then
            pkill -KILL -u $USER_NAME
            userdel $USER_NAME
            echo "User $USER_NAME removed."
        fi

        id -g $USER_NAME >/dev/null 2>&1

        if [ $? -eq 0 ] ; then
            groupdel $USER_NAME
            echo "Group $USER_NAME removed."
        fi

        uninstall_service

        if [ $? -ne 0 ] ; then
            echo "Service sealion removed."
        fi  
    fi

    echo "Removing files..."
    cd /
    rm -rf "$BASEDIR"
fi

echo "Sealion agent uninstalled successfully."
