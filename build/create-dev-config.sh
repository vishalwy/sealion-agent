USAGE="Usage: $0 {-o <Organization token> -v <Agent version> [-c <Category name>] [-H <Host name>] [-x <Proxy address>] [-a <API URL>] | -h for Help}"
ORG_TOKEN=
VERSION=
CATEGORY=
HOST_NAME=$(hostname)
PROXY=$https_proxy
NO_PROXY=$no_proxy
API_URL="https://api-test.sealion.com"

while getopts :o:c:H:x:a:r:v:h OPT ; do
    case "$OPT" in
        o)
            ORG_TOKEN=$OPTARG
            ;;
        c)
            CATEGORY=$OPTARG
            ;;
        h)
            echo $USAGE
            exit 0
            ;;
        H)
            HOST_NAME=$OPTARG
            ;;
        x)
            PROXY=$OPTARG
            ;;
        a)
            API_URL=$OPTARG
            ;;
        v)
            VERSION=$OPTARG
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

if [ "$ORG_TOKEN" == "" ] ; then
    echo "Missing option '-o'" >&2
    echo $USAGE
    exit 1
fi

if [ "$VERSION" == "" ] ; then
    echo "Missing option '-v'" >&2
    echo $USAGE
    exit 1
fi

BASEDIR=$([ ${0:0:1} != "/" ] && echo "$(pwd)/$0" || echo "$0")
BASEDIR=${BASEDIR%/*}
cp -r "$BASEDIR/res/etc" "$BASEDIR/../code/"

CONFIG="\"orgToken\": \"$ORG_TOKEN\", \"apiUrl\": \"$API_URL\", \"agentVersion\": \"$VERSION\", \"name\": \"$HOST_NAME\", \"ref\": \"tarball\""
TEMP_VAR=""

if [ "$CATEGORY" != "" ] ; then
    CONFIG="$CONFIG, \"category\": \"$CATEGORY\""
fi

echo "{$CONFIG}" >"$BASEDIR/../code/etc/agent.json"
sed -i 's/\("level"\s*:\s*\)"[^"]\+"/\1"debug"/' "$BASEDIR/../code/etc/config.json"

if [ "$PROXY" != "" ] ; then
    PROXY="$(echo "$PROXY" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(\"env\"\s*:\s*\[\)/\1{\"https\_proxy\": \"$PROXY\"}/'"
    eval sed "$ARGS" "\"$BASEDIR/../code/etc/config.json\""
    TEMP_VAR=", "
fi

if [ "$NO_PROXY" != "" ] ; then
    NO_PROXY="$(echo "$NO_PROXY" | sed 's/[^-A-Za-z0-9_]/\\&/g')"
    ARGS="-i 's/\(\"env\"\s*:\s*\[\)/\1{\"no\_proxy\": \"$NO_PROXY\"}$TEMP_VAR/'"
    eval sed "$ARGS" "\"$BASEDIR/../code/etc/config.json\""
fi

echo "Generated config files at $BASEDIR/../code/etc"

