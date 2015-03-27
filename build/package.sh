#!/usr/bin/env bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found

#directory of the script
script_base_dir=$(readlink -f "$0")
script_base_dir=${script_base_dir%/*}

source "${script_base_dir}/res/scripts/helper.sh"  #import utility functions

#Function to print usage info
#Arguments
#   $1 - whether to print the whole help or just the prompt
#Returns 0
usage() {
    if [[ "$1" != "1" ]] ; then
        echo "Run '$0 --help' for more information"
        return 0
    fi

    local usage_info="Usage: $0 [options] <version>\nOptions:\n"
    usage_info+=" -d,\t--domain <arg> \tDomain for which the tarball to be generated; Default to 'sealion.com'\n"
    usage_info+=" -h,\t--help         \tDisplay this information"
    echo -e "$usage_info"
    return 0
}

#Function to import script into another script
#Arguments
#   $1 - source script
#   $2 - target script
import_script() {
    #sed escape import script name and extract only the file name
    local import_script_pattern="$(sed 's/[^-A-Za-z0-9_]/\\&/g' <<< ${1})"   
    import_script_pattern="${import_script_pattern##*/}"

    #import it by first reading the file after the source statement and then deleting the line
    local pattern="^\\s*source\\s\\+.*${import_script_pattern}.*$"
    local args="-i -e '/${pattern}/ r $1' -e '/${pattern}/d'"
    eval sed "$args" $2
}

#Function to update various details inside a script
#Arguments
#   $1 - script to update
set_script_details() {
    local temp_var args
    
    #set api url
    temp_var="$(sed 's/[^-A-Za-z0-9_]/\\&/g' <<< ${api_url})"
    args="-i 's/\\(^API\\_URL=\\)\\(\"[^\"]\\+\"\\)/\\1\"${temp_var}\"/i'"
    eval sed $args "$1"
    
    #set version
    temp_var="$(sed 's/[^-A-Za-z0-9_]/\\&/g' <<< ${version})"
    args="-i 's/\\(^VERSION=\\)\\(\"[^\"]\\+\"\\)/\\1\"${temp_var}\"/i'"
    eval sed $args "$1"

    #set agent download url
    temp_var="$(sed 's/[^-A-Za-z0-9_]/\\&/g' <<< ${agent_url})"
    args="-i 's/\\(^DOWNLOAD\\_URL=\\)\\(\"[^\"]\\+\"\\)/\\1\"${temp_var}\"/i'"
    eval sed $args "$1"

    #set registration url; applicable only for curl installer for node
    temp_var="$(sed 's/[^-A-Za-z0-9_]/\\&/g' <<< ${api_url}/agents)"
    args="-i 's/\\(^REGISTRATION\\_URL=\\)\\(\"[^\"]\\+\"\\)/\\1\"${temp_var}\"/i'"
    eval sed $args "$1"

    import_script res/scripts/helper.sh $1  #import the script
    chmod +x $1  #add exe flag
}

#Function to generate various scripts
generate_scripts() {
    #copy service script
    cp res/scripts/sealion "${build_target}/${output}/agent/etc/init.d/sealion"
    chmod +x "${build_target}/${output}/agent/etc/init.d/sealion"
    echo "Service script generated"

    #copy uninstall script
    cp res/scripts/uninstall.sh "${build_target}/${output}/agent/uninstall.sh"
    chmod +x "${build_target}/${output}/agent/uninstall.sh"
    echo "Uninstaller generated"

    #copy and update install script
    cp res/scripts/install.sh "${build_target}/${output}/install.sh"
    set_script_details "${build_target}/${output}/install.sh"
    echo "Installer generated"

    #copy and update curl install script
    cp res/scripts/curl-install.sh "${build_target}/curl-install.sh"
    set_script_details "${build_target}/curl-install.sh"
    echo "Curl installer generated"

    #copy and update curl install script for node
    cp res/scripts/curl-install-node.sh "${build_target}/curl-install-node.sh"
    set_script_details "${build_target}/curl-install-node.sh"
    echo "Curl installer for node generated"
    
    #copy and update readme
    cp res/README "${build_target}/${output}/agent"
    local build_date="$(sed 's/[^-A-Za-z0-9_]/\\&/g' <<< $(date +'%F %T %Z'))"  #package timestamp

    #revision from which the build was generated; available only if it is a git repo
    local build_revision=$([[ "$(type -P git 2>/dev/null)" == "" ]] && echo git rev-parse --short=10 HEAD 2>/dev/null)
    [[ "$build_revision" != "" ]] && build_revision="- $(sed 's/[^-A-Za-z0-9_]/\\&/g' <<< ${build_revision})"
    
    #add version, date and git revision at the top README
    sed -i "1iSeaLion Agent ${version} - ${build_date} ${build_revision}" "${build_target}/${output}/agent/README" 
    
    echo "README generated"
}

#script variables
default_domain="sealion.com"
domain=$default_domain version=

#parse command line
opt_parse d:h "domain= help" options args "$@"

#if parsing failed print the usage and exit
if [[ $? -ne 0 ]] ; then
    echo "$options" >&2
    usage ; exit 125
fi

#loop through the options
for option_index in "${!options[@]}" ; do
    [[ $(( option_index % 2 )) -ne 0 ]] && continue  #skip option arguments
    option_arg=${options[$(( option_index + 1 ))]}  #option argument for the current option

    #find the proper option and perform the action
    case "${options[${option_index}]}" in
        d|domain)
            domain=$option_arg
            ;;
        h|help)
            usage 1 ; exit 0
            ;;
    esac
done

#set the version
for arg in "${args[@]}" ; do
    version=$arg
done

#trim whitespace from both ends
version="$(sed -e 's/^\s*//' -e 's/\s*$//' <<< ${version})"
domain="$(sed -e 's/^\s*//' -e 's/\s*$//' <<< ${domain})"

build_target=$domain  #build target is the domain for which packaging is done

#you need to specify the version
if [ "$version" == "" ] ; then
    echo "Please specify a valid version for the build"
    usage ; exit 1
fi

#if domain is sealion.com then api url is api.sealion.com
#if domain is something like test.sealion.com then api url is api-test.sealion.com
#agent download url also follows this naming convention
if [ "$domain" != "$default_domain" ] ; then
    domain="-$domain"
else
    domain=".$domain"
fi

api_url="https://api$domain" agent_url="https://agent$domain"  #set the urls
output="sealion-agent" orig_domain="$build_target"
build_target="bin/$build_target"  #update build target

#move to current dir so that all the paths are available
cd "$script_base_dir"

#cleanup and recreate the output directories
rm -rf $build_target >/dev/null 2>&1
mkdir -p $build_target/$output/agent
chmod +x $build_target/$output

#copy the src directories to output
find ../code/ -mindepth 1 -maxdepth 1 -type d -regextype sed -regex '.*/\(\(lib\)\|\(opt\)\|\(src\)\|\(bin\)\)' -exec cp -r {} "${build_target}/${output}/agent" \;

cp -r res/etc "${build_target}/${output}/agent"  #copy etc folder from res
mkdir -p "${build_target}/${output}/agent/etc/init.d"  #make init.d folder
generate_scripts  #generate scripts

#if domain is not sealion.com, then set the logging level to debug
if [ "$orig_domain"  != "$default_domain" ] ; then
    "${build_target}/${output}/agent/bin/configure.py" -a "set" -k "logging:level" -v "\"debug\"" "${build_target}/${output}/agent/etc/config.json"
    echo "Agent logging level set to 'debug'"
fi

#generate tar in the output directory and cleanup temp directory created
tarfile="${build_target}/${output}-${version}-noarch.tar.gz"
echo "Generating ${tarfile}..."
tar -zcvf "$tarfile" --exclude="*.pyc" --exclude="__pycache__" --exclude="*~" --exclude-vcs --exclude-backups --directory=$build_target "${output}/"  | (while read line; do echo "    ${line}"; done)
rm -rf "${build_target}/${output}"

