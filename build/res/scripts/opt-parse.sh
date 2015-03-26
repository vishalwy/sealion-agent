
opt_parse() 
{
    local LOCAL_OPTIONS="$1-:"
    local LOCAL_LONG_OPTIONS
    IFS=" "; read -a LOCAL_LONG_OPTIONS <<< "$2"
    eval "$3=(); $4=()"
    
    if [ "${LOCAL_OPTIONS:0:1}" != ":" ] ; then
        LOCAL_OPTIONS=":$LOCAL_OPTIONS"
    fi

    OPTIND=5

    while getopts $LOCAL_OPTIONS OPT ; do
        case "$OPT" in
            -)
                local LONG_OPT=
                local LONG_OPTARG=
                local NEED_ARG=0

                for LONG_OPTION in "${LOCAL_LONG_OPTIONS[@]}" ; do
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
                    eval "$3=\"Option --${OPTARG%%=*} not recognized\""
                    return 1
                elif [[ $NEED_ARG -eq 1 && "$LONG_OPTARG" == "" ]] ; then
                    eval "$3=\"Option --$LONG_OPT requires an argument\""
                    return 2
                elif [ $NEED_ARG -eq 0 ] ; then
                    LONG_OPTARG="NONE"
                fi

                eval "$3+=($LONG_OPT $LONG_OPTARG)"
                ;;
            \?)
                eval "$3=\"Option -$OPTARG not recognized\""
                return 1
                ;;
            :)
                eval "$3=\"Option -$OPTARG requires an argument\""
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

