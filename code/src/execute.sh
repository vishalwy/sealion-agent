#This script is used to execute command-line activities from SeaLion agent.
#This is an attempt to reduce the memory overhead in fork-exec as bash consumes less memory compared to Python.
#It also enable parallel process execution using multiple CPU cores. 

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

#trap exit, and send signal to sub-shell jobs, which in turn kills their children
trap "terminate" EXIT

#Function to close the output streams and kill background jobs.
terminate() {
    exec 1>&-  #close stdout
    exec 2>&-  #close stderr
    kill -SIGTERM $(jobs -p) >/dev/null 2>&1
}

#Function to kill children
kill_children() {
    if [ $no_setsid -eq 0 ] ; then  #kill process group if we have setsid
        kill -SIGKILL -- -$SESSION_PID  >/dev/null 2>&1
    else 
        kill -SIGKILL $SESSION_PID >/dev/null 2>&1  #bad luck; the grand children are still alive
    fi
}

#initialize the indexes of each column in the line read from stdin
timestamp_index=0  #unique timestamp of the activity
output_index=1  #filename of output
command_index=2  #command to be executed, this has to be the last index as a command can have spaces in it

PATH="${PATH}:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"  #common paths found in various linux distros

#check whether we have setsid available
type setsid >/dev/null 2>&1
no_setsid=$?

#if setsid is not available we wont be able to run the activities in a new session
#which means, we wont be able to kill the process tree if the command timeout
[[ $no_setsid -ne 0 ]] && echo "warning: Cannot run commands as process group; setsid not available"

#continuously read line from stdin, blocking read.
#format of a line is 'TIMESTAMP OUTPUT_FILE: COMMAND_WITH_SPACES'
while read -r line ; do
    activity=(${line%%:*})  #make activity array from string upto ':' character
    activity=("${activity[@]}" "${line#*:}")  #add string after ':' character to activity array

    (
        #This is a sub-shell, which is forked from parent process. 
        #We run this as a background job to enable parallel execution.

        trap "kill_children" SIGTERM  #kill children on exit

        if [ "$BASHPID" == "" ] ; then  #for bash versions where BASHPID does not exist
            read BASHPID </proc/self/stat
            BASHPID=($BASHPID)
            BASHPID=${BASHPID[4]}  #pid is at the 4th index
        fi

        echo "data: ${activity[$timestamp_index]} pid $BASHPID"  #write out the process id for tracking purpose

        if [ $no_setsid -eq 0 ] ; then  #run it in a new session
            setsid bash -c "${activity[$command_index]}" 1>"${activity[$output_index]}" 2>"${activity[$output_index]}" &
        else
            bash -c "${activity[$command_index]}" 1>"${activity[$output_index]}" 2>"${activity[$output_index]}" &
        fi

        SESSION_PID=$!  #pid of the bash process
        wait  #wait for the background job to finish
        echo "data: ${activity[$timestamp_index]} return_code $?"  #write out the return code which indicates that the process has finished
    ) &
done
