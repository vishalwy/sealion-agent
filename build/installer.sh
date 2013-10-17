#!/bin/bash

DOWNLOAD_URL="<base-agent-url>"
REGISTRATION_URL="<registration-url>"
PLATFORM=`uname -m`
TAR_FILE_URL="<tar-file-url>"$PLATFORM".tar.gz"

USAGE="Usage:\n curl -k "$DOWNLOAD_URL"| bash /dev/stdin -o <Organisation Token> \n\t [-H <Hostname>] \n\t [-c <category name>] \n\t [-h for help]"


TMP_FILE_PATH=`mktemp -d /tmp/sealion-agent.XXXX` || exit 1
TMP_FILE_NAME=$TMP_FILE_PATH"/sealion-agent.tar.gz"
TMP_DATA_NAME=$TMP_FILE_PATH"/sealion-data.tmp"

OPTERR=0

INIT_FILE=/usr/local/sealion-agent/etc/sealion
INSTALLATION_DIRECTORY=/usr/local/sealion-agent/
PROXY_FILE_PATH=/usr/local/sealion-agent/etc/config/proxy.json

USERNAME="sealion"
SYMLINK_PATHS=(K K S S S S K)
is_root=0


if [ "`uname -s`" != "Linux" ]; then
    echo "SeaLion agent works on Linux only" >&2
    exit 1
fi

if [[ "$PLATFORM" != "x86_64" && "$PLATFORM" != "i686" ]]; then
    echo "Platform not supported" >&2
    exit 1
fi

clean_up()
{
    for (( i = 1 ; i < $1 ; i++ )) 
    do
        rm -f /etc/rc$i.d/${SYMLINK_PATHS[$i]}20sealion
    done
    rm -rf $TMP_FILE_PATH
    rm -rf $INSTALLATION_DIRECTORY
}

get_JSON_value()
{
    if [ $# -eq 0 ] ; then
        return 1
    fi 
    
    JSON=$@
    
    version=`echo $JSON | sed 's/.*"agentVersion"\s*:\s*\([0-9\.]*\)[,}].*/\1/'` 
    agent_id=`echo $JSON | sed 's/.*"_id"\s*:\s*"\([0-9a-z]*\)"[,}].*/\1/'`
    already_registered=`echo $JSON | sed 's/.*"alreadyRegistered"\s*:\s*\(0\|1\)[,}].*/\1/'`
    
    return 0
}

while getopts a:o:c:v:hH: OPT ; do
    case "$OPT" in
        v)
            version=$OPTARG
        ;;
        a)
            agent_id=$OPTARG
        ;;
        H)
            host=$OPTARG
        ;;
        h)
            printf "$USAGE \n" >&1
            exit 0
        ;;
        o)
        if [ -z $org_token ] ; then
            org_token=$OPTARG
        fi
        ;;
        c)
            category=$OPTARG
        ;;
        \?)
            echo "Invalid argument -$OPTARG" >&2
            printf "$USAGE \n" >&2
            exit 126
        ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            printf "$USAGE \n" >&2
            exit 125
        ;;
    esac
done

if [ -z $org_token ] ; then
    echo "Error: No organization token found. Aborting" >&2
    printf "$USAGE \n" >&2
    exit 124
fi

echo "Downloading agent..."

if [ -z $agent_id ] ; then
    curl -# $TAR_FILE_URL -o $TMP_FILE_NAME
    if [ $? -ne 0 ] ; then
        echo "Error: Downloading source file failed" >&2
        exit 117
    fi
else
    curl -s $TAR_FILE_URL -o $TMP_FILE_NAME
    if [ $? -ne 0 ] ; then
        echo "Error: Downloading source file failed" >&2
        exit 117
    fi
fi

running=`pgrep sealion-node | wc -w`
if [ $running -gt 0 ] ; then
    echo "Trying to stop SeaLion service"
    $INIT_FILE stop
    sleep 3
fi

if [ -z $agent_id ] ; then

    if [ -z "$host" ] ; then
        host=$HOSTNAME  
    fi
    
    is_root=1    
        
    mkdir -p $INSTALLATION_DIRECTORY
    if [ $? -ne 0 ] ; then
        echo "Error: Directory creation failed!!!" >&2
        exit 118
    fi

    useradd -r -d $INSTALLATION_DIRECTORY $USERNAME 2> /dev/null
    tempVar=$?
    if [ $tempVar -ne 0 ] ; then
        if [ $tempVar -ne 9 ] ; then
            echo "Error: User 'sealion' creation failed!" >&2
            rm -r $INSTALLATION_DIRECTORY
            exit 1
        fi
    fi
    echo "Created 'sealion' user successfully" >&1
else
    if [ -z $version ] ; then 
        echo "Error: Agent-version not found"
        exit 121
    fi
fi    

echo "Extracting files to /usr/local/sealion-agent..." >&1
    
    tar -xzf $TMP_FILE_NAME -C $INSTALLATION_DIRECTORY --overwrite
    if [ $? -ne 0 ] ; then
        echo "Error: Installation failed" >&2
        if [ $is_root -eq 1 ] ; then
            userdel sealion
            rm -rf $INSTALLATION_DIRECTORY
            rm -rf $TMP_FILE_PATH
            if [ $? -ne 0 ] ; then
                echo "Error: Failed to delete temporary files" >&2
            fi
        fi
        exit 1
    fi

echo "Files extracted successfully" >&1
cd $INSTALLATION_DIRECTORY

if [ $is_root -eq 1 ] ; then
    chown -R $USERNAME:$USERNAME $INSTALLATION_DIRECTORY

    ln -sf $INIT_FILE /etc/init.d/sealion
    chmod +x $INIT_FILE
    chown -h $USERNAME:$USERNAME /etc/init.d/sealion

    for (( i = 1 ; i < 7 ; i++ )) 
    do
        ln -sf $INIT_FILE /etc/rc$i.d/${SYMLINK_PATHS[$i]}20sealion
        if [ $? -ne 0 ] ; then
            echo "Error: Unable to update init.d files. Aborting" >&2
            clean_up $i
            exit 1
        fi
        chown -h $USERNAME:$USERNAME /etc/rc$i.d/${SYMLINK_PATHS[$i]}20sealion
    done
    
    echo "Installed SeaLion as a service" >&1
fi

if [ -z $agent_id ] ; then
    if [ -z "$category" ] ; then
        return_code=`curl -s -w "%{http_code}" -H "Content-Type: application/json" -X POST -d "{\"orgToken\":\"$org_token\", \"name\":\"$host\"}"  $REGISTRATION_URL -o $TMP_DATA_NAME`
        if [[ $? -ne 0 || $return_code -ne 201 ]] ; then
            echo $return_code
            cat $TMP_DATA_NAME
            clean_up 6
            echo "Error: Registration failed. Aborting" >&2
            exit 123
        fi
    else
        return_code=`curl -s -w "%{http_code}" -H "Content-Type: application/json" -X POST -d "{\"orgToken\":\"$org_token\", \"name\":\"$host\", \"category\":\"$category\"}"  $REGISTRATION_URL -o $TMP_DATA_NAME`
        if [[ $? -ne 0 || $return_code -ne 201 ]] ; then
            clean_up 6
            echo "Error: Registration failed. Aborting" >&2
            exit 123
        fi
    fi
    
    dataJSON=`cat $TMP_DATA_NAME`
    
    get_JSON_value $dataJSON
    if [ $? -ne 0 ] ; then
        clean_up 6
        echo "Error: Failed to parse response. Aborting" >&2   
        exit 121
    fi
    
    if [ -z $version ] ; then
        clean_up 6
        echo "Error: 'agent-version' not present in response. Aborting" >&2
        exit 119
    fi    
    
    if [ -z $agent_id ] ; then
        clean_up 6
        echo "Error: 'agent-id' not present in response. Aborting" >&2
        exit 120
    fi
fi

echo "{ \"agentId\":\"$agent_id\" , \"agentVersion\":\"$version\" , \"orgToken\":\"$org_token\"}" > etc/config/agent-config.json

rm -rf $TMP_FILE_PATH
if [ $? -ne 0 ] ; then
    echo "Error: Failed to delete temporary files" >&2
fi

if [ -n $http_proxy ] ; then
    HTTPPROXY=$http_proxy
else
    if [ -n $HTTP_PROXY ] ;then
        HTTPPROXY=$HTTP_PROXY                
    fi
fi

if [[ -n $HTTPPROXY && ! -f $PROXY_FILE_PATH ]] ; then
        echo "{\"http_proxy\" : \"$HTTPPROXY\"}" > $PROXY_FILE_PATH    
fi

if [ $is_root -eq 1 ] ; then
    chown -R $USERNAME:$USERNAME etc/config
fi 

    
echo "Starting agent..." >&1
$INIT_FILE start
if [ $? -ne 0 ] ; then
    echo "Error: Service can not be started" >&2
    exit 1
else
    echo "Installation successful. Please continue on https://sealion.com" >&1
    exit 0
fi
