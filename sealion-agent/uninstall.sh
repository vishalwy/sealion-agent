sudo service sealion stop 2> /dev/null

echo "Sealion Agent: Removing initialization files"
    sudo update-rc.d -f sealion remove 2> /dev/null 1>/dev/null
    if [ $? -ne 0 ] ; then
        echo "Sealion Agent: init.d links not removed"
    else
        echo "Sealion Agent: init.d links removed"
    fi
    
    sudo rm -f /etc/init.d/sealion
    if [ $? -ne 0 ] ; then
        echo "Sealion Agent: Failed to remove initialization file"
    else
        echo "Sealion Agent: Initialization file removed"
    fi

echo "Sealion Agent: Removing files"
    sudo rm -rf /usr/local/sealion-agent
    if [ $? -ne 0 ] ; then
        echo "Sealion Agent: Unable to remove files"
    else
        echo "Sealion Agent: Files successfully removed"
    fi
