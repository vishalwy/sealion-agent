#!/bin/bash

#check platform compatibility
if [ "`uname -s`" != "Linux" ] ; then
    echo 'Error: SeaLion agent works on Linux only' >&2
    exit 1
fi

#check for kernel version (min 2.6)
eval $(uname -r | awk -F'.' '{printf("KERNEL_VERSION=%s KERNEL_MAJOR=%s\n", $1, $2)}')

if [ $KERNEL_VERSION -le 2 ] ; then
    if [[ $KERNEL_VERSION -eq 1 || $KERNEL_MAJOR -lt 6 ]] ; then
        echo "Error: SeaLion agent requires kernel 2.6 or above" >&2
        exit 1
    fi
fi

#config variables
API_URL="<api-url>"
UPDATE_URL="<agent-download-url>"
VERSION="<version>"

#script variables
BASEDIR=$(readlink -f "$0")
BASEDIR=$(dirname "$BASEDIR")
BASEDIR=${BASEDIR%/}
USER_NAME="sealion"
PYTHON=$(which python)
IS_UPDATE=1
DEFAULT_INSTALL_PATH="/usr/local/sealion-agent"
INSTALL_AS_SERVICE=1
USAGE="Usage: $0 {-o <org token> [-c <category name>] [-h <host name>] [-x <https proxy>] [-p <python binary>] | -h}"

#setup variables
INSTALL_PATH=$DEFAULT_INSTALL_PATH
ORG_TOKEN=
CATEGORY=
HOST_NAME=$(hostname)
PROXY=$https_proxy
NO_PROXY=$no_proxy

while getopts :i:o:c:H:x:p:h OPT ; do
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
            exit 0
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
        \?)
            echo "Invalid option -$OPTARG" >&2
            exit 126
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            exit 125
            ;;
    esac
done

#check for python (min 2.6)
PYTHON_OK=0

if [ -f $PYTHON ] ; then
    case "$($PYTHON --version 2>&1)" in
        *" 3."*)
            PYTHON_OK=1
            ;;
        *" 2.6"*)
            PYTHON_OK=1
            ;;
        *" 2.7"*)
            PYTHON_OK=1
            ;;
    esac
fi

if [ $PYTHON_OK -eq 0 ] ; then
    echo "Error: SeaLion agent requires python version 2.6 or above" >&2
    exit 1
fi

update_agent_config()
{
    ARGS="-i 's/\(\"$1\"\s*:\s*\)\(\"[^\"]\+\"\)/\1\"$2\"/'"
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
        echo "Error: Cannot create service. Could not locate init.d/rc directories" >&2
        return 1
    fi
    
    ln -sf "$SERVICE_FILE" $INIT_D_PATH/sealion
    
    for (( i = 1 ; i < 7 ; i++ )) ; do
        VAR_NAME="RC"$i"_PATH"
        ln -sf "$SERVICE_FILE" ${!VAR_NAME}/${SYMLINK_PATHS[$i]}99sealion
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create service. Unable to update init.d files" >&2
            return 1
        fi
    done
    
    return 0
}

check_dependency()
{
    cd agent/lib
    CODE=$(printf "import sys\nsys.path.append('websocket_client')\nsys.path.append('socketio_client')\n\ntry:\n\timport socketio_client\nexcept Exception as e:\n\tprint(str(e))\n\tsys.exit(1)\n\nsys.exit(0)")
    ret=$($PYTHON -c "$CODE" 2>&1)

    if [ $? -ne 0 ] ; then
        echo "Error: Python package dependency check failed; $ret"
        rm -rf *.pyc
        exit 1
    fi

    rm -rf *.pyc
    cd ../../
}

INSTALL_PATH=$(readlink -m "$INSTALL_PATH")
INSTALL_PATH=${INSTALL_PATH%/}
cd "$BASEDIR"
check_dependency

if [ "$INSTALL_PATH" != "$DEFAULT_INSTALL_PATH" ] ; then
    INSTALL_AS_SERVICE=0
fi

SERVICE_FILE="$INSTALL_PATH/etc/init.d/sealion"

if [ "$ORG_TOKEN" != '' ] ; then
    if [[ $EUID -ne 0 ]]; then
        echo "Error: You need to run this as root user" >&2
        exit 1
    fi

    IS_UPDATE=0

    echo "Creating install directory at '$INSTALL_PATH'"
    mkdir -p "$INSTALL_PATH"

    if [ $? -ne 0 ] ; then
        echo "Error: Cannot create installation directory" >&2
        exit 118
    fi

    id -g $USER_NAME >/dev/null 2>&1

    if [ $? -ne 0 ] ; then
        echo "Creating $USER_NAME group"
        groupadd -r $USER_NAME >/dev/null 2>&1
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create $USER_NAME group" >&2
            exit 1
        fi
    else
        echo "Group $USER_NAME already exists"
    fi

    id $USER_NAME >/dev/null 2>&1

    if [ $? -ne 0 ] ; then
        echo "Creating $USER_NAME user"
        useradd -rMN -g $USER_NAME $USER_NAME >/dev/null 2>&1
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create $USER_NAME user" >&2
            exit 1
        fi
    else
        echo "User $USER_NAME already exists"
    fi
else
    if [ "$(id -u -n)" != "$USER_NAME" ] ; then
        echo "Error: You need to run this as $USER_NAME user" >&2
        exit 1
    fi

    if [ ! -f "$SERVICE_FILE" ] ; then
        echo "Error: '$INSTALL_PATH' is not a valid sealion install directory" >&2
        exit 1
    fi
fi

if [ -f "$INSTALL_PATH/bin/sealion-node" ] ; then
    echo "Killing evil twin :-)"
    rm -rf "$INSTALL_PATH/*"
fi

if [ -f "$SERVICE_FILE" ] ; then
    echo "Stopping agent"
    "$SERVICE_FILE" stop
fi

echo "Copying files"

if [ $IS_UPDATE -eq 0 ] ; then
    cp -r agent/* "$INSTALL_PATH"
    CONFIG="\"orgToken\": \"$ORG_TOKEN\", \"apiUrl\": \"$API_URL\", \"updateUrl\": \"$UPDATE_URL\", \"agentVersion\": \"$VERSION\", \"name\": \"$HOST_NAME\""
    TEMP_VAR=""

    if [ "$CATEGORY" != "" ] ; then
        CONFIG="$CONFIG, \"category\": \"$CATEGORY\""
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
    find agent/ -mindepth 1 -maxdepth 1 -type d ! -name 'etc' -exec cp -r {} "$INSTALL_PATH" \;
    update_agent_config "agentVersion" $VERSION
    update_agent_config "apiUrl" $API_URL
    update_agent_config "updateUrl" $UPDATE_URL
    echo "Sealion agent updated successfully"
fi

echo "Starting agent"
"$SERVICE_FILE" start

