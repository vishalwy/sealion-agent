
opt_parse() 
{
    local parse_options="$1-:" parse_long_options
    IFS=" "; read -a parse_long_options <<< "$2"
    eval "$3=(); $4=()"
    
    if [[ "${parse_options:0:1}" != ":" ]] ; then
        parse_options=":$parse_options"
    fi

    OPTIND=5

    while getopts $parse_options opt ; do
        case "$opt" in
            -)
                local long_opt= long_opt_arg= arg_required=0
                
                for parse_long_option in "${parse_long_options[@]}" ; do
                    if [ "${parse_long_option%=}" == "${OPTARG%%=*}" ] ; then
                        local len="${#parse_long_option}"
                        [[ "${parse_long_option:$(( len - 1 )):1}" == "=" ]] && arg_required=1
                        long_opt="${parse_long_option%=}"
                        long_opt_arg="${OPTARG#*=}"

                        if [[ "$long_opt_arg" == "$OPTARG" && $arg_required -eq 1 ]] ; then
                            long_opt_arg=${!OPTIND}
                            OPTIND=$(( $OPTIND + 1 ))
                        fi

                        break
                    fi
                done

                if [[ "$long_opt" == "" ]] ; then
                    eval "$3=\"Option --${OPTARG%%=*} not recognized\""
                    return 1
                elif [[ $arg_required -eq 1 && "$long_opt_arg" == "" ]] ; then
                    eval "$3=\"Option --$long_opt requires an argument\""
                    return 2
                elif [ $arg_required -eq 0 ] ; then
                    long_opt_arg="NONE"
                fi

                eval "$3+=($long_opt $long_opt_arg)"
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
                eval "$3+=($opt $OPTARG)"
                ;;
        esac
    done

    while [ "$OPTIND" -le "$#" ] ; do
        eval "$4+=(${!OPTIND})"
        OPTIND=$(( $OPTIND + 1 ))
    done

    return 0
}

