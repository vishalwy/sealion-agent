#!/usr/bin/env bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found

#script directory
script_base_dir=$(readlink -f "$0")
script_base_dir=${script_base_dir%/*}

source "$script_base_dir/helper.sh"  #import utility functions

#Function to print usage info
#Arguments
#   $1 - whether to print the whole help or just the prompt
#Returns 0
usage()
{
    if [ "$1" != "1" ] ; then
        echo "Run '$0 --help' for more information"
        return 0
    fi

    local usage_info="Usage: $0 [options] <organization token>\nOptions:\n"
    usage_info+=" -o,\t                  \tOrganization token; This is kept for backward compatibility and has a higher precedence\n"
    usage_info+=" -c,\t--category <arg>  \tCategory name under which the server to be registered\n"
    usage_info+=" -H,\t--host-name <arg> \tServer name to be used\n"
    usage_info+=" -x,\t--proxy <arg>     \tProxy server details\n"
    usage_info+=" -p,\t--python <arg>    \tPath to the python binary used for executing agent code\n"
    usage_info+=" -e,\t--env <arg>, ...  \tJSON document representing the environment variables to be exported\n"
    usage_info+=" -h,\t--help            \tDisplay this information"
    echo -e "$usage_info"
    return 0
}

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
api_url="<api-url>"
version="<version>"

user_name="sealion"  #username for the agent
python_binary="python"  #default python binary
default_install_path="/usr/local/sealion-agent"  #default install directory
sealion_node_found=0  #evil twin
update_agent=0  #install or update

#setup variables
org_token= category= agent_id=
install_path=$default_install_path host_name=$(hostname)
proxy=$https_proxy no_proxy=$no_proxy
install_source="tarball"  #the method used to install agent. curl or tarball
env_vars=()  #any other environment variables to export
padding="       "  #padding for messages

#check if it is Linux
if [[ "$(uname -s)" != "Linux" ]] ; then
    echo 'SeaLion agent works on Linux only' >&2
    exit $SCRIPT_ERR_INCOMPATIBLE_PLATFORM
fi

#extract kernel version
kernel_version=$(uname -r)
kernel_major_version="${kernel_version%%.*}"
kernel_version="${kernel_version#*.}"
kernel_minor_version="${kernel_version%%.*}"

#check if the kernel version is > 2.6
if [[ $kernel_major_version -lt 2 || ($kernel_major_version -eq 2 && $kernel_minor_version -lt 6) ]] ; then
    echo 'SeaLion agent requires kernel version 2.6 or above' >&2
    exit $SCRIPT_ERR_INCOMPATIBLE_PLATFORM
fi

#parse command line
opt_parse i:o:c:H:x:p:a:r:v:e:h "category= host-name= proxy= python= env= help" options args "$@"

#if parsing failed print the usage and exit
if [[ $? -ne 0 ]] ; then
    echo "$options" >&2
    usage ; exit $SCRIPT_ERR_INVALID_USAGE
fi

#set organization token if any
for arg in "${args[@]}" ; do
    org_token=$arg
done

#loop through the options
for option_index in "${!options[@]}" ; do
    [[ $(( option_index % 2 )) -ne 0 ]] && continue  #skip option arguments
    option_arg=${options[$(( option_index + 1 ))]}  #option argument for the current option

    #find the proper option and perform the action
    case "${options[${option_index}]}" in
        i)
            install_path=$option_arg
            ;;
        o)
            org_token=$option_arg
            ;;
        c|category)
            category=$option_arg
            ;;
        H|host-name)
            host_name=$option_arg
            ;;
        x|proxy)
            proxy=$option_arg
            ;;
        p|python)
            python_binary=$option_arg
            ;;
        a)
            agent_id=$option_arg
            update_agent=1
            ;;
        r)
            install_source=$option_arg
            ;;
        e|env)
            env_vars+=("$option_arg")
            ;;
        h|help)
            usage 1 ; exit $SCRIPT_ERR_SUCCESS
            ;;
    esac
done

#there should be an organization token
if [ "$org_token" == '' ] ; then
    echo "Please specify an organization token" >&2
    usage
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
    if [ "$(type -P "$python_binary")" == "" ] ; then
        echo "Error: No python found" >&2
        exit $SCRIPT_ERR_INVALID_PYTHON
    fi

    #various commands required for installer and the agent
    WHICH_COMMANDS=("sed" "cat" "find" "chown" "bash" "grep" "readlink")

    #we need commands for user/group management if it is an agent installation and not update
    if [ $update_agent -eq 0 ] ; then
        WHICH_COMMANDS+=("groupadd" "useradd" "userdel" "groupdel")
    fi

    MISSING_COMMANDS=()  #array to hold missing commands

    #loop through the commands and find the missing commands
    for COMMAND in "${WHICH_COMMANDS[@]}" ; do
        if [ "$(type -P $COMMAND 2>/dev/null)" == "" ] ; then
            MISSING_COMMANDS+=("$padding Cannot locate command '$COMMAND'")
        fi
    done

    #print out and exit if there are any commands missing
    if [ "${#MISSING_COMMANDS[@]}" != "0" ] ; then
        echo -e "Error: Command dependency check failed\n$(IFS=$'\n'; echo "${MISSING_COMMANDS[*]}")" >&2
        exit $SCRIPT_ERR_COMMAND_NOT_FOUND
    fi

    RET=$("$python_binary" agent/bin/check_dependency.py 2>&1)  #execute the script to find out any missing modules
    RET_CODE=$?

    if [[ $RET_CODE -eq $SCRIPT_ERR_SUCCESS && "$RET" != "Success" ]] ; then  #is python really a python binary. check the output to validate it
        echo "Error: '$python_binary' is not a valid python binary" >&2
        exit $SCRIPT_ERR_INVALID_PYTHON
    elif [ $RET_CODE -ne $SCRIPT_ERR_SUCCESS ] ; then  #dependency check failed
        echo "Error: Python dependency check failed" >&2
        echo -e $RET | (while read LINE; do echo "$padding $LINE" >&2; done)  #print the missing modules with some padding

        #cleanup the temp files generated while performing python dependency check
        rm -rf *.pyc
        find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1

        exit $RET_CODE
    fi

    #cleanup the temp files generated while performing python dependency check
    rm -rf *.pyc
    find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1
}

#function to export environment variables stored in $env_vars
export_env_var()
{
    ERROR_EN_VARS=()  #array to hold erroneous JSON objects for env vars

    for ENV_VAR in "${env_vars[@]}" ; do
        TEMP_OUTPUT=$("$python_binary" agent/bin/configure.py -a "add" -k "env" -v "$ENV_VAR" "$install_path/etc/config.json" 2>&1)

        #add to error list if it failed
        if [ $? -ne 0 ] ; then
            ERROR_EN_VARS=("${ERROR_EN_VARS[@]}" "$padding $ENV_VAR - ${TEMP_OUTPUT#Error: }")
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
    if [ "$1" == "1" ] ; then
        "$python_binary" agent/bin/configure.py -a "set" -k "agentVersion" -v "\"$version\"" -n "$install_path/etc/agent.json"
        "$python_binary" agent/bin/configure.py -a "set" -k "apiUrl" -v "\"$api_url\"" -n "$install_path/etc/agent.json"
    else
        #agent.json config
        CONFIG="\"orgToken\": \"$org_token\", \"apiUrl\": \"$api_url\", \"agentVersion\": \"$version\", \"name\": \"$host_name\", \"ref\": \"$install_source\""

        #add category if specified
        if [ "$category" != "" ] ; then
            CONFIG="$CONFIG, \"category\": \"$category\""
        fi

        #add agent id if specified
        if [ "$agent_id" != "" ] ; then
            CONFIG="$CONFIG, \"_id\": \"$agent_id\""
        fi

        "$python_binary" agent/bin/configure.py -a "set" -k "" -v "{$CONFIG}" -n "$install_path/etc/agent.json"  #set the configuration
        export_env_var  #export the environment variables specified
    fi

    #specify the python binary in the control script and uninstaller
    TEMP_VAR="$(echo "$python_binary" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/python/\"$TEMP_VAR\"/'"
    eval sed "$ARGS" "\"$install_path/etc/init.d/sealion\""
    eval sed "$ARGS" "\"$install_path/uninstall.sh\""
}

#set the install path
install_path=$(eval echo "$install_path")  #evaluate the path to resolve symbols like ~
install_path=$([[ "$install_path" != "" && ${install_path:0:1} != "/" ]] && echo "$(pwd)/$install_path" || echo "$install_path")  #absolute path
install_path=${install_path%/}  #remove / from the end

cd "$script_base_dir"  #move to the script base dir so that all paths can be found
check_dependency  #perform dependency check

#export https_proxy env
if [ "$proxy" != "" ] ; then
    env_vars=("${env_vars[@]}" "{\"https_proxy\": \"$proxy\"}")
fi

#export no_proxy env
if [ "$no_proxy" != "" ] ; then
    env_vars=("${env_vars[@]}" "{\"no_proxy\": \"$no_proxy\"}")
fi

SERVICE_FILE="$install_path/etc/init.d/sealion"  #service file for the agent

#check for existence of evil twin
if [ -f "$install_path/bin/sealion-node" ] ; then
    sealion_node_found=1
fi

if [ $update_agent -eq 0 ] ; then  #if this is a fresh install
    if [[ $EUID -ne 0 ]]; then  #run install script as root as it require some privileged operations like creating user/group etc
        echo "Error: You need to run this as root" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi

    #create install directory
    mkdir -p "$install_path/var/log"

    #error check
    if [ $? -ne 0 ] ; then
        echo "Error: Cannot create installation directory at '$install_path'" >&2
        exit $SCRIPT_ERR_FAILED_DIR_CREATE
    else
        echo "Install directory created at '$install_path'"
    fi

    chmod +x "$install_path"

    #create sealion group
    if [ "$(grep "^$user_name" /etc/group)" == "" ] ; then
        groupadd -r $user_name >/dev/null 2>&1
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create $user_name group" >&2
            exit $SCRIPT_ERR_FAILED_GROUP_CREATE
        else
            echo "Group $user_name created"
        fi
    else
        echo "Group $user_name already exists"
    fi

    #check for sealion user
    id $user_name >/dev/null 2>&1

    #create sealion user if it doesn't exists
    if [ $? -ne 0 ] ; then
        useradd -rM -g $user_name $user_name >/dev/null 2>&1
        
        if [ $? -ne 0 ] ; then
            echo "Error: Cannot create user $user_name" >&2
            exit $SCRIPT_ERR_FAILED_USER_CREATE
        else
            echo "User $user_name created"
        fi
    else
        echo "User $user_name already exists"
    fi
else
    #update should run as sealion user only
    if [ "$(id -u -n)" != "$user_name" ] ; then
        echo "Error: You need to run this as $user_name user" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi

    #validate the install path by checking the presence of service file
    #if this is an update from SeaLion node agent, then ignore it
    if [[ ! -f "$SERVICE_FILE" && $sealion_node_found -eq 0 ]] ; then
        echo "Error: '$install_path' is not a valid sealion installation directory" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi
fi

#remove the evil twin
if [ $sealion_node_found -eq 1 ] ; then
    echo "Removing sealion-node..."
    "$install_path/etc/sealion" stop >/dev/null 2>&1  #stop the node agent

    #rename the node agent log file
    find "$install_path/var/log" -mindepth 1 -maxdepth 1 -type f -regextype sed ! -regex '\(.*/update\.log\)\|\(.*/.\+\.old\..\+\)' -exec mv "{}" "$(mktemp -u {}.old.XXXX)" \; 1>/dev/null 2>&1
    
    #remove all the files except var/log/*
    find "$install_path/var" -mindepth 1 -maxdepth 1 ! -name 'log' -exec rm -rf "{}" \; 1>/dev/null 2>&1
    find "$install_path" -mindepth 1 -maxdepth 1 ! -name 'var' ! -name 'tmp' -exec rm -rf "{}" \; >/dev/null 2>&1
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

if [ $update_agent -eq 0 ] ; then  #if it is not an update
    #remove everything except var folder and copy the new files
    find "$install_path" -mindepth 1 -maxdepth 1 ! -name 'var' -exec rm -rf "{}" \; >/dev/null 2>&1
    cp -r agent/* "$install_path"

    setup_config  #create the configuration
    chown -R $user_name:$user_name "$install_path"  #change ownership
    echo "Sealion agent installed successfully"    

    #create service if agent is installed at default location
    if [[ "$install_path" == "$default_install_path" ]] ; then
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
    if [ $sealion_node_found -eq 1 ] ; then  #if updating sealion node
        cp -r agent/* "$install_path"  #copy the files
        setup_config  #create configuration

        #since update is run as unprivileged sealion user, we wont be able to modify /etc/sealion
        #instead convert the sealion node service file to point it to the new service file.
        #in effect it becomes /etc/sealion -> install_path/etc/sealion -> install_path/etc/init.d/sealion
        ln -sf "$SERVICE_FILE" "$install_path/etc/sealion"
    else
        #remove all files except var/ etc/ and tmp/ and copy files except etc/
        find "$install_path" -mindepth 1 -maxdepth 1 ! -name 'var' ! -name 'etc' ! -name 'tmp' -exec rm -rf "{}" \; >/dev/null 2>&1
        find agent/ -mindepth 1 -maxdepth 1 ! -name 'etc' -exec cp -r {} "$install_path" \;

        setup_config 1 #update the agent version and api url in agent.json
    fi

    echo "Sealion agent updated successfully"
fi

echo "Starting agent..."
"$SERVICE_FILE" start
RET=$?

if [[ $update_agent -eq 0 && $RET -eq 0 ]] ; then
    echo "Find more info at '$install_path/README'"
    URL="$(echo "$api_url" | sed 's/api\(\.\|-\)//')"
    echo "Please continue on $URL"
fi

exit $RET
