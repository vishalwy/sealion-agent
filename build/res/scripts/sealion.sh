#!/usr/bin/env bash

### BEGIN INIT INFO
# Provides: sealion
# Required-Start:       
# Required-Stop:     
# Should-Start:      
# Default-Start: 2 3 4 5
# Default-Stop: 0 1 6
# Short-Description: SeaLion Agent
# Description: SeaLion is cloud based server debugging tool. This is SeaLion's agent to send monitoring data to SeaLion server
### END INIT INFO

trap '[[ $? -eq 127 ]] && exit 127' ERR  #exit in case command not found
PATH="${PATH}:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"  #common paths found in various linux distros

#find out the base dir of the script
script_base_dir=$(readlink -f "$0")
script_base_dir=${script_base_dir%/*}

#generate command line
cmdline_options="<options>"
cmdline="${cmdline_options} ${1}"
cmdline="${cmdline# }"

"${script_base_dir}/../../bin/sealion" $cmdline
exit $?

