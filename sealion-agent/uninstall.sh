#! /bin/bash
SYMLINK_PATHS=( K K S S S S K )
sleep 5
clean_up()
{
    for (( i = 0 ; i < $1 ; i++ )) 
    do
        rm -f /etc/rc$i.d/${SYMLINK_PATHS[$i]}20sealion
    done
}

service sealion stop 2> /dev/null

echo "Sealion Agent: Removing initialization files"
    clean_up 7
    
    rm -f /etc/init.d/sealion
    if [ $? -ne 0 ] ; then
        echo "Sealion Agent: Failed to remove initialization file"
    else
        echo "Sealion Agent: Initialization file removed"
    fi

echo "Sealion Agent: Removing files"
    rm -rf /usr/local/sealion-agent
    if [ $? -ne 0 ] ; then
        echo "Sealion Agent: Unable to remove files"
    else
        echo "Sealion Agent: Files successfully removed"
    fi