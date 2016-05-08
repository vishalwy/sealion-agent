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
    exec 1>&- 1>/dev/null  #close and redirect stdout
    exec 2>&- 2>/dev/null  #close and redirect stderr

    #kill all the children
    #kill them individually to avoid kill throwing error for non-existing processes
    #that can result in the running process ids being ignored
    while read -r pid ; do
        kill -SIGTERM $pid
    done <<<"$(jobs -pr)"

    pid= ; read pid <"${exe_dir}/var/run/sealion.pid"  #read pid from file

    #resurrect agent if the pid read from the file is matching to the original pid and is not running
    #we do resurrection only if the agent is running as daemon
    #this is not an attempt to prevent SIGKILL from users; rather a way to resurrect when killed by OOM killer
    if [[ "$pid" == "$PPID" && "$is_daemon" == "1" && ! -d "/proc/${pid}" ]] ; then
        type date >/dev/null 2>&1
        [[ $? -eq 0 ]] && timestamp=$(date +"%F %T,%3N")
        echo "${timestamp} CRITICAL                - Abnormal termination detected for process ${PPID}; Resurrecting..." >>"${exe_dir}/var/log/sealion.log"
        eval $cmdline  #replace the executable with command line
    fi
}

#Function to kill children
kill_children() {
    kill -SIGKILL -- -${pgid} >/dev/null 2>&1
}

main_script="${1##*/}"  #extract the main python script
is_daemon=$2  #check whether agent is running without a controlling terminal

#sealion agent dir
exe_dir=${1%/*}
exe_dir=${exe_dir%/*}

#frame the executable command line by space separating the arguments
cmdline="" ; while read -r -d $'\0' line ; do 
    [[ "$line" == *"$main_script" ]] && line=$1  #if it is the script, replace it with full path
    line=${line//\"/\\\"}  #escape any double quotes and append it
    cmdline="${cmdline} \"${line}\""
done </proc/${PPID}/cmdline

#check whether the script is same as the one present in the command line of the parent process
if [[ "$main_script" == "" || "$exe_dir" == "" || "$cmdline" != *"$main_script"* ]] ; then
    echo "Missing or invalid agent main script" >&2
    echo "Usage: ${0} <agent main script>" ; exit 1
fi

#continuously read line from stdin, blocking read.
#format of a line is 'TIMESTAMP COMMAND_INTERVAL OUTPUT_FILE COMMAND_LINE' ending with \r
while IFS=" " read -r -d $'\r' timestamp command_interval output_file command_line ; do
    #execute maintenance commands; they are identified by looking at timestamp which is zero
    if [[ "$timestamp" == "0" ]] ; then
        $command_line >"$output_file" 2>&1
        continue
    fi

    (
        #this is a sub-shell, which is forked from parent process. 
        #we run this as a background job to enable parallel execution.
        #format of output is 'data: TIMESTAMP (pid|return_code) VALUE'
        #you can also log in the format '(debug|info|warning): message'

        trap "kill_children" EXIT  #trap exit, and kill the process group
        trap "exit" SIGTERM  #exit on SIGTERM 
        set -m  #enable job control so that the background jobs runs in a new process group

        #export the interval for the command; useful to perform any time based calculation
        export COMMAND_INTERVAL="$command_interval"

        bash -c "$command_line" >"$output_file" 2>&1 </dev/null &  #execute the command
        pgid=$!  #process group id of the last background job
        echo "data: ${timestamp} pid ${pgid}"  #write out the process id for tracking purpose
        wait >/dev/null 2>&1  #wait for the background job to finish; redirect the output so that it wont print any errors
        echo "data: ${timestamp} return_code ${?}"  #write out the return code which indicates that the process has finished
    ) &
done
