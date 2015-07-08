#!/usr/bin/env bash

#Install/update script for SeaLion agent

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found
PATH="${PATH}:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"  #common paths found in various linux distros

#script directory
script_base_dir=$(readlink -f "$0")
script_base_dir=${script_base_dir%/*}

source "${script_base_dir}/helper.sh"  #import utility functions

#Function to print usage info
#Arguments
#   $1 - whether to print the whole help or just the prompt
#Returns 0
usage() {
    if [[ "$1" != "1" ]] ; then
        echo "Run '${0} --help' for more information"
        return 0
    fi

    local usage_info="Usage: ${0} [options] <organization token>\nOptions:\n"
    usage_info="${usage_info} -o,                      Organization token; kept for backward compatibility\n"
    usage_info="${usage_info} -c,  --category <arg>    Category name under which the server to be registered\n"
    usage_info="${usage_info} -H,  --host-name <arg>   Server name to be used\n"
    usage_info="${usage_info} -x,  --proxy <arg>       Proxy server details\n"
    usage_info="${usage_info} -p,  --python <arg>      Path to Python binary used for executing agent code\n"
    usage_info="${usage_info} -e,  --env <arg>, ...    JSON document representing the environment variables to be exported\n"
    usage_info="${usage_info}      --no-create-user    Do not create 'sealion' user; instead use current user to run agent\n"
    usage_info="${usage_info} -h,  --help              Display this information"
    echo -e "$usage_info"
    return 0
}

#Function to install service
#Returns 0 on success; 1 on error
install_service() {
    local rc_path rc_index service_paths=()
    local symlink_paths=(K S S S S K)  #symlinks for each rc path
    local init_d_path=$(find /etc/ -type d -name init.d)  #inti.d path
    local rc_path_count="${#symlink_paths[@]}"

    #find all rc paths
    for (( i = 0 ; i < $rc_path_count ; i++ )) ; do
        rc_path=$(find /etc/ -type d -name "rc$(( i + 1 )).d")
        [[ "$rc_path" == "" ]] && break
        rc_paths=("${rc_paths[@]}" "$rc_path")
    done
    
    #if init.d is not found or rc paths are missing
    if [[ "$init_d_path" == "" || "${#rc_paths[@]}" != "$rc_path_count" ]] ; then
        echo "Error: Cannot create service 'sealion'. Could not locate init.d/rc directories" >&2
        echo "Use '${service_file}' to control sealion"
        return 1
    fi

    #create a symlink to the control script. the same script can be used directly to control the agent
    ln -sf "$service_file" "${init_d_path}/sealion"

    #loop through and update rc paths
    for (( i = 0 ; i < $rc_path_count ; i++ )) ; do 
        rc_path="${rc_paths[${i}]}/${symlink_paths[${i}]}99sealion"
        ln -sf "$service_file" "$rc_path"
        
        if [[ $? -ne 0 ]] ; then
            echo "Error: Cannot create service 'sealion'. Unable to update '${rc_path}' file" >&2
            echo "Use '${service_file}' to control sealion"
            return 1
        fi
    done
    
    echo "Service 'sealion' created"
    return 0  #success
}

#Function to check command and python module dependencies
#Terminates the script on error
check_dependency() {
    #check if python binary is valid
    type "$python_binary" >/dev/null 2>&1
    
    if [[ $? -ne 0 ]] ; then
        echo "Error: Could not locate Python binary" >&2
        exit $SCRIPT_ERR_INVALID_PYTHON
    fi
    
    local which_commands missing_items ret_code

    #various commands required for installer and the agent
    #we also need commands for user/group management if it is an agent installation and not update
    which_commands=("sed" "find" "chmod" "bash" "/usr/bin/env")
    [[ $update_agent -eq 0 && $create_user -eq 1 ]] && which_commands=("${which_commands[@]}" "groupadd" "useradd" "userdel" "groupdel" "chown")

    missing_items=$(check_for_commands "${which_commands[@]}")

    if [[ $? -ne 0 ]] ; then
        echo "Error: Command dependency check failed" >&2
        echo -e $missing_items | (while read line; do echo "${padding}${line}" >&2; done)  #print the missing commands with some padding
        exit $SCRIPT_ERR_COMMAND_NOT_FOUND
    fi

    missing_items=$("$python_binary" agent/bin/check_dependency.py 2>&1)  #execute the script to find out any missing modules
    ret_code=$?

    if [[ $ret_code -eq $SCRIPT_ERR_SUCCESS && "$missing_items" != "Success" ]] ; then  #is python really a python binary. check the output to validate it
        echo "Error: '${python_binary}' is not a valid Python binary" >&2
        exit $SCRIPT_ERR_INVALID_PYTHON
    elif [[ $ret_code -ne $SCRIPT_ERR_SUCCESS ]] ; then  #dependency check failed
        echo "Error: Python dependency check failed" >&2
        echo -e $missing_items | (while read line; do echo "${padding}${line}" >&2; done)  #print the missing modules with some padding

        #cleanup the temp files generated while performing python dependency check
        rm -rf *.pyc
        find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1

        exit $ret_code
    fi

    #cleanup the temp files generated while performing python dependency check
    rm -rf *.pyc
    find . -type d -name '__pycache__' -exec rm -rf {} \; >/dev/null 2>&1
}

#Function to export environment variables stored in $env_vars
export_env_vars() {
    local export_errors=()  #array to hold erroneous JSON objects for env vars

    for env_var in "${env_vars[@]}" ; do
        local output=$("${install_path}/bin/jsonfig.py" -a "add" -k "env" -v "$env_var" "${install_path}/etc/config.json" 2>&1)

        #add to error list if it failed
        [[ $? -ne 0 ]] && export_errors=("${export_errors[@]}"  "${padding}${env_var} - ${output#Error: }")
    done

    #print any errors as warnings
    if [[ "${#export_errors[@]}" != "0" ]] ; then
        echo "Warning: Failed to export the folloing environment variables" >&2
        echo -e $(IFS=$'\n'; echo "${export_errors[*]}")
    fi
}

#Function to setup the configuration for the agent
#Arguments
#   $1 - update api url and agent version only in agent.json
setup_config() {
    local config temp_var args
    temp_var=$(type -p "$python_binary")  #get the location of the python binary given

    #compare the default python location with the python binary given
    #if no match, then specify then update the shebang in python scripts to use the given interpreter
    if [[ "$(type -p python)" != "$temp_var" ]] ; then
        temp_var="$(sed 's/[^-A-Za-z0-9_]/\\&/g' <<<${python_binary})"
        args="-i 's/\\(^#\\!.\\+\\s\\)\\(.*$\\)/\\1${temp_var}/'"

        for file in $(find "${install_path}/bin/" -name '*.py') ; do
            eval sed $args "$file"
        done
    fi

    if [[ "$1" == "1" ]] ; then
        "${install_path}/bin/jsonfig.py" -a "set" -k "agentVersion" -v "\"$version\"" -n "${install_path}/etc/agent.json"
        "${install_path}/bin/jsonfig.py" -a "set" -k "apiUrl" -v "\"$api_url\"" -n "${install_path}/etc/agent.json"

        #as we keep adding modules, we need to include them for logging 
        config=$("${install_path}/bin/jsonfig.py" -k "logging:modules" -n agent/etc/config.json 2>/dev/null)
        [[ "$config" != "" ]] && "${install_path}/bin/jsonfig.py" -a "add" -k "logging:modules" -v "$config" "${install_path}/etc/config.json"
    else
        #agent.json config
        config="\"orgToken\": \"${org_token}\", \"apiUrl\": \"${api_url}\", \"agentVersion\": \"${version}\", \"name\": \"${host_name}\", \"ref\": \"${install_source}\""
        [[ "$category" != "" ]] && config="${config}, \"category\": \"${category}\""
        [[ "$agent_id" != "" ]] && config="${config}, \"_id\": \"${agent_id}\""
        
        "${install_path}/bin/jsonfig.py" -a "set" -k "" -v "{$config}" -n "${install_path}/etc/agent.json"  #set the configuration
        export_env_vars  #export the environment variables specified

        #if the user specified, set that in the config
        [[ $create_user -eq 0 ]] && "${install_path}/bin/jsonfig.py" -a "set" -k "user" -v "\"${user_name}\"" "${install_path}/etc/config.json" 2>&1
    fi
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

#config variables, they should be updated while building the tarball
api_url="<api-url>"
version="<version>"

user_name="sealion"  #username for the agent
create_user=1  #whether to create the user identified by user_name
python_binary="python"  #default python binary
default_install_path="/usr/local/sealion-agent"  #default install directory
sealion_node_found=0  #evil twin
update_agent=0  #install or update

#setup variables
org_token= category= agent_id= install_path=
host_name=$(hostname) proxy=$https_proxy no_proxy=$no_proxy
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
opt_parse i:o:c:H:x:p:a:r:v:e:h "category= host-name= proxy= python= env= no-create-user help" options args "$@"

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
            env_vars=("${env_vars[@]}" "$option_arg")
            ;;
        no-create-user)
            user_name=$(id -u -n)  #run as the current user
            create_user=0  #do not create the user
            ;;
        h|help)
            usage 1 ; exit $SCRIPT_ERR_SUCCESS
            ;;
    esac
done

#there should be an organization token
if [[ "$org_token" == "" ]] ; then
    echo "Please specify an organization token" >&2
    usage ; exit $SCRIPT_ERR_INVALID_USAGE
fi

#if no install path is set, we will need to fill the default
if [[ "$install_path" == "" ]] ; then
    #if we have a user specified, set install path under home directory of the user
    if [[ $create_user -eq 0 ]] ; then
        install_path=$(eval echo "~${user_name}/sealion-agent")

        if [[ "$install_path" == "~${user_name}/sealion-agent" ]] ; then
            echo "Error: Cannot find the home directory of '${user_name}'" >&2
            exit $SCRIPT_ERR_FAILED_DIR_CREATE
        fi
    else
        install_path=$default_install_path
    fi
fi

#set the absolute path for installation
install_path=$(eval echo "$install_path")
[[ ${install_path:0:1} != "/" ]] && install_path="$(pwd)/${install_path}" 
[[ "${#install_path}" != "0" ]] && install_path=${install_path%/}  #remove / from the end

cd "$script_base_dir"  #move to the script base dir so that all paths can be found
check_dependency  #perform dependency check
[[ "$proxy" != "" ]] && env_vars=("${env_vars[@]}" "{\"https_proxy\": \"${proxy}\"}")  #export proxy
[[ "$no_proxy" != "" ]] && env_vars=("${env_vars[@]}" "{\"no_proxy\": \"${no_proxy}\"}")  #export no_proxy
service_file="${install_path}/etc/init.d/sealion"  #service file for the agent
[[ -f "${install_path}/bin/sealion-node" ]] && sealion_node_found=1  #check for existence of evil twin

if [[ $update_agent -eq 0 ]] ; then  #if this is a fresh install
    #run install script as root as it require some privileged operations like creating user/group etc
    if [[ $create_user -eq 1 && $EUID -ne 0 ]] ; then  
        echo "Error: You need to run this script as 'root'" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi

    mkdir -p "${install_path}/var/log" >/dev/null 2>&1  #create install directory

    #error check
    if [[ $? -ne 0 ]] ; then
        echo "Error: Cannot create installation directory at '${install_path}'" >&2
        exit $SCRIPT_ERR_FAILED_DIR_CREATE    
    fi

    #check for write permission to install path
    if [[ ! -w "$install_path" ]] ; then
        echo "Error: No write permission to '${install_path}'" >&2
        exit $SCRIPT_ERR_FAILED_DIR_CREATE
    fi

    echo "Install directory created at '${install_path}'"
    chmod +x "$install_path"

    #should we create the user and group
    if [[ $create_user -eq 1 ]] ; then
        #check for existence of group
        group_exists=0 ; while read line ; do 
            [[ "${line%%:*}" == "$user_name" ]] && group_exists=1 && break
        done </etc/group

        #create sealion group
        if [[ $group_exists -eq 0 ]] ; then
            groupadd -r $user_name >/dev/null 2>&1

            if [[ $? -ne 0 ]] ; then
                echo "Error: Cannot create '${user_name}' group" >&2
                exit $SCRIPT_ERR_FAILED_GROUP_CREATE
            else
                echo "Group '${user_name}' created"
            fi
        else
            echo "Group '${user_name}' already exists"
        fi

        #check for sealion user
        id $user_name >/dev/null 2>&1

        #create sealion user if it doesn't exists
        if [[ $? -ne 0 ]] ; then
            useradd -rM -g $user_name $user_name >/dev/null 2>&1

            if [[ $? -ne 0 ]] ; then
                echo "Error: Cannot create user '${user_name}'" >&2
                exit $SCRIPT_ERR_FAILED_USER_CREATE
            else
                echo "User '${user_name}' created"
            fi
        else
            echo "User '${user_name}' already exists"
        fi
    fi
else
    #try to find out whether a user is defined in the config
    if [[ -f "agent/bin/jsonfig.py" ]] ; then
        temp_user_name=$("$python_binary" agent/bin/jsonfig.py -k "user" "${install_path}/etc/config.json" 2>/dev/null)
        temp_user_name="${temp_user_name#\"}"
        temp_user_name="${temp_user_name%\"}"
        [[ "$temp_user_name" != "" ]] && user_name=$temp_user_name
    fi

    #update should run as the given user only
    if [[ "$(id -u -n)" != "$user_name" ]] ; then
        echo "Error: You need to run this script as '${user_name}'" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi

    #validate the install path by checking the presence of service file
    #if this is an update from SeaLion node agent, then ignore it
    if [[ ! -f "$service_file" && $sealion_node_found -eq 0 ]] ; then
        echo "Error: '${install_path}' is not a valid SeaLion agent installation directory" >&2
        exit $SCRIPT_ERR_INVALID_USAGE
    fi

    #check for the write permission to the install path
    if [[ ! -w "$install_path" ]] ; then
        echo "Error: No write permission to '${install_path}'" >&2
        exit $SCRIPT_ERR_FAILED_DIR_CREATE
    fi
fi

#remove the evil twin
if [[ $sealion_node_found -eq 1 ]] ; then
    echo "Removing sealion-node..."
    "${install_path}/etc/sealion" stop >/dev/null 2>&1  #stop the node agent

    #rename the node agent log file
    find "${install_path}/var/log" -mindepth 1 -maxdepth 1 -type f -regextype sed ! -regex '\(.*/update\.log\)\|\(.*/.\+\.old\..\+\)' -exec mv "{}" "$(mktemp -u {}.old.XXXX)" \; 1>/dev/null 2>&1
    
    #remove all the files except var/log/*
    find "${install_path}/var" -mindepth 1 -maxdepth 1 ! -name 'log' -exec rm -rf "{}" \; 1>/dev/null 2>&1
    find "$install_path" -mindepth 1 -maxdepth 1 ! -name 'var' ! -name 'tmp' -exec rm -rf "{}" \; >/dev/null 2>&1
fi

#stop the agent if it is an update or re-install
if [[ -f "$service_file" ]] ; then
    echo "Stopping agent..."
    "$service_file" stop
    ret_status=$?

    #exit if the user interrupted the operation or the command was not found
    [[ $ret_status -eq 34 || $ret_status -eq 127 ]] && exit ret_status
fi

echo "Copying files..."

if [[ $update_agent -eq 0 ]] ; then  #if it is not an update
    #remove everything except var directory and copy the new files
    find "$install_path" -mindepth 1 -maxdepth 1 ! -name 'var' -exec rm -rf "{}" \; >/dev/null 2>&1
    cp -r agent/* "$install_path"

    setup_config  #create the configuration
    [[ $create_user -eq 1 ]] && chown -R "${user_name}:${user_name}" "$install_path"  #change ownership if required
    echo "SeaLion agent installed successfully"    

    #create service if agent is installed at default location and running as root
    if [[ $EUID -eq 0 && "$install_path" == "$default_install_path" ]] ; then
        install_service
    else
        echo "Use '${service_file}' to control sealion"
    fi
else  #update
    if [[ $sealion_node_found -eq 1 ]] ; then  #if updating sealion node
        cp -r agent/* "$install_path"  #copy the files
        setup_config  #create configuration

        #since update is run as unprivileged sealion user, we wont be able to modify /etc/sealion
        #instead convert the sealion node service file to point it to the new service file.
        #in effect it becomes /etc/sealion -> install_path/etc/sealion -> install_path/etc/init.d/sealion
        ln -sf "$service_file" "${install_path}/etc/sealion"
    else
        #remove all files except var/ etc/ and tmp/ and copy files except etc/
        find "$install_path" -mindepth 1 -maxdepth 1 ! -name 'var' ! -name 'etc' ! -name 'tmp' -exec rm -rf "{}" \; >/dev/null 2>&1
        find agent/ -mindepth 1 -maxdepth 1 ! -name 'etc' -exec cp -r {} "$install_path" \;

        setup_config 1 #update the agent version and api url in agent.json
    fi

    echo "SeaLion agent updated successfully"
fi

echo "Starting agent..."
"$service_file" start
ret_status=$?

#finishing quote
if [[ $update_agent -eq 0 && $ret_status -eq 0 ]] ; then
    echo "Find more info at '${install_path}/README'"
    echo "Please continue on $(sed 's/api\(\.\|-\)//' <<<${api_url})"
fi

exit $ret_status
