#!/bin/bash

trap "kill $(jobs -p)" EXIT
read TIMESTAMP OUTPUT COMMAND <<<$(echo 0 1 2)

while read -r LINE ; do
    ACTIVITY=(${LINE%%:*})
    ACTIVITY=("${ACTIVITY[@]}" "${LINE#*:}")

    (
        trap "kill -9 0" EXIT
        echo "${ACTIVITY[$TIMESTAMP]} pid $BASHPID"
        bash -c "${ACTIVITY[$COMMAND]}" 1>"${ACTIVITY[$OUTPUT]}" 2>"${ACTIVITY[$OUTPUT]}" &
        wait
        echo "${ACTIVITY[$TIMESTAMP]} return_code $?"
    ) &
done
