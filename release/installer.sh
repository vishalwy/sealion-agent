#!/bin/bash
args=$@
TMP_FILE_PATH=/tmp/sealion-agent
TMP_FILE_NAME=$TMP_FILE_PATH"/sealion-agent.tmp"
USAGE="Usage: curl -k https://agent.sealion.com | bash /dev/stdin \n\t-o <Organisation Token> \n\t[-H <Hostname>] \n\t[-c <category name>] \n\t [-h for help]"

mkdir -p $TMP_FILE_PATH
if [ $? -ne 0 ] ; then
    echo "Sealion-Agent Error: Can't create temporary directory"
    exit 1
fi

while getopts a:o:c:v:hH: OPT ; do
    case "$OPT" in
        v)
            version=$OPTARG
        ;;
        a)
            agent_id=$OPTARG
        ;;
        H)
            host=$OPTARG
        ;;
        h)
            printf "$USAGE \n" >&1
            exit 0
        ;;
        o)
        if [ -z $org_token ] ; then
            org_token=$OPTARG
        fi
        ;;
        c)
            tags=$OPTARG
        ;;
        \?)
            echo "Invalid argument -$OPTARG" >&2
            printf "$USAGE \n" >&2
            exit 126
        ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            printf "$USAGE \n" >&2
            exit 125
        ;;
    esac
done

echo "Downloading agent..."

if [ -z $agent_id ] ; then
    curl -# https://agent.sealion.com/sealion.sh -o $TMP_FILE_NAME
else
    curl https://agent.sealion.com/sealion.sh -o $TMP_FILE_NAME
fi

bash $TMP_FILE_NAME $args
