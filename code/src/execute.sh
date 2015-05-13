#This script is used to execute command-line activities from SeaLion agent.
#This is an attempt to reduce the memory overhead in fork-exec as bash consumes less memory compared to Python.
#It also enable parallel process execution using multiple CPU cores. 
#During termination the script also checks whether the agent is terminated abnormally, if so it resurrects the agent

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

trap "terminate" EXIT  #trap exit, and send signal to sub-shell jobs, which in turn kills their children
trap "exit" SIGTERM  #exit on SIGTERM 
PATH="${PATH}:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"  #common paths found in various linux distros

#Function to close the output streams and kill background jobs.
#It also resurrects sealion agent if terminated abnormally
terminate() {
    local pid= timestamp="                       "
    exec 1>&- 1>/dev/null #close and redirect stdout
    exec 2>&- 2>/dev/null #close and redirect stderr
    kill -SIGTERM $(jobs -p) >/dev/null 2>&1
    read pid <"$pid_file"  #read pid from file

    #resurrect agent if the pid read from the file is matching to the original pid and is not running
    #we do resurrection only if the agent is running as a daemon which is identified by looking at the main script name
    #this is not an attempt to prevent SIGKILL from users; rather a way to resurrect when killed by OOM killer
    if [[ "$pid" == "$PPID" && "$main_script" == "sealion.py" && ! -d "/proc/${pid}" ]] ; then
        type date >/dev/null 2>&1
        [[ $? -eq 0 ]] && timestamp=$(date +"%F %T,%3N")
        echo "${timestamp} CRITICAL                - Abnormal termination detected for process ${PPID}; Resurrecting..." >>"$log_file"
        eval $cmdline  #replace the executable with command line
    fi
}

#Function to kill children
kill_children() {
    if [[ $no_setsid -eq 0 ]] ; then  #kill process group if we have setsid
        kill -SIGKILL -- -$SESSION_PID  >/dev/null 2>&1
    else 
        kill -SIGKILL $SESSION_PID >/dev/null 2>&1  #bad luck; the grand children are still alive
    fi
}

usage="Usage: ${0} <agent main script> <output files directory> [clean]"

if [[ "$#" -lt "2" ]] ; then
    echo "Missing arguments" >&2
    echo $usage ; exit 1
fi

#sealion agent dir
exe_dir=${1%/*}
exe_dir=${exe_dir%/*}

main_script="${1##*/}"  #extract the main python script
read -r cmdline </proc/${PPID}/cmdline  #extract the command line for the parent process

#main script has to be one of them
if [[ "$main_script" != "sealion.py" && "$main_script" != "main.py" ]] ; then
    echo "Invalid agent main script"
    echo $usage ; exit 1
fi

#check whether the script is same as the one present in the command line of the parent process
if [[ "$exe_dir" == "" || "$cmdline" != *"$main_script"* ]] ; then
    echo "Invalid agent main script"
    echo $usage ; exit 1
fi

output_dir=${2%/}  #directory for output files
pid_file="${exe_dir}/var/run/sealion.pid"  #pid file to be checked for
log_file="${exe_dir}/var/log/sealion.log"  #log file to be written
cmdline=""  #command to restart the agent 

#frame the executable command line by space separating the arguments
while read -r -d $'\0' line ; do 
    [[ "$line" == *"$main_script" ]] && line=$1  #if it is the script, replace it with full path
    line=${line//\"/\\\"}  #escape any double quotes and append it
    cmdline+=" \"${line}\""
done </proc/${PPID}/cmdline

#initialize the indexes of each column in the line read from stdin
timestamp_index=0  #unique timestamp of the activity
output_index=1  #filename of output
command_index=2  #command to be executed, this has to be the last index as a command can have spaces in it

#whether to clean the output directory
if [[ "$3" == "clean" ]] ; then
    #check whether we have rm available; if so remove the files in the output directory
    type rm >/dev/null 2>&1
    [[ $? -eq 0 ]] && rm -rf "${output_dir}"/* >/dev/null 2>&1
elif [[ "$3" != "" ]] ; then
    echo "Unknown startup command '${3}'" >&2
    echo $usage ; exit 1
fi

#check whether we have setsid available
type setsid >/dev/null 2>&1
no_setsid=$?

#if setsid is not available we wont be able to run the activities in a new session
#which means, we wont be able to kill the process tree if the command timeout
[[ $no_setsid -ne 0 ]] && echo "warning: Cannot run commands as process group; 'setsid' not available"

#continuously read line from stdin, blocking read.
#format of a line is 'TIMESTAMP OUTPUT_FILE: COMMAND_WITH_SPACES'
while read -r line ; do
    old_ifs=$IFS ; IFS=" " ; read -a activity <<<"${line%%:*}" ; IFS=$old_ifs  #make activity array from string upto ':' character
    activity+=("${line#*:}")  #add string after ':' character to activity array

    (
        #this is a sub-shell, which is forked from parent process. 
        #we run this as a background job to enable parallel execution.
        #format of output is 'data: TIMESTAMP pid|return_code VALUE'

        trap "kill_children" SIGTERM  #kill children on SIGTERM

        if [[ "$BASHPID" == "" ]] ; then  #for bash versions where BASHPID does not exist
            read BASHPID </proc/self/stat
            old_ifs=$IFS ; IFS=" " ; read -a BASHPID <<<"$BASHPID" ; IFS=$old_ifs
            BASHPID=${BASHPID[4]}  #pid is at the 4th index
        fi

        echo "data: ${activity[${timestamp_index}]} pid ${BASHPID}"  #write out the process id for tracking purpose

        if [[ $no_setsid -eq 0 ]] ; then  #run it in a new session
            setsid bash -c "${activity[${command_index}]}" >"${output_dir}/${activity[${output_index}]}" 2>&1 &
        else
            bash -c "${activity[${command_index}]}" >"${output_dir}/${activity[${output_index}]}" 2>&1 &
        fi

        SESSION_PID=$!  #pid of the bash process
        wait  #wait for the background job to finish
        echo "data: ${activity[${timestamp_index}]} return_code ${?}"  #write out the return code which indicates that the process has finished
    ) &
done
