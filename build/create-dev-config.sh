#!/usr/bin/env bash

#Script to create configuration files to run the agent. Used for development purpose.

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found
PATH="${PATH}:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"  #common paths found in various linux distros

#script directory
script_base_dir=$(readlink -f "$0")
script_base_dir=${script_base_dir%/*}

source "${script_base_dir}/res/scripts/helper.sh"  #import utility functions

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
    usage_info="${usage_info} -c,  --category <arg>    Category name under which the server to be registered\n"
    usage_info="${usage_info} -H,  --host-name <arg>   Server name to be used\n"
    usage_info="${usage_info} -x,  --proxy <arg>       Proxy server details\n"
    usage_info="${usage_info} -a,  --api-url <arg>     API URL for the agent; default to 'api-test.sealion.com'\n"
    usage_info="${usage_info} -h,  --help              Display this information"
    echo -e "$usage_info"
    return 0
}

#script variables
org_token= category= host_name= proxy=
api_url="api-test.sealion.com"  #default to test

#parse command line
opt_parse c:H:x:a:h "category= host-name= proxy= api-url= help" options args "$@"

#if parsing failed print the usage and exit
if [[ $? -ne 0 ]] ; then
    echo "$options" >&2
    usage ; exit 1
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
        c|category)
            category=$option_arg
            ;;
        H|host-name)
            host_name=$option_arg
            ;;
        x|proxy)
            proxy=$option_arg
            ;;
        a|api-url)
            api_url=$option_arg
            ;;
        h|help)
            usage 1 ; exit 0
            ;;
    esac
done

#there should be an organization token
if [[ "$org_token" == "" ]] ; then
    echo "Please specify an organization token" >&2
    usage ; exit 1
fi

#copy etc from res to code
cp -r "${script_base_dir}/res/etc" "${script_base_dir}/../code/"

#agent.json config
[[ "$host_name" != "" ]] && sub_config="\"name\": \"${host_name}\""  #add host name if specified
config="\"orgToken\": \"${org_token}\", \"apiUrl\": \"https://${api_url}\", \"config\": {${sub_config}}"
[[ "$category" != "" ]] && config="${config}, \"category\": \"${category}\""  #add category if specified
"${script_base_dir}/../code/bin/jsonfig.py" -a "set" -k "" -v "{$config}" -n "${script_base_dir}/../code/etc/agent.json"  #set the configuration

#export https_proxy
"${script_base_dir}/../code/bin/jsonfig.py" -a "merge" -k "env" -v "{\"https_proxy\": \"${proxy}\"}" "${script_base_dir}/../code/etc/config.json"
"${script_base_dir}/../code/bin/jsonfig.py" -a "merge" -k "env" -v "{\"HTTPS_PROXY\": \"${proxy}\"}" "${script_base_dir}/../code/etc/config.json"

#update config.json with logging level
"${script_base_dir}/../code/bin/jsonfig.py" -a "set" -k "logging:level" -v "\"debug\"" "${script_base_dir}/../code/etc/config.json"

#update config.json to use current user
"${script_base_dir}/../code/bin/jsonfig.py" -a "set" -k "user" -v "\"$(id -u -n)\"" "${script_base_dir}/../code/etc/config.json"

echo "Generated config files at ${script_base_dir}/../code/etc"

