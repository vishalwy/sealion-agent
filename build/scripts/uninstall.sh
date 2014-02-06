#!/bin/bash

BASEDIR=$(dirname $0)
BASEDIR=${BASEDIR%/}
BASEDIR="'$BASEDIR'"
USER_NAME="sealion"

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

    if [[ -z $RC1_PATH || -z $RC2_PATH || -z $RC3_PATH || -z $RC4_PATH || -z $RC5_PATH || -z $RC6_PATH || -z $INIT_D_PATH ]] ; then
            echo "Error: Could not locate init.d/rc folders" >&2
    else
        for (( i = 1 ; i < 7 ; i++ )) do
            VAR_NAME="RC"$i"_PATH"/${SYMLINK_PATHS[$i]}99sealion
            rm -f $VAR_NAME

            if [ $? -ne 0 ] ; then
                echo "Error: Failed to remove $VAR_NAME file"
            fi
        done

        rm -f $INIT_D_PATH/sealion
        
        if [ $? -ne 0 ] ; then
            echo "Error: Failed to remove $INIT_D_PATH/sealion file"
        fi
    fi
}

if [ "$BASEDIR" == "'/usr/local/sealion-agent'" ] ; then
    echo "Removing service"
    uninstall_service
fi

pkill -KILL -u $USER_NAME
userdel $USER_NAME
groupdel $USER_NAME

rm -rf $BASEDIR

if [ $? -ne 0 ] ; then
    echo "Error: Failed to remove files"
fi

