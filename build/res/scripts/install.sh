#!/usr/bin/env bash

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

#directory of the script
BASEDIR=$(readlink -f "$0")
BASEDIR=${BASEDIR%/*}

USER_NAME="sealion"  #username for the agent
PYTHON="python"  #default python binary
DEFAULT_INSTALL_PATH="/usr/local/sealion-agent"  #default install directory
INSTALL_AS_SERVICE=1  #whether to install agent as system service
SEALION_NODE_FOUND=0  #evil twin
UPDATE_AGENT=0  #install or update
USAGE="Usage: $0 {-o <Organization token> [-c <Category name>] [-H <Host name>] [-x <Proxy address>] [-p <Python binary>] | -h for Help}"

#setup variables
INSTALL_PATH=$DEFAULT_INSTALL_PATH
ORG_TOKEN=
CATEGORY=
AGENT_ID=
HOST_NAME=$(hostname)
PROXY=$https_proxy  #export https proxy
NO_PROXY=$no_proxy  #export no proxy
REF="tarball"  #the method used to install agent. curl or tarball
ENV_VARS=()  #any other environment variables to export
PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin  #common paths found in various linux distributions
PADDING="      "  #padding for messages

#check if it is Linux
if [ "$(uname -s)" != "Linux" ] ; then
    echo 'Error: SeaLion agent works on Linux only' >&2
    exit $SCRIPT_ERR_INCOMPATIBLE_PLATFORM
fi

#extract kernel version
KERNEL_VERSION=$(uname -r)
KERNEL_MAJOR_VERSION="${KERNEL_VERSION%%.*}"
KERNEL_VERSION="${KERNEL_VERSION#*.}"
KERNEL_MINOR_VERSION="${KERNEL_VERSION%%.*}"

#check if the kernel version is >2.6
if [[ $KERNEL_MAJOR_VERSION -lt 2 || ($KERNEL_MAJOR_VERSION -eq 2 && $KERNEL_MINOR_VERSION -lt 6) ]] ; then
    echo 'Error: SeaLion agent requires kernel version 2.6 or above' >&2
    exit $SCRIPT_ERR_INCOMPATIBLE_PLATFORM
fi

#parse command line options
while getopts :i:o:c:H:x:p:a:r:v:e:h OPT ; do
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
        e)
            ENV_VARS=("${ENV_VARS[@]}" "$OPTARG")
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

#there should be an organization token
if [ "$ORG_TOKEN" == '' ] ; then
    echo "Missing option '-o'" >&2
    echo $USAGE
    exit $SCRIPT_ERR_INVALID_USAGE
fi

#function to create service scripts
install_service()
{
    #service file paths
    RC1_PATH=`find /etc/ -type d -name rc1.d`
    RC2_PATH=`find /etc/ -type d -name rc2.d`
    RC3_PATH=`find /etc/ -type d -name rc3.d`
    RC4_PATH=`find /etc/ -type d -name rc4.d`
    RC5_PATH=`find /etc/ -type d -name rc5.d`
    RC6_PATH=`find /etc/ -type d -name rc6.d`
    INIT_D_PATH=`find /etc/ -type d -name init.d`
    SYMLINK_PATHS=(K K S S S S K)

    #locate paths
    if [[ -z $RC1_PATH || -z $RC2_PATH || -z $RC3_PATH || -z $RC4_PATH || -z $RC5_PATH || -z $RC6_PATH || -z $INIT_D_PATH ]] ; then
        echo "Error: Cannot create service sealion. Could not locate init.d/rc directories." >&2
        return 1
    fi
    
    #create a symlink to the control script. the same scriot can be used directly to control the agent
    ln -sf "$SERVICE_FILE" $INIT_D_PATH/sealion
    
    #update init.d files
    for (( i = 1 ; i < 7 ; i++ )) ; do
        VAR_NAME="RC"$i"_PATH"
        ln -sf "$SERVICE_FILE" ${!VAR_NAME}/${SYMLINK_PATHS[$i]}99sealion
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create service sealion. Unable to update init.d files." >&2
            return 1
        fi
    done
    
    return 0  #success
}

#function to check command and python module dependency 
check_dependency()
{
    #check if python binary is valid
    if [ "$(type -P "$PYTHON")" == "" ] ; then
        echo "Error: No python found" >&2
        exit $SCRIPT_ERR_INVALID_PYTHON
    fi

    #various commands required for installer and the agent
    WHICH_COMMANDS=("sed" "cat" "find" "chown" "bash" "grep")

    #we need commands for user/group management if it is an agent installation and not update
    if [ $UPDATE_AGENT -eq 0 ] ; then
        WHICH_COMMANDS=("${WHICH_COMMANDS[@]}" "groupadd" "useradd" "userdel" "groupdel")
    fi

    MISSING_COMMANDS=()  #array to hold missing commands

    #loop through the commands and find the missing commands
    for COMMAND in "${WHICH_COMMANDS[@]}" ; do
        if [ "$(type -P $COMMAND 2>/dev/null)" == "" ] ; then
            MISSING_COMMANDS=("${MISSING_COMMANDS[@]}" "$PADDING Cannot locate command '$COMMAND'")
        fi
    done

    #print out and exit if there are any commands missing
    if [ "${#MISSING_COMMANDS[@]}" != "0" ] ; then
        echo -e "Error: Command dependency check failed\n$(IFS=$'\n'; echo "${MISSING_COMMANDS[*]}")" >&2
        exit $SCRIPT_ERR_COMMAND_NOT_FOUND
    fi

    RET=$("$PYTHON" agent/bin/check_dependency.py 2>&1)  #execute the script to find out any missing modules
    RET_CODE=$?

    if [[ $RET_CODE -eq $SCRIPT_ERR_SUCCESS && "$RET" != "Success" ]] ; then  #is python really a python binary. check the output to validate it
        echo "Error: '$PYTHON' is not a valid python binary" >&2
        exit $SCRIPT_ERR_INVALID_PYTHON
    elif [ $RET_CODE -ne $SCRIPT_ERR_SUCCESS ] ; then  #dependency check failed
        echo "Error: Python dependency check failed" >&2
        echo -e $RET | (while read LINE; do echo "$PADDING $LINE" >&2; done)  #print the missing modules with some padding

        #cleanup the temp files generated while performing python dependency check
        rm -rf *.pyc
        find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1

        exit $RET_CODE
    fi

    #cleanup the temp files generated while performing python dependency check
    rm -rf *.pyc
    find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1
}

#function to export environment variables stored in $ENV_VARS
export_env_var()
{
    ERROR_EN_VARS=()  #array to hold erroneous JSON objects for env vars

    for ENV_VAR in "${ENV_VARS[@]}" ; do
        TEMP_OUTPUT=$("$PYTHON" agent/bin/configure.py -a "add" -k "env" -v "$ENV_VAR" "$INSTALL_PATH/etc/config.json" 2>&1)

        #add to error list if it failed
        if [ $? -ne 0 ] ; then
            ERROR_EN_VARS=("${ERROR_EN_VARS[@]}" "$PADDING $ENV_VAR - ${TEMP_OUTPUT#Error: }")
        fi
    done

    #print any errors as warnings
    if [ "${#ERROR_EN_VARS[@]}" != "0" ] ; then
        echo -e "Warning: Failed to export the folloing environment variables\n$(IFS=$'\n'; echo "${ERROR_EN_VARS[*]}")" >&2
    fi
}

#function to setup the configuration for the agent
setup_config()
{
    #agent.json config
    CONFIG="\"orgToken\": \"$ORG_TOKEN\", \"apiUrl\": \"$API_URL\", \"agentVersion\": \"$VERSION\", \"name\": \"$HOST_NAME\", \"ref\": \"$REF\""

    #add category if specified
    if [ "$CATEGORY" != "" ] ; then
        CONFIG="$CONFIG, \"category\": \"$CATEGORY\""
    fi

    #add agent id if specified
    if [ "$AGENT_ID" != "" ] ; then
        CONFIG="$CONFIG, \"_id\": \"$AGENT_ID\""
    fi
    
    "$PYTHON" agent/bin/configure.py -a "set" -k "" -v "{$CONFIG}" -n "$INSTALL_PATH/etc/agent.json"  #set the configuration
    export_env_var  #export the environment variables specified

    #specify the python binary in the control script and uninstaller
    PYTHON="$(echo "$PYTHON" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/python/\"$PYTHON\"/'"
    eval sed "$ARGS" "\"$INSTALL_PATH/etc/init.d/sealion\""
    eval sed "$ARGS" "\"$INSTALL_PATH/uninstall.sh\""
}

#set the install path
INSTALL_PATH=$(eval echo "$INSTALL_PATH")  #evaluate the path to resolve symbols like ~
INSTALL_PATH=$([[ "$INSTALL_PATH" != "" && ${INSTALL_PATH:0:1} != "/" ]] && echo "$(pwd)/$INSTALL_PATH" || echo "$INSTALL_PATH")  #absolute path
INSTALL_PATH=${INSTALL_PATH%/}  #remove / from the end

cd "$BASEDIR"  #move to the script base dir so that all paths can be found
check_dependency  #perform dependency check

#export https_proxy env
if [ "$PROXY" != "" ] ; then
    ENV_VARS=("${ENV_VARS[@]}" "{\"https_proxy\": \"$PROXY\"}")
fi

#export no_proxy env
if [ "$NO_PROXY" != "" ] ; then
    ENV_VARS=("${ENV_VARS[@]}" "{\"no_proxy\": \"$NO_PROXY\"}")
fi

#install service if installing to the default path
if [ "$INSTALL_PATH" != "$DEFAULT_INSTALL_PATH" ] ; then
    INSTALL_AS_SERVICE=0
fi

SERVICE_FILE="$INSTALL_PATH/etc/init.d/sealion"  #service file for the agent

#check for existence of evil twin
if [ -f "$INSTALL_PATH/bin/sealion-node" ] ; then
    SEALION_NODE_FOUND=1
fi

if [ $UPDATE_AGENT -eq 0 ] ; then  #if this is a fresh install
    if [[ $EUID -ne 0 ]]; then  #run install script as root as it require some privileged operations like creating user/group etc
        echo "Error: You need to run this as root" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi

    #create install directory
    mkdir -p "$INSTALL_PATH/var/log"

    #error check
    if [ $? -ne 0 ] ; then
        echo "Error: Cannot create installation directory at '$INSTALL_PATH'" >&2
        exit $SCRIPT_ERR_FAILED_DIR_CREATE
    else
        echo "Install directory created at '$INSTALL_PATH'"
    fi

    chmod +x "$INSTALL_PATH"

    #create sealion group
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

    #check for sealion user
    id $USER_NAME >/dev/null 2>&1

    #create sealion user if it doesn't exists
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
    #update should run as sealion user only
    if [ "$(id -u -n)" != "$USER_NAME" ] ; then
        echo "Error: You need to run this as $USER_NAME user" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi

    #validate the install path by checking the presence of service file
    #if this is an update from SeaLion node agent, then ignore it
    if [[ ! -f "$SERVICE_FILE" && $SEALION_NODE_FOUND -eq 0 ]] ; then
        echo "Error: '$INSTALL_PATH' is not a valid sealion installation directory" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi
fi

#remove the evil twin
if [ $SEALION_NODE_FOUND -eq 1 ] ; then
    echo "Removing sealion-node..."
    "$INSTALL_PATH/etc/sealion" stop >/dev/null 2>&1  #stop the node agent

    #rename the node agent log file
    find "$INSTALL_PATH/var/log" -mindepth 1 -maxdepth 1 -type f -regextype sed ! -regex '\(.*/update\.log\)\|\(.*/.\+\.old\..\+\)' -exec mv "{}" "$(mktemp -u {}.old.XXXX)" \; 1>/dev/null 2>&1
    
    #remove all the files except var/log/*
    find "$INSTALL_PATH/var" -mindepth 1 -maxdepth 1 ! -name 'log' -exec rm -rf "{}" \; 1>/dev/null 2>&1
    find "$INSTALL_PATH" -mindepth 1 -maxdepth 1 ! -name 'var' ! -name 'tmp' -exec rm -rf "{}" \; >/dev/null 2>&1
fi

#stop the agent if it is an update or re-install
if [ -f "$SERVICE_FILE" ] ; then
    echo "Stopping agent..."
    "$SERVICE_FILE" stop
    RET=$?

    #exit if the user interrupted the operation or the command was not found
    if [[ $RET -eq 34 || $RET -eq 127 ]] ; then
        exit $RET
    fi
fi

echo "Copying files..."

if [ $UPDATE_AGENT -eq 0 ] ; then  #if it is not an update
    #remove everything except var folder and copy the new files
    find "$INSTALL_PATH" -mindepth 1 -maxdepth 1 ! -name 'var' -exec rm -rf "{}" \; >/dev/null 2>&1
    cp -r agent/* "$INSTALL_PATH"

    setup_config  #create the configuration
    chown -R $USER_NAME:$USER_NAME "$INSTALL_PATH"  #change ownership
    echo "Sealion agent installed successfully"    

    #create service if agent is installed at default location
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
else  #update
    if [ $SEALION_NODE_FOUND -eq 1 ] ; then  #if updating sealion node
        cp -r agent/* "$INSTALL_PATH"  #copy the files
        setup_config  #create configuration

        #since update is run as unprivileged sealion user, we wont be able to modify /etc/sealion
        #instead convert the sealion node service file to point it to the new service file.
        #in effect it becomes /etc/sealion -> INSTALL_PATH/etc/sealion -> INSTALL_PATH/etc/init.d/sealion
        ln -sf "$SERVICE_FILE" "$INSTALL_PATH/etc/sealion"
    else
        #remove all files except var/ etc/ and tmp/ and copy files except etc/
        find "$INSTALL_PATH" -mindepth 1 -maxdepth 1 ! -name 'var' ! -name 'etc' ! -name 'tmp' -exec rm -rf "{}" \; >/dev/null 2>&1
        find agent/ -mindepth 1 -maxdepth 1 ! -name 'etc' -exec cp -r {} "$INSTALL_PATH" \;

        #update the agent version and api url in agent.json
        "$PYTHON" agent/bin/configure.py -a "set" -k "agentVersion" -v "\"$VERSION\"" -n "$INSTALL_PATH/etc/agent.json"
        "$PYTHON" agent/bin/configure.py -a "set" -k "apiUrl" -v "\"$API_URL\"" -n "$INSTALL_PATH/etc/agent.json"
    fi

    echo "Sealion agent updated successfully"
fi

echo "Starting agent..."
"$SERVICE_FILE" start
RET=$?

if [[ $UPDATE_AGENT -eq 0 && $RET -eq 0 ]] ; then
    echo "Find more info at '$INSTALL_PATH/README'"
    URL="$(echo "$API_URL" | sed 's/api\(\.\|-\)//')"
    echo "Please continue on $URL"
fi

exit $RET
