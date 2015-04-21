#!/usr/bin/env bash

#Single line install script for SeaLion agent.
#The script downloads the appropriate agent tarball, extracts it and then calls the actual installer.
#During agent update it logs stdout/stderr from the installer to a file.

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found
PATH="${PATH}:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"  #common paths found in various linux distros

source helper.sh   #import utility functions

#Function to print usage info
#Arguments
#   $1 - whether to print the whole help or just the prompt
#Returns 0
usage() {
    local bin="curl -s ${download_url} | sudo bash /dev/stdin"
    [[ "$0" != "/dev/stdin" ]] && bin="$0"

    if [[ "$1" != "1" ]] ; then
        echo "Run '${bin} --help' for more information"
        return 0
    fi

    local usage_info="Usage: ${bin} [options] <organization token>\nOptions:\n"
    usage_info+=" -o,\t                  \tOrganization token; kept for backward compatibility\n"
    usage_info+=" -c,\t--category <arg>  \tCategory name under which the server to be registered\n"
    usage_info+=" -H,\t--host-name <arg> \tServer name to be used\n"
    usage_info+=" -x,\t--proxy <arg>     \tProxy server details\n"
    usage_info+=" -p,\t--python <arg>    \tPath to Python binary used for executing agent code\n"
    usage_info+=" -e,\t--env <arg>, ...  \tJSON document representing the environment variables to be exported\n"
    usage_info+="    \t--no-create-user  \tDo not create 'sealion' user; use current user instead to run agent\n"
    usage_info+=" -h,\t--help            \tDisplay this information"
    echo -e "$usage_info"
    return 0
}

#Function to perform command dependency check
#Terminates the script on error
check_dependency() {
    local missing_items

    #check for commands
    missing_items=$(check_for_commands "sed" "tar" "bash" "grep" "mktemp")

    if [[ $? -ne 0 ]] ; then
        echo "Error: Command dependency check failed" >&2
        echo -e $missing_items | (while read line; do log_output "       ${line}" 2; done)  #print the missing commands with some padding
        [[ "$agent_id" != "" ]] && report_failure 6
        exit 123
    fi
}

#Function to call api url using the url caller
#Arguments:
#   $@ - parameters for the url caller
#Returns the url caller exit status
call_url() {
    local params=""

    for arg in "$@" ; do
        arg=${arg//\"/\\\"}
        params+=" \"${arg}\""
    done

    bash -c "${orig_url_caller} ${params}"
    return $?
}

#Function to continuously read from the input and log
#Arguments
#   $1 - output stream
read_and_log() {
    #blocking read with a timeout
    while read -t 300 line; do 
        log_output "$line" $1
    done
}

#Function to report failure reason so that server can send a mail to the user
#Arguments
#   $1 - reason for failure 
report_failure() {
    [[ "$agent_id" == "" ]] && return  #abort if no agent id is specified

    #make the request
    call_url -s $proxy -H "Content-Type: application/json" -X PUT -d "{\"reason\": \"${1}\"}" "${api_url}/orgs/${org_token}/agents/${agent_id}/updatefail" >/dev/null 2>&1
}

#Function to log the output in terminal as well as a file 
log_output() {
    local output=$1 stream=$2 stream_text="O"

    #write to output/error stream
    if [[ $stream -eq 2 ]] ; then
        echo $output >&2
        stream_text="E"
    else
        echo $output >&1
    fi

    #if file path is not set, then it is the first time the function is called
    if [[ "$update_log" == "" ]] ; then
        #set the destination based on the existence of the update.log file
        local destination="${install_path}/var/log"
        [[ -f "${destination}/update.log" ]] && destination+="/update.log"

        #if this is an update and destination is writable, 
        #then set the variable otherwise set the variable to a space so that the next time we dont have to perform all these
        if [[ "agent_id" != "" && -w "$destination" ]] ; then
            update_log="${install_path}/var/log/update.log"
        else
            update_log=" "
        fi
    fi

    [[ "$update_log" != " " ]] && echo $(date +"%F %T,%3N - ${stream_text}: ${output}") >>"$update_log"
    return 0
}

#config variables, they should be updated while building the tarball
api_url="<api-url>"
download_url="<agent-download-url>"

user_name="sealion"  #username for the agent
orig_url_caller=$([ "$URL_CALLER" != "" ] && echo "$URL_CALLER" || echo "curl")  #command for api url calls
unset -v URL_CALLER  #reset url caller so that child scripts wont inherit it

#setup variables
install_path="/usr/local/sealion-agent"  #install directory for the agent
temp_file_path="/tmp/sealion-agent.XXXX"  #template for the path where the agent installer will be downloaded
tmp_data_file="/tmp/sealion-agent.response.XXXX"  #temp file for api url response
proxy= agent_id= org_token=

#parse command line
opt_parse i:o:c:H:x:p:a:r:v:e:h "category= host-name= proxy= python= env= no-create-user help" options args "$@"

#if parsing failed print the usage and exit
if [[ $? -ne 0 ]] ; then
    echo "$options" >&2
    usage ; exit 125
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
        x|proxy)
            proxy="-x ${option_arg}"
            ;;
        a)
            agent_id=$option_arg
            ;;
        o)
            org_token=$option_arg
            ;;
        h|help)
            usage 1 ; exit 0
            ;;
    esac
done

#set the absolute path for installation
install_path=$(eval echo "$install_path")
[[ ${install_path:0:1} != "/" ]] && install_path="$(pwd)/${install_path}" 
[[ "${#install_path}" != "0" ]] && install_path=${install_path%/}  #remove / from the end

check_dependency  #perform command dependency check
tmp_data_file=$(mktemp "$tmp_data_file")  #create temp data file for api response
log_output "Getting agent installer details..."

#call the url and get the response
sub_url=$([ "$agent_id" != "" ] && echo "/agents/${agent_id}" || echo "")  #we need to include agent id also if this is an update
status=$(call_url -s $proxy -w "%{http_code}" -H "Content-Type: application/json" -o "$tmp_data_file" "${api_url}/orgs/${org_token}${sub_url}/agentVersion" 2>&1)

#check the return value and status code
if [[ $? -ne 0 || "$status" != "200" ]] ; then
    log_output "Error: Failed to get agent installer details; ${status}" 2
    rm -f "$tmp_data_file"
    exit 117
fi

#read the agent version and download url from the response
version=$(grep '"agentVersion"\s*:\s*"[^"]*"' "$tmp_data_file" -o | sed 's/"agentVersion"\s*:\s*"\([^"]*\)"/\1/')
tar_download_url=$(grep '"agentDownloadURL"\s*:\s*"[^"]*"' "$tmp_data_file" -o | sed 's/"agentDownloadURL"\s*:\s*"\([^"]*\)"/\1/')
rm -f "$tmp_data_file"  #we no longer require it

#if the major version is <= 2, means it requesting for node agent
if [[ "$(grep '^[0-9]\+' -o <<<${version})" -le "2" ]] ; then
    call_url -s $proxy "${download_url}/curl-install-node.sh" 2>/dev/null | bash /dev/stdin -t $tar_download_url "$@" 1> >( read_and_log ) 2> >( read_and_log 2 )
    status=$?
    sleep 2
    [[ $status -ne 0 ]] && report_failure $status
    exit $status
fi

#create directory for downloading agent installer
temp_file_path=$(mktemp -d "$temp_file_path")
temp_file_path=${temp_file_path%/}
tmp_file_name="${temp_file_path}/sealion-agent.tar.gz"

log_output "Downloading agent installer version ${version}..."
status=$(call_url -s $proxy -w "%{http_code}" -o "$tmp_file_name" $tar_download_url 2>&1)

#check return value and status code
if [[ $? -ne 0 || "$status" -ge "400" ]] ; then
    log_output "Error: Failed to download agent installer; ${status}" 2
    [[ "$status" -ge "400" ]] && report_failure 5
    
    if [[ -f "${install_path}/bin/sealion-node" && -f "${install_path}/etc/sealion" ]] ; then
        "${install_path}/etc/sealion" start
    fi

    rm -rf "$temp_file_path"
    exit 117
fi

#extract the agent installer tar
status=$(tar -xf "$tmp_file_name" --directory="$temp_file_path" 2>&1)

#check for tar extract failure 
if [[ $? -ne 0 ]] ; then
    log_output "Error: Failed to extract files; ${status}" 2
    rm -rf "$temp_file_path"
    exit 1
fi

#execute the installer script; 
#be sure to call it via bash to avoid getting permission denied on temp folder where script execution is not allowed
bash "${temp_file_path}/sealion-agent/install.sh" -r curl "$@" 1> >( read_and_log ) 2> >( read_and_log 2 )
status=$?
rm -rf "$temp_file_path"  #remove temp file as we no longer need them

#check for failure and report any error
if [[ "$agent_id" != "" && $status -ne 0 ]] ; then
    report_failure $status

    if [[ -f "${install_path}/bin/sealion-node" && -f "${install_path}/etc/sealion" ]] ; then
        "${install_path}/etc/sealion" start
    fi

    exit 123
fi

exit 0
