#!/bin/bash

#Copyright  : (c) Webyog, Inc
#Author     : Vishal P.R
#Email      : hello@sealion.com

USAGE="Usage: $0 {-i <Updater directory> -o <Organization token> -a <Agent Id> -p <Python binary> | -h for Help}"
DOWNLOAD_PATH=
ORG_TOKEN=
AGENT_ID=
PYTHON_BINARY=

while getopts :i:o:p:a:h OPT ; do
    case "$OPT" in
        i)
            DOWNLOAD_PATH=$OPTARG
            ;;
        o)
            ORG_TOKEN=$OPTARG
            ;;
        a)
            AGENT_ID=$OPTARG
            ;;
        p)
            PYTHON_BINARY=$OPTARG
            ;;
        h)
            echo $USAGE
            exit 0
            ;;
        \?)
            echo "Invalid option '-$OPTARG'" >&2
            echo $USAGE
            exit 1
            ;;
        :)
            echo "Option '-$OPTARG' requires an argument" >&2
            echo $USAGE
            exit 1
            ;;
    esac
done

DOWNLOAD_PATH=${DOWNLOAD_PATH%/}
INSTALL_SCRIPT="$DOWNLOAD_PATH/sealion-agent/install.sh"
DOWNLOAD_PATH="$DOWNLOAD_PATH/../../../"
INSTALL_SCRIPT -o $ORG_TOKEN -a $AGENT_ID -p $PYTHON_BINARY -i "$DOWNLOAD_PATH"

