#!/bin/bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

#script error codes
SCRIPT_ERR_SUCCESS=0
SCRIPT_ERR_INVALID_PYTHON=1
SCRIPT_ERR_INCOMPATIBLE_PYTHON=2
SCRIPT_ERR_FAILED_DEPENDENCY=3
SCRIPT_ERR_INCOMPATIBLE_PLATFORM=4
SCRIPT_ERR_COMMAND_NOT_FOUND=6
SCRIPT_ERR_INVALID_USAGE=7
SCRIPT_ERR_FAILED_DIR_CREATE=8
SCRIPT_ERR_FAILED_GROUP_CREATE=9
SCRIPT_ERR_FAILED_USER_CREATE=10

#config variables
API_URL="<api-url>"
VERSION="<version>"

#script variables
BASEDIR=$(readlink -f "$0")
BASEDIR=$(dirname "$BASEDIR")
BASEDIR=${BASEDIR%/}
USER_NAME="sealion"
PYTHON="python"
DEFAULT_INSTALL_PATH="/usr/local/sealion-agent"
INSTALL_AS_SERVICE=1
SEALION_NODE_FOUND=0
UPDATE_AGENT=0
USAGE="Usage: $0 {-o <Organization token> [-c <Category name>] [-H <Host name>] [-x <Proxy address>] [-p <Python binary>] | -h for Help}"

#setup variables
INSTALL_PATH=$DEFAULT_INSTALL_PATH
ORG_TOKEN=
CATEGORY=
AGENT_ID=
HOST_NAME=$(hostname)
PROXY=$https_proxy
NO_PROXY=$no_proxy
REF="tarball"
PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin

while getopts :i:o:c:H:x:p:a:r:v:h OPT ; do
    case "$OPT" in
        i)
            INSTALL_PATH=$OPTARG
            ;;
        o)
            ORG_TOKEN=$OPTARG
            ;;
        c)
            CATEGORY=$OPTARG
            ;;
        h)
            echo $USAGE
            exit $SCRIPT_ERR_SUCCESS
            ;;
        H)
            HOST_NAME=$OPTARG
            ;;
        x)
            PROXY=$OPTARG
            ;;
        p)
            PYTHON=$OPTARG
            ;;
        a)
            AGENT_ID=$OPTARG
            UPDATE_AGENT=1
            ;;
        r)
            REF=$OPTARG
            ;;
        \?)
            echo "Invalid option '-$OPTARG'" >&2
            echo $USAGE
            exit $SCRIPT_ERR_INVALID_USAGE
            ;;
        :)
            echo "Option '-$OPTARG' requires an argument" >&2
            echo $USAGE
            exit $SCRIPT_ERR_INVALID_USAGE
            ;;
    esac
done

if [ "$ORG_TOKEN" == '' ] ; then
    echo "Missing option '-o'" >&2
    echo $USAGE
    exit $SCRIPT_ERR_INVALID_USAGE
fi

if [ "`uname -s`" != "Linux" ] ; then
    echo 'Error: SeaLion agent works on Linux only' >&2
    exit $SCRIPT_ERR_INCOMPATIBLE_PLATFORM
fi

update_agent_config()
{
    KEY="$(echo "$1" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    VALUE="$(echo "$2" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(\"$KEY\"\s*:\s*\)\(\"[^\"]\+\"\)/\1\"$VALUE\"/'"
    eval sed "$ARGS" "\"$INSTALL_PATH/etc/agent.json\""
}

install_service()
{
    RC1_PATH=`find /etc/ -type d -name rc1.d`
    RC2_PATH=`find /etc/ -type d -name rc2.d`
    RC3_PATH=`find /etc/ -type d -name rc3.d`
    RC4_PATH=`find /etc/ -type d -name rc4.d`
    RC5_PATH=`find /etc/ -type d -name rc5.d`
    RC6_PATH=`find /etc/ -type d -name rc6.d`
    INIT_D_PATH=`find /etc/ -type d -name init.d`
    SYMLINK_PATHS=(K K S S S S K)

    if [[ -z $RC1_PATH || -z $RC2_PATH || -z $RC3_PATH || -z $RC4_PATH || -z $RC5_PATH || -z $RC6_PATH || -z $INIT_D_PATH ]] ; then
        echo "Error: Cannot create service sealion. Could not locate init.d/rc directories." >&2
        return 1
    fi
    
    ln -sf "$SERVICE_FILE" $INIT_D_PATH/sealion
    
    for (( i = 1 ; i < 7 ; i++ )) ; do
        VAR_NAME="RC"$i"_PATH"
        ln -sf "$SERVICE_FILE" ${!VAR_NAME}/${SYMLINK_PATHS[$i]}99sealion
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create service sealion. Unable to update init.d files." >&2
            return 1
        fi
    done
    
    return 0
}

check_dependency()
{
    echo "Performing dependency check..."

    if [ "$(which "$PYTHON")" == "" ] ; then
        echo "Error: No python found" >&2
        exit $SCRIPT_ERR_INVALID_PYTHON
    fi

    WHICH_COMMANDS=("sed" "readlink" "cat" "find" "chown" "bash" "grep")

    if [ $UPDATE_AGENT -eq 0 ] ; then
        WHICH_COMMANDS=("${WHICH_COMMANDS[@]}" "groupadd" "useradd" "userdel" "groupdel")
    fi

    MISSING_COMMANDS=""
    PADDING="      "

    for COMMAND in "${WHICH_COMMANDS[@]}" ; do
        if [ "$(which $COMMAND 2>/dev/null)" == "" ] ; then
            MISSING_COMMANDS=$([ "$MISSING_COMMANDS" != "" ] && echo "$MISSING_COMMANDS\n$PADDING Cannot locate command '$COMMAND'" || echo "$PADDING Cannot locate command '$COMMAND'")
        fi
    done

    if [ "$MISSING_COMMANDS" != "" ] ; then
        echo -e "Error: Command dependency check failed\n$MISSING_COMMANDS" >&2
        exit $SCRIPT_ERR_COMMAND_NOT_FOUND
    fi

    cd agent/lib
    PROXY_OPTION=$([ "$PROXY" == "" ] && echo "" || echo "-x $PROXY")
    RET=$("$PYTHON" ../bin/check_dependency.py -p "       " $PROXY_OPTION 2>&1)
    RET_CODE=$?

    if [[ $RET_CODE -eq $SCRIPT_ERR_SUCCESS && "$RET" != "Success" ]] ; then
        echo "Error: '$PYTHON' is not a valid python binary" >&2
        exit $SCRIPT_ERR_INVALID_PYTHON
    elif [ $RET_CODE -ne $SCRIPT_ERR_SUCCESS ] ; then
        echo -e "Error: Python dependency check failed\n$RET" >&2
        rm -rf *.pyc
        find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1
        exit $RET_CODE
    fi

    rm -rf *.pyc
    find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1
    cd ../../
}

migrate_node_agent_config()
{
    TEMP=$(cat "$INSTALL_PATH/etc/config/proxy.json" 2>/dev/null | grep "\"http\_proxy\"\s*:\s*\"\([^\"]*\)\"" -o | sed 's/.*"http\_proxy"\s*:\s*"\([^"]*\)".*/\1/')
    
    if [ "$TEMP" != "" ] ; then
        PROXY=$TEMP
    fi
}

setup_config()
{
    CONFIG="\"orgToken\": \"$ORG_TOKEN\", \"apiUrl\": \"$API_URL\", \"agentVersion\": \"$VERSION\", \"name\": \"$HOST_NAME\", \"ref\": \"$REF\""
    TEMP_VAR=""

    if [ "$CATEGORY" != "" ] ; then
        CONFIG="$CONFIG, \"category\": \"$CATEGORY\""
    fi

    if [ "$AGENT_ID" != "" ] ; then
        CONFIG="$CONFIG, \"_id\": \"$AGENT_ID\""
    fi
        
    echo "{$CONFIG}" >"$INSTALL_PATH/etc/agent.json"

    if [ "$PROXY" != "" ] ; then
        PROXY="$(echo "$PROXY" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
        ARGS="-i 's/\(\"env\"\s*:\s*\[\)/\1{\"https\_proxy\": \"$PROXY\"}/'"
        eval sed "$ARGS" "\"$INSTALL_PATH/etc/config.json\""
        TEMP_VAR=", "
    fi

    if [ "$NO_PROXY" != "" ] ; then
        NO_PROXY="$(echo "$NO_PROXY" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
        ARGS="-i 's/\(\"env\"\s*:\s*\[\)/\1{\"no\_proxy\": \"$NO_PROXY\"}$TEMP_VAR/'"
        eval sed "$ARGS" "\"$INSTALL_PATH/etc/config.json\""
    fi

    PYTHON="$(echo "$PYTHON" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/python/\"$PYTHON\"/'"
    eval sed "$ARGS" "\"$INSTALL_PATH/etc/init.d/sealion\""
    eval sed "$ARGS" "\"$INSTALL_PATH/uninstall.sh\""
}

INSTALL_PATH=$(eval echo "$INSTALL_PATH")

if [[ "$INSTALL_PATH" != "" && ${INSTALL_PATH:0:1} != "/" ]] ; then
    INSTALL_PATH="$(pwd)/$INSTALL_PATH"
fi

INSTALL_PATH=${INSTALL_PATH%/}
cd "$BASEDIR"
check_dependency

if [ "$INSTALL_PATH" != "$DEFAULT_INSTALL_PATH" ] ; then
    INSTALL_AS_SERVICE=0
fi

SERVICE_FILE="$INSTALL_PATH/etc/init.d/sealion"

if [ -f "$INSTALL_PATH/bin/sealion-node" ] ; then
    SEALION_NODE_FOUND=1
fi

if [ $UPDATE_AGENT -eq 0 ] ; then
    if [[ $EUID -ne 0 ]]; then
        echo "Error: You need to run this as root" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi

    mkdir -p "$INSTALL_PATH/var/log"
    chmod +x "$INSTALL_PATH"

    if [ $? -ne 0 ] ; then
        echo "Error: Cannot create installation directory at '$INSTALL_PATH'" >&2
        exit $SCRIPT_ERR_FAILED_DIR_CREATE
    else
        echo "Install directory created at '$INSTALL_PATH'"
    fi

    if [ "$(grep "^$USER_NAME" /etc/group)" == "" ] ; then
        groupadd -r $USER_NAME >/dev/null 2>&1
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create $USER_NAME group" >&2
            exit $SCRIPT_ERR_FAILED_GROUP_CREATE
        else
            echo "Group $USER_NAME created"
        fi
    else
        echo "Group $USER_NAME already exists"
    fi

    id $USER_NAME >/dev/null 2>&1

    if [ $? -ne 0 ] ; then
        useradd -rM -g $USER_NAME $USER_NAME >/dev/null 2>&1
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create user $USER_NAME" >&2
            exit $SCRIPT_ERR_FAILED_USER_CREATE
        else
            echo "User $USER_NAME created"
        fi
    else
        echo "User $USER_NAME already exists"
    fi
else
    if [ "$(id -u -n)" != "$USER_NAME" ] ; then
        echo "Error: You need to run this as $USER_NAME user" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi

    if [[ ! -f "$SERVICE_FILE" && $SEALION_NODE_FOUND -eq 0 ]] ; then
        echo "Error: '$INSTALL_PATH' is not a valid sealion installation directory" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi
fi

if [ $SEALION_NODE_FOUND -eq 1 ] ; then
    echo "Removing sealion-node..."
    "$INSTALL_PATH/etc/sealion" stop >/dev/null 2>&1
    find "$INSTALL_PATH/var/log" -mindepth 1 -maxdepth 1 -type f -regextype sed ! -regex '\(.*/update\.log\)\|\(.*/.\+\.old\..\+\)' -exec mv "{}" "$(mktemp -u {}.old.XXXX)" \; 1>/dev/null 2>&1
    find "$INSTALL_PATH/var" -mindepth 1 -maxdepth 1 ! -name 'log' -exec rm -rf "{}" \; 1>/dev/null 2>&1
    find "$INSTALL_PATH" -mindepth 1 -maxdepth 1 ! -name 'var' ! -name 'tmp' -exec rm -rf "{}" \; >/dev/null 2>&1
fi

if [ -f "$SERVICE_FILE" ] ; then
    echo "Stopping agent..."
    "$SERVICE_FILE" stop
fi

echo "Copying files..."

if [ $UPDATE_AGENT -eq 0 ] ; then
    find "$INSTALL_PATH" -mindepth 1 -maxdepth 1 ! -name 'var' -exec rm -rf "{}" \; >/dev/null 2>&1
    cp -r agent/* "$INSTALL_PATH"
    setup_config
    chown -R $USER_NAME:$USER_NAME "$INSTALL_PATH"
    echo "Sealion agent installed successfully"    

    if [ $INSTALL_AS_SERVICE -eq 1 ] ; then
        install_service

        if [ $? -ne 0 ] ; then
            echo "Use '$SERVICE_FILE' to control sealion"
        else
            echo "Service created"
        fi
    else
        echo "Use '$SERVICE_FILE' to control sealion"
    fi
else
    if [ $SEALION_NODE_FOUND -eq 1 ] ; then
        cp -r agent/* "$INSTALL_PATH"
        setup_config
        ln -sf "$SERVICE_FILE" "$INSTALL_PATH/etc/sealion"
    else
        find "$INSTALL_PATH" -mindepth 1 -maxdepth 1 ! -name 'var' ! -name 'etc' ! -name 'tmp' -exec rm -rf "{}" \; >/dev/null 2>&1
        find agent/ -mindepth 1 -maxdepth 1 ! -name 'etc' -exec cp -r {} "$INSTALL_PATH" \;
        update_agent_config "agentVersion" $VERSION
        update_agent_config "apiUrl" $API_URL
    fi

    echo "Sealion agent updated successfully"
fi

echo "Starting agent..."
"$SERVICE_FILE" start
RET=$?

if [[ $UPDATE_AGENT -eq 0 && $RET -eq 0 ]] ; then
    URL="$(echo "$API_URL" | sed 's/api\(\.\|-\)//')"
    echo "Please continue on $URL"
fi

exit $RET
