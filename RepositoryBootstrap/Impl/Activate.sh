#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  Activate.sh
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 19:48:31
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
set +v                                      # Disable output

# Note that we can't exit or return from this script, as it is sourced at the
# repo's root. Because of this, we use the ugly 'should_continue' hack.
should_continue=1

this_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source ${this_dir}/CommonFunctions.sh

if [[ ${is_darwin} -eq 1 ]]
then
    os_name=BSD
else
    os_name=Linux
fi

# The following environment variables are used by this script and must be populated
# prior to its invocation:
#
#    DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME
#

# Ensure that the script is being invoked via source (as it modifies the current environment)
if [[ ${should_continue} == 1 && ${0##*/} == Activate.sh ]]
then
    echo ""
    echo "[31m[1mERROR:[0m This script activates a terminal for development according to information specific to the repository."
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m Because this process makes changes to environment variables, it must be run within the current context."
    echo "[31m[1mERROR:[0m To do this, please source (run) the script as follows:"
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m     source ./Activate.sh"
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m         - or -"
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m     . ./Activate.sh"
    echo "[31m[1mERROR:[0m"
    echo ""

    should_continue=0
fi

# Read the bootstrap data
if [[ ${should_continue} == 1 && ! -e `pwd`/Generated/${os_name}/${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}/EnvironmentBootstrap.data ]]
then
    echo ""
    echo "[31m[1mERROR:[0m It appears that Setup.sh has not been run for this repository. Please run Setup.sh and run this script again."
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m     [`pwd`/Generated/${os_name}/${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}/EnvironmentBootstrap.data was not found]"
    echo "[31m[1mERROR:[0m"
    echo ""

    should_continue=0
fi

if [[ ${should_continue} == 1 ]]
then
    while read line;
    do
        if [[ ${line} == foundation_repo* ]]
        then
            if [[ ${OSTYPE} == *darwin* ]]
            then
                export DEVELOPMENT_ENVIRONMENT_FOUNDATION=$(greadlink -f ${line#foundation_repo=})
            else
                export DEVELOPMENT_ENVIRONMENT_FOUNDATION=$(readlink -f ${line#foundation_repo=})
            fi
        elif [[ ${line} == is_mixin_repo* ]]
        then
            is_mixin_repo=${line#is_mixin_repo=}
        elif [[ ${line} == is_configurable* ]]
        then
            is_configurable=${line#is_configurable=}
        fi

    done < "`pwd`/Generated/${os_name}/${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}/EnvironmentBootstrap.data"
fi

# Get a python version to use for setup
if [[ ${should_continue} == 1 ]]
then
    # Note that this environment name must match the value associated with DE_ORIGINAL_PATH found in ../Constants.py
    export DEVELOPMENT_ENVIRONMENT_ORIGINAL_PATH=${PATH}

    if [[ ${is_darwin} -eq 1 ]]
    then
        python_dir=/Library/Frameworks/Python.framework/Versions
        pushd ${python_dir} > /dev/null

        for d in $(find * -maxdepth 0 -type d);
        do
            if [[ -e ${python_dir}/${d}/bin/python ]]
            then
                export PATH=${python_dir}/${d}/bin:${PATH}
            fi
        done

        popd > /dev/null
    else
        # python
        python_dir=${DEVELOPMENT_ENVIRONMENT_FOUNDATION}/Tools/Python
        pushd ${python_dir} > /dev/null

        for d in $(find v* -maxdepth 0 -type d);
        do
            if [[ -e ${python_dir}/${d}/${os_name}/x64/${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}/bin/python ]]
            then
                export PATH=${python_dir}/${d}/${os_name}/x64/${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}/bin:${PATH}
            fi
        done

        popd > /dev/null
    fi

    export PYTHONPATH=${DEVELOPMENT_ENVIRONMENT_FOUNDATION}:${DEVELOPMENT_ENVIRONMENT_FOUNDATION}/Libraries/Python/Common_Foundation/src:${DEVELOPMENT_ENVIRONMENT_FOUNDATION}/Libraries/Python/Common_FoundationEx/src

    # ----------------------------------------------------------------------
    # |  List configurations if requested
    if [[ "$1" == "ListConfigurations" ]]
    then
        shift 1

        python -m RepositoryBootstrap.Impl.Activate ListConfigurations "`pwd`" "$@"
        should_continue=0
    fi
fi

# If here, we are in a verified activation scenario. Set the previous value to this value, knowing that that is the value
# that will be committed.
if [[ ${should_continue} == 1 ]]
then
    previous_foundation=${DEVELOPMENT_ENVIRONMENT_FOUNDATION}

    # ----------------------------------------------------------------------
    # |  Only allow one activated environment at a time (unless we are activating a mixin repo)
    if [[ ${is_mixin_repo} != "1" && "${DEVELOPMENT_ENVIRONMENT_REPOSITORY}" != "" && "${DEVELOPMENT_ENVIRONMENT_REPOSITORY}" != "`pwd`" ]]
    then
        echo ""
        echo "[31m[1mERROR:[0m Only one repository can be activated within an environment at a time, and it appears as if one is already active. Please open a new terminal and run this script again."
        echo "[31m[1mERROR:[0m"
        echo "[31m[1mERROR:[0m     [DEVELOPMENT_ENVIRONMENT_REPOSITORY is already defined as \"$DEVELOPMENT_ENVIRONMENT_REPOSITORY}\"]"
        echo "[31m[1mERROR:[0m"

        should_continue=0
    fi
fi

if [[ ${should_continue} == 1 ]]
then
    # ----------------------------------------------------------------------
    # |  A mixin repository can't be activated in isolation
    if [[ ${is_mixin_repo} == "1" && "${DEVELOPMENT_ENVIRONMENT_REPOSITORY_ACTIVATED_KEY}" == "" ]]
    then
        echo ""
        echo "[31m[1mERROR:[0m A mixin repository cannot be activated in isolation. Activate another repository before activating this one."
        echo "[31m[1mERROR:[0m"

        should_continue=0
    fi
fi

if [[ ${should_continue} == 1 ]]
then
    # ----------------------------------------------------------------------
    # |  Prepare the args
    if [[ ${is_configurable} == "1" ]]
    then
        if [[ "$1" == "" ]]
        then
            echo ""
            echo "[31m[1mERROR:[0m This repository is configurable, which means that it can be activated in a variety of different ways. Please run this script again with a configuration name provided on the command line."
            echo "[31m[1mERROR:[0m"
            echo "[31m[1mERROR:[0m     Available configurations are:"
            echo "[31m[1mERROR:[0m"
            python -m RepositoryBootstrap.Impl.Activate ListConfigurations "`pwd`" --display-format command_line
            echo "[31m[1mERROR:[0m"
            echo ""

            should_continue=0
        fi

        if [[ "${DEVELOPMENT_ENVIRONMENT_REPOSITORY_CONFIGURATION}" != "" && "${DEVELOPMENT_ENVIRONMENT_REPOSITORY_CONFIGURATION}" != "$1" ]]
        then
            echo ""
            echo "[31m[1mERROR:[0m The environment was previously activated with this repository but used a different configuration. Please open a new terminal window and activate this repository with the new configuration."
            echo "[31m[1mERROR:[0m"
            echo "[31m[1mERROR:[0m     ["${DEVELOPMENT_ENVIRONMENT_REPOSITORY_CONFIGURATION}" != "$1"]"
            echo "[31m[1mERROR:[0m"

            should_continue=0
        fi

        configuration=$1
        shift 1
    else
        initial_char="$(echo $1 | head -c 1)"

        if [[ "${initial_char}" != "" && "${initial_char}" != "-" && "${initial_char}" != "/" ]]
        then
            echo ""
            echo "[31m[1mERROR:[0m This repository is not configurable, but a configuration name was provided."
            echo "[31m[1mERROR:[0m"
            echo "[31m[1mERROR:[0m     [$1]"
            echo "[31m[1mERROR:[0m"

            should_continue=0
        else
            configuration=None
        fi
    fi
fi

if [[ ${should_continue} == 1 ]]
then
    temp_script_name=$(mktemp_func)
    [[ ! -e ${temp_script_name} ]] || rm -f "${temp_script_name}"

    # ----------------------------------------------------------------------
    # |  Generate...
    echo ""

    python -m RepositoryBootstrap.Impl.Activate Activate ${temp_script_name} "`pwd`" ${configuration} "$@"
    generation_error=$?

    # ----------------------------------------------------------------------
    # |  Invoke...
    if [[ -e ${temp_script_name} ]]
    then
        chmod u+x ${temp_script_name}

        source ${temp_script_name}
        execution_error=$?
    fi

    # ----------------------------------------------------------------------
    # |  Process Errors...
    if [[ ${generation_error} != 0 ]]
    then
        echo ""
        echo "[31m[1mERROR:[0m Errors were encountered and the environment has not been successfully activated for development."
        echo "[31m[1mERROR:[0m"
        echo "[31m[1mERROR:[0m     [${DEVELOPMENT_ENVIRONMENT_FOUNDATION}/RepositoryBootstrap/Impl/Activate.py failed]"
        echo "[31m[1mERROR:[0m"
        echo ""

        should_continue=0

    elif [[ ${execution_error} != 0 ]]
    then
        echo ""
        echo "[31m[1mERROR:[0m Errors were encountered and the environment has not been successfully activated for development."
        echo "[31m[1mERROR:[0m"
        echo "[31m[1mERROR:[0m     [${temp_script_name} failed]"
        echo "[31m[1mERROR:[0m"
        echo ""

        should_continue=0
    fi
fi

# Cleanup
[[ ! -f ${temp_script_name} ]] || rm -f "${temp_script_name}"

if [[ ${should_continue} == 1 ]]
then
    echo ""
    python -m RepositoryBootstrap.Impl.PanelPrint "The environment has been activated for the repository and this terminal is ready for development." "bold green"
    echo ""
    echo ""
else
    export PATH=${DEVELOPMENT_ENVIRONMENT_ORIGINAL_PATH}
fi

if [[ "${previous_foundation}" != "" ]]; then
    export DEVELOPMENT_ENVIRONMENT_FOUNDATION=${previous_foundation}
else
    unset DEVELOPMENT_ENVIRONMENT_FOUNDATION
fi

unset DEVELOPMENT_ENVIRONMENT_ORIGINAL_PATH
unset PYTHONPATH
