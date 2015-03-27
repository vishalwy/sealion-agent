#!/usr/bin/env bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found

#directory of the script
script_base_dir=$(readlink -f "$0")
script_base_dir=${script_base_dir%/*}

#Function to uninstall service
#Returns 0 on success; 1 on error
uninstall_service() {
    local rc_path rc_index service_paths=()
    local symlink_paths=(K S S S S K)  #symlinks for each rc path
    local init_d_path=$(find /etc/ -type d -name init.d)  #inti.d path
    local rc_path_count="${#symlink_paths[@]}"

    #find all the rc paths
    for (( i = 0 ; i < $rc_path_count ; i++ )) ; do
        rc_path=$(find /etc/ -type d -name "rc$(( i + 1 )).d")
        [[ "$rc_path" == "" ]] && break
        rc_paths+=(rc_path)
    done
    
    #if init.d is not found or rc paths are missing
    if [[ "$init_d_path" == "" || "${#rc_paths[@]}" != "$rc_path_count" ]] ; then
        echo "Error: Could not locate init.d/rc directories" >&2
        return 1
    fi

    #loop through and remove rc paths
    for (( i = 0 ; i < $rc_path_count ; i++ )) ; do        
        rc_path="${rc_paths[$i]}/${symlink_paths[$i]}99sealion"
        rm -f "$rc_path"

        if [[ $? -ne 0 ]] ; then
            echo "Error: Failed to remove ${rc_path} file" >&2
            return 1
        fi
    done

    rm -f "${init_d_path}/sealion"  #remove init.d path
        
    if [[ $? -ne 0 ]] ; then
        echo "Error: Failed to remove ${init_d_path}/sealion file" >&2
        return 1
    fi
    
    return 0
}

user_name="sealion"  #username for the agent
cd "$script_base_dir"  #move to the script base dir so that all paths can be found

#validate current user
if [[ "$(id -u -n)" != "$user_name" && $EUID -ne 0 ]] ; then
    echo "Error: You need to run this script as either root or $user_name" >&2
    exit 1
fi

#use the service file to stop agent.
#service file may not be available if the user already removed the agent from the web interface
if [[ -f "etc/init.d/sealion" ]] ; then
    echo "Stopping agent..."
    etc/init.d/sealion stop
fi

#use unregister script to unregister the agent.
#the script may not be available if the user already removed the agent from the web interface
if [[ -f "bin/unregister.py" ]] ; then
    echo "Unregistering agent..."
    python bin/unregister.py >/dev/null 2>&1

    if [[ $? -ne 0 ]] ; then  #exit if unregistering the agent failed
        echo "Error: Failed to unregister agent" >&2
        exit 1
    fi
fi

if [[ $EUID -ne 0 ]]; then  #if not running as root user
    #we remove all the files except var/log and uninstall.sh. 
    #we wont be able to remove the user, group and service as it requires super privileges
    echo "Removing files except logs, README and uninstall.sh"
    find var -mindepth 1 -maxdepth 1 ! -name 'log' ! -name 'crash' -exec rm -rf {} \;
    find . -mindepth 1 -maxdepth 1 -type d ! -name 'var' -exec rm -rf {} \;
else
    #if install dir is the default install dir, then only we will remove user, group and service
    if [[ "$script_base_dir" == "/usr/local/sealion-agent" ]] ; then
        id $user_name >/dev/null 2>&1

        #kill all the process and remove the user sealion
        if [[ $? -eq 0 ]] ; then
            pkill -KILL -u $user_name
            userdel $user_name
            echo "User ${user_name} removed"
        fi

        id -g $user_name >/dev/null 2>&1

        #remove the group
        if [[ $? -eq 0 ]] ; then
            groupdel $user_name
            echo "Group ${user_name} removed"
        fi

        uninstall_service  #uninstall the service

        if [[ $? -ne 0 ]] ; then
            echo "Service sealion removed"
        fi  
    fi

    echo "Removing files..."
    cd /
    rm -rf "$script_base_dir"
fi

echo "Sealion agent uninstalled successfully"
