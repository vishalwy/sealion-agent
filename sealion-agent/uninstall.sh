#! /bin/bash
FROM_AGENT=$1
SYMLINK_PATHS=( K K S S S S K )
PROXY_FILE_PATH=/usr/local/sealion-agent/etc/config/proxy.json
PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin

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

if [ "$FROM_AGENT" != "-u" ] ; then

    if [[ $EUID != 0 ]] ; then
        echo "SeaLion agent un-installation requires super privilege." >&2
        exit 116
    fi

    /usr/local/sealion-agent/etc/sealion stop 2> /dev/null
    sleep 5

    JSON_STR=`cat /usr/local/sealion-agent/etc/config/agent-config.json`
    if [ $? -eq 0 ] ; then
        get_JSON_value $JSON_STR

        CURL_PROXY_VARIABLE=

        if [ -f $PROXY_FILE_PATH ] ; then
            JSON_STR=`cat $PROXY_FILE_PATH`
            HTTPPROXY=`echo $JSON_STR | sed 's/^.*"http_proxy"\s*:\s*"\([^"]*\)".*$/\1/'`
            if [ -n $HTTPPROXY ] ; then
                CURL_PROXY_VARIABLE="-x $HTTPPROXY"
            fi
        fi

        if [ -n $org_token -a -n $agent_id ] ; then
            DELETE_URL="<api-url>/orgs/"$org_token"/servers/"$agent_id
            curl -s $CURL_PROXY_VARIABLE -X DELETE $DELETE_URL
        fi
    fi

    echo "SeaLion Agent: Removing initialization files"

        RC1_PATH=`find /etc/ -type d -name rc1.d`
        RC2_PATH=`find /etc/ -type d -name rc2.d`
        RC3_PATH=`find /etc/ -type d -name rc3.d`
        RC4_PATH=`find /etc/ -type d -name rc4.d`
        RC5_PATH=`find /etc/ -type d -name rc5.d`
        RC6_PATH=`find /etc/ -type d -name rc6.d`
        INIT_D_PATH=`find /etc/ -type d -name init.d`

        if [[ -z $RC1_PATH || -z $RC2_PATH || -z $RC3_PATH || -z $RC4_PATH || -z $RC5_PATH || -z $RC6_PATH || -z $INIT_D_PATH ]] ; then
                echo "Error: Could not locate init.d/rc folders" >&2
        else
            for (( i = 1 ; i < 7 ; i++ ))
            do
                VAR_NAME="RC"$i"_PATH"/${SYMLINK_PATHS[$i]}99sealion
                rm -f $VAR_NAME
                if [ $? -ne 0 ] ; then
                    echo "SeaLion Agent: Failed to remove $VAR_NAME file"
                fi
            done

            rm -f $INIT_D_PATH/sealion
            if [ $? -ne 0 ] ; then
                echo "SeaLion Agent: Failed to remove $INIT_D_PATH/sealion file"
            else
                echo "SeaLion Agent: Initialization file removed"
            fi
        fi

    echo "SeaLion Agent: Removing sealion group and user"
        pkill -KILL -u sealion
        userdel sealion
        groupdel sealion
else
    /usr/local/sealion-agent/etc/sealion stop 2> /dev/null
    sleep 5
fi

echo "SeaLion Agent: Removing files"
    rm -rf /usr/local/sealion-agent
    if [ $? -ne 0 ] ; then
        echo "SeaLion Agent: Unable to remove files"
    else
        echo "SeaLion Agent: Files successfully removed"
    fi
