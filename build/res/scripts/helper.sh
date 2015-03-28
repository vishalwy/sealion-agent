#Function to parse command line arguments
#Arguments
#   $1 - short options; for example '-h'; if the option takes an argument suffix it with ':'
#   $2 - space separated list of long options; for example '--h'; if the option takes an argument suffix it with '='
#   $3 - variable to hold the array of options and their arguments; options will be at even indexes and their args at odd indexes
#   $4 - variable to hold the array of non option arguments
#   $@ - the remaining arguments are the argument to be parsed
#Returns 0 on success; 1 if option is not recognized; 2 if the argument is missing;
opt_parse() {
    local parse_options="$1-:"  #add '-' at the end of short options so that we can use getopts to parse long options

    #read the long options as an array; we need it do lookup for match
    local parse_long_options
    IFS=" "; read -a parse_long_options <<< "$2"

    eval "$3=(); $4=()"  #initialize the out variable to empty array;
    [[ "${parse_options:0:1}" != ":" ]] && parse_options=":$parse_options"  #enable silent mode for getopts if it is not done already
    OPTIND=5  #start index for getopts as this function has 4 fixed parameters

    #parse the arguments
    while getopts $parse_options opt ; do
        case "$opt" in
            -)  #we have a long option to parse
                local long_opt= long_opt_arg= arg_required=0
                
                #loop through our list of long options to find a match
                for parse_long_option in "${parse_long_options[@]}" ; do
                    #look for a match; we can ignore anything starting from the '=' character 
                    if [[ "${parse_long_option%=}" == "${OPTARG%%=*}" ]] ; then
                        #find out whether this option requires an argument by looking for '=' at the end
                        local len="${#parse_long_option}"
                        [[ "${parse_long_option:$(( len - 1 )):1}" == "=" ]] && arg_required=1

                        long_opt="${parse_long_option%=}"  #long option name excluding '='
                        long_opt_arg="${OPTARG#*=}"  #long option argument is extracted by removing the characters till the first '='

                        #if the option requires an argument, and it is still not available, then read it from the next option
                        if [[ $arg_required -eq 1 && "$long_opt_arg" == "$OPTARG" ]] ; then
                            long_opt_arg=${!OPTIND}  #read it from the next index
                            OPTIND=$(( $OPTIND + 1 ))  #increase the index so that getopts will ignore it
                        fi

                        break  #break as we found the match
                    fi
                done

                if [[ "$long_opt" == "" ]] ; then  #error since we could not find a match for the option given
                    eval "$3=\"Option --${OPTARG%%=*} not recognized\""
                    return 1
                elif [[ $arg_required -eq 1 && "$long_opt_arg" == "" ]] ; then  #error since we could not read the argument for the option
                    eval "$3=\"Option --$long_opt requires an argument\""
                    return 2
                elif [[ $arg_required -eq 0 ]] ; then  #set option argument to special string
                    long_opt_arg="NONE"
                fi

                eval "$3+=($long_opt $long_opt_arg)"  #add it to the array
                ;;
            \?)  #unknown option
                eval "$3=\"Option -$OPTARG not recognized\""
                return 1
                ;;
            :)  #argument for the option is missing
                eval "$3=\"Option -$OPTARG requires an argument\""
                return 2
                ;;
            *)  #valid option; add it to the array
                local opt_arg=$OPTARG
                [[ -z $OPTARG ]] && opt_arg="NONE"
                eval "$3+=($opt $opt_arg)"
                ;;
        esac
    done

    #now add the remaining arguments to non option arguments array
    while [[ "$OPTIND" -le "$#" ]] ; do
        eval "$4+=(${!OPTIND})"
        OPTIND=$(( $OPTIND + 1 ))
    done

    return 0  #success
}

#Function to perform command availability check
#Arguments:
#   $@ - commands to check for availability
#Returns 0 on success else 1
check_for_commands() {
    local command_missing=0

    #loop through the commands and find the missing commands
    for which_command in "$@" ; do
        type "$which_command" >/dev/null 2>&1

        if [[ $? -ne 0 ]] ; then
            echo "$which_command"
            command_missing=1
        fi
    done
    
    return $command_missing
}
