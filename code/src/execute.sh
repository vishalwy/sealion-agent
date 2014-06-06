#!/bin/bash

read TIMESTAMP OUTPUT COMMAND <<<$(echo 0 1 2)

while read -r LINE ; do
    ACTIVITY=(${LINE%%:*})
    ACTIVITY=("${ACTIVITY[@]}" "${LINE#*:}")

    (
        echo "${ACTIVITY[$TIMESTAMP]} pid $BASHPID"
        bash -c "${ACTIVITY[$COMMAND]}" 1>"${ACTIVITY[$OUTPUT]}" 2>"${ACTIVITY[$OUTPUT]}" &
        wait
        echo "${ACTIVITY[$TIMESTAMP]} return_code $?"
    ) &
done
