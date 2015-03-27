#!/usr/bin/env bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found

#script directory
script_base_dir=$(readlink -f "$0")
script_base_dir=${script_base_dir%/*}

source "$script_base_dir/res/scripts/helper.sh"  #import utility functions

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

    local usage_info="Usage: $0 [options]\nOptions:\n"
    usage_info+=" -o,\t--org-token <arg>  \tOrganization token to be used\n"
    usage_info+=" -c,\t--category <arg>   \tCategory name under which the server to be registered\n"
    usage_info+=" -H,\t--host-name <arg>  \tServer name to be used\n"
    usage_info+=" -x,\t--proxy <arg>      \tProxy server details\n"
    usage_info+=" -a,\t--api-url <arg>    \tAPI URL for the agent; default to 'https://api-test.sealion.com'\n"
    usage_info+=" -v,\t--version <arg>    \tAgent version to be used\n"
    usage_info+=" -h,\t--help             \tDisplay this information"
    echo -e "$usage_info"
    return 0
}

#script variables
org_token= version= category= 
host_name=$(hostname) proxy=$https_proxy no_proxy=$no_proxy
api_url="https://api-test.sealion.com"  #default to test

#parse command line
opt_parse o:c:H:x:a:v:h "org-token= category= host-name= proxy= api-url= version= help" options args "$@"

#if parsing failed print the usage and exit
if [[ $? -ne 0 ]] ; then
    echo "$options" >&2
    usage ; exit 1
fi

#loop through the options
for option_index in "${!options[@]}" ; do
    [[ $(( option_index % 2 )) -ne 0 ]] && continue  #skip option arguments
    option_arg=${options[$(( option_index + 1 ))]}  #option argument for the current option

    #find the proper option and perform the action
    case "${options[${option_index}]}" in
        o\org-token)
            org_token=$option_arg
            ;;
        c|category)
            category=$option_arg
            ;;
        H|host-name)
            host_name=$Ooption_arg
            ;;
        x|proxy)
            proxy=$option_arg
            ;;
        a|api-url)
            api_url=$option_arg
            ;;
        v|version)
            version=$option_arg
            ;;
        h|help)
            usage 1 ; exit 0
            ;;
    esac
done

#there should be an organization token
if [[ "$org_token" == '' ]] ; then
    echo "Please specify an organization token" >&2
    usage ; exit 1
fi

#you need to specify agent version
if [[ "$version" == "" ]] ; then
    echo "Please specify the agent version" >&2
    usage ; exit 1
fi

#copy etc from res to code
cp -r "${script_base_dir}/res/etc" "${script_base_dir}/../code/"

#agent.json config
config="\"orgToken\": \"${org_token}\", \"apiUrl\": \"{$api_url}\", \"agentVersion\": \"${version}\", \"name\": \"${host_name}\", \"ref\": \"$REF\""
[[ "$category" != "" ]] && config+=", \"category\": \"$category\""  #add category if specified

"${script_base_dir}/../code/bin/configure.py" -a "set" -k "" -v "{$config}" -n "${script_base_dir}/../code/etc/agent.json"  #set the configuration
proxy_vars=()  #array to hold proxy vars
[[ "$proxy" != "" ]] && proxy_vars+=("{\"https_proxy\": \"$proxy\"}")  #export https_proxy
[[ "$no_proxy" != "" ]] && proxy_vars=("${proxy_vars[@]}" "{\"no_proxy\": \"$no_proxy\"}")  #export no_proxy

#update config.json with proxy variables
config=$(IFS=', '; echo "${proxy_vars[*]}")
[[ "$config" != "" ]] && "${script_base_dir}/../code/bin/configure.py" -a "add" -k "env" -v "[$config]" "${script_base_dir}/../code/etc/config.json"

#update config.json with logging level
"${script_base_dir}/../code/bin/configure.py" -a "set" -k "logging:level" -v "\"debug\"" "${script_base_dir}/../code/etc/config.json"

echo "Generated config files at ${script_base_dir}/../code/etc"

