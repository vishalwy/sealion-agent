#!/bin/bash

# check platform compatibility
# check if linux
if [ "`uname -s`" != "Linux" ]; then
    echo "Error: SeaLion agent works on Linux only" >&2
    exit 1
fi

PLATFORM=`uname -m`
# check for platform architecture
if [[ "$PLATFORM" != "x86_64" && "$PLATFORM" != "i686" ]]; then
    echo "Error: Platform not supported" >&2
    exit 1
fi

# check for kernel version (min 2.6)
eval $(uname -r | awk -F'.' '{printf("KERNEL_VERSION=%s KERNEL_MAJOR=%s\n", $1, $2)}')
if [ $KERNEL_VERSION -le 2 ] ; then
    if [[ $KERNEL_VERSION -eq 1 || $KERNEL_MAJOR -lt 6 ]]; then
        echo "Error: SeaLion agent requires kernel 2.6 or above. Exiting" >&2
        exit 1
    fi
fi

# check for glibc version (min 2.4)
LIBCPATH="`find /lib*/ | grep libc.so.6 | head -1`"
if [ -z "$LIBCPATH" ]; then
    echo "Error: GLIBC_2.5 not found. Exiting"
    exit 1
else
    STRINGS="`which strings`"
    if [ -z "$STRINGS" ]; then
        echo "Error: strings command not available. Please install binutils package and try again."
        exit 1  
    fi
    LIBC25="`$STRINGS $LIBCPATH | grep 'GLIBC_2.5'`"
    if [ -z "$LIBC25" ]; then
        echo "Error: SeaLion agent requires GLIBC_2.5 or above. Exiting"
        exit 1
    fi
fi

DOWNLOAD_URL="<download url>"
REGISTRATION_URL="<registration url>"
TAR_FILE_URL=

while getopts a:t:o:x:c:v:hH: OPT ; do
    case "$OPT" in
        t)
            TAR_FILE_URL=$OPTARG
            ;;
    esac
done

TAR_FILE_URL=$(echo $TAR_FILE_URL | sed "s/PLATFORM/$PLATFORM/")
PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin

USAGE="Usage:\n curl -s "$DOWNLOAD_URL" | sudo bash /dev/stdin -o <Organisation Token> \n\t[-H <Hostname>] \n\t[-c <Category name>] \n\t[-x <Proxy address>] \n\t[-h for help]"

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

CURL_COMMAND_PROXY=

clean_up()
{
    for (( i = 1 ; i < $1 ; i++ )) 
    do
        VAR_NAME="RC"$i"_PATH"/${SYMLINK_PATHS[$i]}99sealion
        rm -f $VAR_NAME
    done
    
    rm -f $INIT_D_PATH/sealion
    rm -rf $TMP_FILE_PATH
    rm -rf $INSTALLATION_DIRECTORY
}

get_JSON_value()
{
    if [ $# -eq 0 ] ; then
        return 1
    fi 
    
    JSON=$@
    
    version=`echo $JSON | sed 's/.*"agentVersion"\s*:\s*"\?\([0-9\.]*\)"\?[,}].*/\1/'` 
    agent_id=`echo $JSON | sed 's/.*"_id"\s*:\s*"\([0-9a-z]*\)"[,}].*/\1/'`
    already_registered=`echo $JSON | sed 's/.*"alreadyRegistered"\s*:\s*\(0\|1\)[,}].*/\1/'`
    
    return 0
}

unset OPTIND

while getopts a:t:o:x:c:v:hH: OPT ; do
    case "$OPT" in
        v)
            version=$OPTARG
        ;;
        x)
            HTTPPROXY=$OPTARG
            CURL_COMMAND_PROXY="-x $HTTPPROXY"
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

if [[ $EUID != 0 && -z $agent_id ]] ; then
    echo "SeaLion agent installation requires super privilege" >&2
    echo -e "Usage:\n curl -s "$DOWNLOAD_URL" | sudo bash /dev/stdin -o $org_token \n\t[-H <Hostname>] \n\t[-c <Category name>] \n\t[-x <Proxy address>] \n\t[-h for help]"
    exit 116
fi

echo "Downloading agent..."


if [ -z $agent_id ] ; then
    curl -# $CURL_COMMAND_PROXY $TAR_FILE_URL -o $TMP_FILE_NAME
    if [ $? -ne 0 ] ; then
        echo "Error: Downloading source file failed" >&2
        exit 117
    fi
else
    curl -s $CURL_COMMAND_PROXY $TAR_FILE_URL -o $TMP_FILE_NAME
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
    
    groupadd -r $USERNAME 2> /dev/null
    tempVar=$?
    if [ $tempVar -ne 0 ] ; then
        if [ $tempVar -ne 9 ] ; then
            echo "Error: Group 'sealion' creation failed!" >&2
            rm -r $INSTALLATION_DIRECTORY
            exit 1
        fi
    fi
    echo "Created 'sealion' group successfully" >&1
    
    useradd -r -d $INSTALLATION_DIRECTORY -g $USERNAME $USERNAME 2> /dev/null
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

if [ -f "$INSTALLATION_DIRECTORYetc/init.d/sealion" ] ; then
    echo "Removing sealion-python"
    "$INSTALLATION_DIRECTORYetc/init.d/sealion" stop
    find "$INSTALLATION_DIRECTORY" -mindepth 1 -maxdepth 1 ! -name 'var' -exec rm -rf {} \; >/dev/null 2>&1
fi

echo "Extracting files to /usr/local/sealion-agent..." >&1
    
    tar -xzf $TMP_FILE_NAME -C $INSTALLATION_DIRECTORY --overwrite
    if [ $? -ne 0 ] ; then
        echo "Error: Installation failed" >&2
        if [ $is_root -eq 1 ] ; then
            userdel sealion
            groupdel sealion
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
    RC1_PATH=`find /etc/ -type d -name rc1.d`
    RC2_PATH=`find /etc/ -type d -name rc2.d`
    RC3_PATH=`find /etc/ -type d -name rc3.d`
    RC4_PATH=`find /etc/ -type d -name rc4.d`
    RC5_PATH=`find /etc/ -type d -name rc5.d`
    RC6_PATH=`find /etc/ -type d -name rc6.d`
    INIT_D_PATH=`find /etc/ -type d -name init.d`

    if [[ -z $RC1_PATH || -z $RC2_PATH || -z $RC3_PATH || -z $RC4_PATH || -z $RC5_PATH || -z $RC6_PATH || -z $INIT_D_PATH ]] ; then
        echo "Error: Could not locate init.d/rc folders" >&2
        userdel sealion
        groupdel sealion
        rm -rf $INSTALLATION_DIRECTORY
        rm -rf $TMP_FILE_PATH
        if [ $? -ne 0 ] ; then
            echo "Error: Failed to delete temporary files" >&2
        fi
        exit 115
    fi

    chown -R $USERNAME:$USERNAME $INSTALLATION_DIRECTORY
    
    ln -sf $INIT_FILE $INIT_D_PATH/sealion
    chmod +x $INIT_FILE
    
    for (( i = 1 ; i < 7 ; i++ )) 
    do
        VAR_NAME="RC"$i"_PATH"
        ln -sf $INIT_FILE ${!VAR_NAME}/${SYMLINK_PATHS[$i]}99sealion
        if [ $? -ne 0 ] ; then
            echo "Error: Unable to update init.d files. Aborting" >&2
            clean_up $i
            exit 1
        fi
    done
    
    echo "Installed SeaLion as a service" >&1
fi

if [ -z $agent_id ] ; then
    if [ -z "$category" ] ; then
        return_code=`curl -s $CURL_COMMAND_PROXY -w "%{http_code}" -H "Content-Type: application/json" -X POST -d "{\"orgToken\":\"$org_token\", \"name\":\"$host\", \"ref\":\"curl\"}"  $REGISTRATION_URL -o $TMP_DATA_NAME`
        if [[ $? -ne 0 || $return_code -ne 201 ]] ; then
            clean_up 6
            echo "Error: Registration failed. Aborting" >&2
            exit 123
        fi
    else
        return_code=`curl -s $CURL_COMMAND_PROXY -w "%{http_code}" -H "Content-Type: application/json" -X POST -d "{\"orgToken\":\"$org_token\", \"name\":\"$host\", \"category\":\"$category\", \"ref\":\"curl\"}"  $REGISTRATION_URL -o $TMP_DATA_NAME`
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

if [ -z $HTTPPROXY ] ; then

    if [ -n $http_proxy ] ; then
        HTTPPROXY=$http_proxy
    else
        if [ -n $HTTP_PROXY ] ;then
            HTTPPROXY=$HTTP_PROXY                
        fi
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
    echo "Error: Service cannot be started" >&2
    exit 1
else
    echo "Installation successful. Please continue on https://sealion.com" >&1
    exit 0
fi