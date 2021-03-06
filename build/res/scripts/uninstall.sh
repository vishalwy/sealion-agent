#!/usr/bin/env bash

#Uninstall script for SeaLion agent
#If not run as root, then it removes the files except the log and this script, otherwise a complete uninstall 

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found
PATH="${PATH}:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"  #common paths found in various linux distros

#directory of the script
script_base_dir=$(readlink -f "$0")
script_base_dir=${script_base_dir%/*}

#command line option for unregister script
cmdline_options="<options>"

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
        rc_paths=("${rc_paths[@]}" "$rc_path")
    done
    
    #if init.d is not found or rc paths are missing
    if [[ "$init_d_path" == "" || "${#rc_paths[@]}" != "$rc_path_count" ]] ; then
        echo "Error: Cannot destroy service 'sealion'. Could not locate init.d/rc directories" >&2
        return 1
    fi

    #loop through and remove rc paths
    for (( i = 0 ; i < $rc_path_count ; i++ )) ; do        
        rc_path="${rc_paths[${i}]}/${symlink_paths[${i}]}99sealion"
        rm -f "$rc_path"

        if [[ $? -ne 0 ]] ; then
            echo "Error: Cannot destroy service 'sealion'. Failed to remove ${rc_path} file" >&2
            return 1
        fi
    done

    rm -f "${init_d_path}/sealion"  #remove init.d path
        
    if [[ $? -ne 0 ]] ; then
        echo "Error: Cannot destroy service 'sealion'. Failed to remove ${init_d_path}/sealion file" >&2
        return 1
    fi
    
    echo "Service 'sealion' destroyed"
    return 0
}

user_name="sealion"  #username for the agent
user_delete=1  #whether to delete the user identified by user_name
cd "$script_base_dir"  #move to the script base dir so that all paths can be found

#try to find out whether a user is defined in the config
if [[ -f "bin/jsonfig" ]] ; then
    temp_user_name=$(bin/jsonfig -k "user" etc/config.json 2>/dev/null)
    temp_user_name="${temp_user_name#\"}"
    temp_user_name="${temp_user_name%\"}"
    
    #if we find a user_name, it means we should not delete the user or group
    if [[ "$temp_user_name" != "" ]] ; then
        user_name=$temp_user_name
        user_delete=0
    fi
fi

#validate current user
if [[ "$(id -u -n)" != "$user_name" && $EUID -ne 0 ]] ; then
    echo "Error: You need to run this script as either 'root' or '${user_name}'" >&2
    exit 1
fi

#check for write permission 
if [[ ! -w "$script_base_dir" ]] ; then
    echo "Error: No write permission to '${script_base_dir}'" >&2
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
if [[ -f "bin/unregister" ]] ; then
    echo "Unregistering agent..."
    bin/unregister ${cmdline_options} >/dev/null 2>&1
    [[ $? -ne 0 ]] && echo "Failed unregister agent; please remove it from SeaLion web interface"
fi

#if install dir is the default install dir, then only we will remove user, group and service
if [[ $EUID -eq 0 && "$script_base_dir" == "/usr/local/sealion-agent" ]] ; then
    #should we delete the user and group
    if [[ $user_delete -eq 1 ]] ; then
        id $user_name >/dev/null 2>&1

        #kill all the process and remove the user sealion
        if [[ $? -eq 0 ]] ; then
            pkill -KILL -u $user_name
            userdel $user_name
            echo "User '${user_name}' removed"
        fi

        #check for existence of group
        group_exists=0 ; while read line ; do 
            [[ "${line%%:*}" == "$user_name" ]] && group_exists=1 && break
        done </etc/group

        #remove the group
        if [[ $group_exists -eq 1 ]] ; then
            groupdel $user_name
            echo "Group '${user_name}' removed"
        fi
    fi

    uninstall_service  #uninstall the service
fi

if [[ $EUID -eq 0 || $user_delete -eq 0 ]] ; then
    #remove all the files if the current user is root or the script is running a user that the installer did not create
    echo "Removing files..."
    cd ../
    rm -rf "$script_base_dir"
else
    #we remove all the files except var/log and uninstall.sh. 
    #we wont be able to remove the user, group and service as it requires super privileges
    echo "Removing files except logs, README and uninstall.sh"
    find var -mindepth 1 -maxdepth 1 ! -name 'log' ! -name 'crash' -exec rm -rf {} \;
    find . -mindepth 1 -maxdepth 1 -type d ! -name 'var' -exec rm -rf {} \;
fi

echo "Sealion agent uninstalled successfully"