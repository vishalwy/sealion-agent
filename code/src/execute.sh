#!/bin/bash

trap "kill -SIGTERM $(jobs -p)" EXIT
read TIMESTAMP OUTPUT COMMAND <<<$(echo 0 1 2)
PATH=$PATH:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin
SETSID=$('which setsid' 2>/dev/null)

if [ "SETSID" == "" ] ; then
    echo "warning: setsid not available"
fi

while read -r LINE ; do
    ACTIVITY=(${LINE%%:*})
    ACTIVITY=("${ACTIVITY[@]}" "${LINE#*:}")

    (
        SESSION_PID=

        kill_children()
        {
            if [ "SETSID" != "" ] ; then
                kill -SIGKILL -- -$SESSION_PID
            else
                kill -SIGKILL $SESSION_PID
            fi
        }

        trap "kill_children" SIGTERM
        echo "${ACTIVITY[$TIMESTAMP]} pid $BASHPID"

        if [ "SETSID" != "" ] ; then
            bash -c "${ACTIVITY[$COMMAND]}" 1>"${ACTIVITY[$OUTPUT]}" 2>"${ACTIVITY[$OUTPUT]}" &
        else
            setsid bash -c "${ACTIVITY[$COMMAND]}" 1>"${ACTIVITY[$OUTPUT]}" 2>"${ACTIVITY[$OUTPUT]}" &
        fi

        SESSION_PID=$!
        wait
        echo "${ACTIVITY[$TIMESTAMP]} return_code $?"
    ) &
done
