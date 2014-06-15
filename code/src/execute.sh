#!/bin/bash

#This script is used to execute command-line activities from SeaLion agent.
#This is an attempt to reduce the memory overhead in fork-exec as bash consumes less memory compared to Python.
#It also enable parallel process execution using multiple CPU cores. 

#trap exit, and send signal to sub-shell jobs, which in turn kills their children
trap "kill -SIGTERM $(jobs -p)" EXIT

#initialize the indexes of each column in the line read from stdin
TIMESTAMP=0  #unique timestamp of the activity
OUTPUT=1  #filename of output
COMMAND=2  #command to be executed, this has to be the last index as a command can have spaces in it

PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin  #common paths found in various linux distros
SETSID=$('which setsid' 2>/dev/null)  #check whether we have setsid available

#if setsid is not available we wont be able to run the activities in a new session
#which means, we wont be able to kill the process tree if the command timeout
if [ "SETSID" == "" ] ; then
    echo "warning: setsid not available"
fi

#continuously read line from stdin, blocking read.
#format of a line is 'TIMESTAMP OUTPUT_FILE: COMMAND_WITH_SPACES'
while read -r LINE ; do
    ACTIVITY=(${LINE%%:*})  #make activity array from string upto ':' character
    ACTIVITY=("${ACTIVITY[@]}" "${LINE#*:}")  #add string after ':' character to activity array

    (
        #This is a sub-shell, which is forked from parent process. We run this as a background job to enable parallel execution.
        
        #pid of the bash process
        SESSION_PID=

        kill_children()
        {
            #Function to kill children.
            
            if [ "SETSID" != "" ] ; then  #kill process group if we have setsid
                kill -SIGKILL -- -$SESSION_PID
            else 
                kill -SIGKILL $SESSION_PID
            fi
        }

        trap "kill_children" SIGTERM  #kill children on exit
        echo "data: ${ACTIVITY[$TIMESTAMP]} pid $BASHPID"  #write out the process id for tracking purpose

        if [ "SETSID" != "" ] ; then  #run it in a new session
            setsid bash -c "${ACTIVITY[$COMMAND]}" 1>"${ACTIVITY[$OUTPUT]}" 2>"${ACTIVITY[$OUTPUT]}" &
        else
            bash -c "${ACTIVITY[$COMMAND]}" 1>"${ACTIVITY[$OUTPUT]}" 2>"${ACTIVITY[$OUTPUT]}" &
        fi

        SESSION_PID=$!
        wait  #wait for the background job to finish
        echo "data: ${ACTIVITY[$TIMESTAMP]} return_code $?"  #write out the return code which indicates that the process has finished
    ) &
done
