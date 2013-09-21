#! /bin/bash
FROM_AGENT=$1
SYMLINK_PATHS=( K K S S S S K )

clean_up()
{
    for (( i = 1 ; i < $1 ; i++ ))
    do
        rm -f /etc/rc$i.d/${SYMLINK_PATHS[$i]}20sealion
    done
}

get_JSON_value()
{
    if [ $# -eq 0 ] ; then
        return 1
    fi

    JSON=$@
    agent_id=`echo $JSON | sed 's/^.*"agentId":"\([^"]*\)".*$/\1/'`
    org_token=`echo $JSON | sed 's/^.*"orgToken":"\([^"]*\)".*$/\1/'`

    return 0
}

service sealion stop 2> /dev/null
sleep 5

if [ "$FROM_AGENT" != "-u" ] ; then
    JSON_STR=`cat /usr/local/sealion-agent/etc/config/agent-config.json`
    if [ $? -eq 0 ] ; then
        get_JSON_value $JSON_STR
        if [ -n $org_token -a -n $agent_id ] ; then
            DELETE_URL="<api-url>/orgs/"$org_token"/servers/"$agent_id
            curl -s -X DELETE $DELETE_URL
        fi
    fi
fi

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