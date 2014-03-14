#!/bin/bash

#check platform compatibility
if [ "`uname -s`" != "Linux" ] ; then
    echo 'Error: SeaLion agent works on Linux only' >&2
    exit 1
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
DEFAULT_INSTALL_PATH="/usr/local/sealion-agent"
INSTALL_AS_SERVICE=1
SEALION_NODE_FOUND=0
IGNORE_ORG_TOKEN=0
UPDATING_NODE_AGENT=0
USAGE="Usage: $0 {-o <org token> [-c <category name>] [-H <host name>] [-x <https proxy>] [-p <python binary>] | -h}"

#setup variables
INSTALL_PATH=$DEFAULT_INSTALL_PATH
ORG_TOKEN=
CATEGORY=
HOST_NAME=$(hostname)
PROXY=$https_proxy
NO_PROXY=$no_proxy

while getopts :i:o:c:H:x:p:a:v:h OPT ; do
    case "$OPT" in
        i)
            INSTALL_PATH=$OPTARG
            ;;
        o)
            if [ $IGNORE_ORG_TOKEN -eq 0 ] ; then
                ORG_TOKEN=$OPTARG
            fi
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
        a)
            IGNORE_ORG_TOKEN=1
            ;;
        v)
            IGNORE_ORG_TOKEN=1
            ;;
        \?)
            echo "Invalid option '-$OPTARG'" >&2
            echo $USAGE
            exit 126
            ;;
        :)
            echo "Option '-$OPTARG' requires an argument." >&2
            echo $USAGE
            exit 125
            ;;
    esac
done

#check for python (min 2.6)
PYTHON_OK=0
PYTHON=$(readlink -f "$PYTHON" 2>/dev/null)

if [ $? -ne 0 ] ; then
    echo "Error: '$PYTHON' is not a valid python binary" >&2
    exit 1
fi

if [ -f "$PYTHON" ] ; then
    case $("$PYTHON" --version 2>&1) in
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
        echo "Error: Cannot create service seealion. Could not locate init.d/rc directories." >&2
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
    MODULES=('socketio_client' 'sqlite3')
    STMTS=

    for (( i = 0 ; i < ${#MODULES[@]}; i++ )) ; do
        STMTS="$STMTS\n\timport ${MODULES[$i]}"
    done

    CODE=$(printf "import sys\nsys.path.append('websocket_client')\nsys.path.append('socketio_client')\n\ntry:$STMTS\nexcept Exception as e:\n\tprint(str(e))\n\tsys.exit(1)\n\nsys.exit(0)")
    ret=$($PYTHON -c "$CODE" 2>&1)

    if [ $? -ne 0 ] ; then
        echo "Error: Python package dependency check failed; $ret"
        rm -rf *.pyc
        find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1
        exit 1
    fi

    rm -rf *.pyc
    find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1
    cd ../../
}

migrate_node_agent_config()
{
    
}

setup_config()
{
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
}

INSTALL_PATH=$(readlink -m "$INSTALL_PATH" 2>/dev/null)

if [ $? -ne 0 ] ; then
    echo "Error: '$INSTALL_PATH' is not a valid directory" >&2
    exit 1
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

if [ "$ORG_TOKEN" != '' ] ; then
    if [[ $EUID -ne 0 ]]; then
        echo "Error: You need to run this as root user" >&2
        exit 1
    fi

    mkdir -p "$INSTALL_PATH"

    if [ $? -ne 0 ] ; then
        echo "Error: Cannot create installation directory at '$INSTALL_PATH'" >&2
        exit 118
    else
        echo "Install directory created at '$INSTALL_PATH'"
    fi

    id -g $USER_NAME >/dev/null 2>&1

    if [ $? -ne 0 ] ; then
        groupadd -r $USER_NAME >/dev/null 2>&1
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create $USER_NAME group" >&2
            exit 1
        else
            echo "Group $USER_NAME created"
        fi
    else
        echo "Group $USER_NAME already exists"
    fi

    id $USER_NAME >/dev/null 2>&1

    if [ $? -ne 0 ] ; then
        useradd -rMN -g $USER_NAME $USER_NAME >/dev/null 2>&1
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create $USER_NAME user" >&2
            exit 1
        else
            echo "User $USER_NAME created"
        fi
    else
        echo "User $USER_NAME already exists"
    fi
else
    if [ "$(id -u -n)" != "$USER_NAME" ] ; then
        echo "Error: You need to run this as $USER_NAME user" >&2
        exit 1
    fi

    if [[ ! -f "$SERVICE_FILE" && $SEALION_NODE_FOUND -eq 0 ]] ; then
        echo "Error: '$INSTALL_PATH' is not a valid sealion install directory" >&2
        exit 1
    fi
fi

if [ $SEALION_NODE_FOUND -eq 1 ] ; then
    if [ "$ORG_TOKEN" == '' ] ; then
        migrate_node_agent_config
    fi

    echo "Removing sealion-node"
    kill -SIGKILL `pgrep -d ',' 'sealion-node'` >/dev/null 2>&1
    find "$INSTALL_PATH" -mindepth 1 -maxdepth 1 -exec rm -rf {} \; >/dev/null 2>&1
fi

if [ -f "$SERVICE_FILE" ] ; then
    echo "Stopping agent..."
    "$SERVICE_FILE" stop
fi

echo "Copying files..."

if [ "$ORG_TOKEN" != '' ] ; then
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
        find agent/ -mindepth 1 -maxdepth 1 -type d ! -name 'etc' -exec cp -r {} "$INSTALL_PATH" \;
        update_agent_config "agentVersion" $VERSION
        update_agent_config "apiUrl" $API_URL
        update_agent_config "updateUrl" $UPDATE_URL
    fi

    echo "Sealion agent updated successfully"
fi

echo "Starting agent..."
"$SERVICE_FILE" start

