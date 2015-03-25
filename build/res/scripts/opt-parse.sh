opt_parse() 
{
    local OPTIONS="$1-:"
    local LONG_OPTIONS
    IFS=" "; read -a LONG_OPTIONS <<< "$2"
    eval "$3=(); $4=()"
    local RET_ARGS=()
    
    if [ "${OPTIONS:0:1}" != ":" ] ; then
        OPTIONS=":$OPTIONS"
    fi

    OPTIND=5

    while getopts $OPTIONS OPT ; do
        case "$OPT" in
            -)
                local LONG_OPT=
                local LONG_OPTARG=
                local NEED_ARG=0

                for LONG_OPTION in "${LONG_OPTIONS[@]}" ; do
                    if [ "${LONG_OPTION%=}" == "${OPTARG%%=*}" ] ; then
                        local LEN="${#LONG_OPTION}"
                        LEN=$(( LEN - 1 ))
                        
                        if [ "${LONG_OPTION:$LEN:1}" == "=" ] ; then
                            NEED_ARG=1
                        fi

                        LONG_OPT="${LONG_OPTION%=}"
                        LONG_OPTARG="${OPTARG#*=}"

                        if [[ "$LONG_OPTARG" == "$OPTARG" && $NEED_ARG -eq 1 ]] ; then
                            LONG_OPTARG=${!OPTIND}
                            OPTIND=$(( $OPTIND + 1 ))
                        fi

                        break
                    fi
                done

                if [ "$LONG_OPT" == "" ] ; then
                    echo "option '--${OPTARG%%=*}' not recognized" >&2
                    return 1
                elif [[ $NEED_ARG -eq 1 && "$LONG_OPTARG" == "" ]] ; then
                    echo "option '--$LONG_OPT' requires an argument" >&2
                    return 2
                elif [ $NEED_ARG -eq 0 ] ; then
                    LONG_OPTARG="NONE"
                fi

                eval "$3+=($LONG_OPT $LONG_OPTARG)"
                ;;
            \?)
                echo "option '-$OPTARG' not recognized" >&2
                return 1
                ;;
            :)
                echo "option '-$OPTARG' requires an argument" >&2
                return 2
                ;;
            *)
                eval "$3+=($OPT $OPTARG)"
                ;;
        esac
    done

    while [ "$OPTIND" -le "$#" ] ; do
        eval "$4+=(${!OPTIND})"
        OPTIND=$(( $OPTIND + 1 ))
    done
}
