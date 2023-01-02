#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  Setup.sh
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 17:26:20
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
set -e                                      # Exit on error
set +v                                      # Disable output

# The following environment variables are used by this script and most be populated
# prior to its invocation:
#
#   DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME

this_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

source ${this_dir}/CommonFunctions.sh

prev_ld_library_path=${LD_LIBRARY_PATH}

if [[ ${is_darwin} -eq 1 ]]
then
    _python_binary=/Library/Frameworks/Python.framework/Versions/3.10/bin/python3
else
    _python_binary=/opt/Common_Foundation/python/3.10.6/bin/python
    export LD_LIBRARY_PATH=/opt/Common_Foundation/openssl/1.1.1/lib:${LD_LIBRARY_PATH}
fi

export PYTHONPATH=${this_dir}/../..:${this_dir}/../../Libraries/Python/Common_Foundation/src

# Invoke custom functionality if the first arg is a positional argument
initial_char="$(echo $1 | head -c 1)"
if [[ "${initial_char}" != "" && "${initial_char}" != "-" && ${initial_char} != "/" ]]
then
    setup_first_arg=$1
    shift

    ${_python_binary} -m RepositoryBootstrap.Impl.Setup ${setup_first_arg} "`pwd`" "$@"
else
    # Create a temporary file that contains output produced by the python script. This lets us quickly bootstrap
    # to the python environment while still executing OS-specific commands.
    temp_script_name=$(mktemp_func)
    [[ ! -e ${temp_script_name} ]] || rm -f "${temp_script_name}"

    set +e

    # Generate
    ${_python_binary} -m RepositoryBootstrap.Impl.Setup "${temp_script_name}" "`pwd`" "$@"
    generation_error=$?

    # Invoke
    if [[ -f ${temp_script_name} ]]
    then
        chmod u+x ${temp_script_name}
        source ${temp_script_name}
        execution_error=$?
    fi

    set -e

    # Process errors...
    if [[ ${generation_error} != 0 ]]
    then
        echo ""
        echo "[31m[1mERROR:[0m Errors were encountered and the repository has not been setup for development."
        echo "[31m[1mERROR:[0m"
        echo "[31m[1mERROR:[0m     [${DEVELOPMENT_ENVIRONMENT_FOUNDATION}/RepositoryBootstrap/Impl/Setup.py failed]"
        echo "[31m[1mERROR:[0m"
        echo ""

        exit -1
    fi

    if [[ ${execution_error} != 0 ]]
    then
        echo ""
        echo "[31m[1mERROR:[0m Errors were encountered and the repository has not been setup for development."
        echo "[31m[1mERROR:[0m"
        echo "[31m[1mERROR:[0m     [${temp_script_name} failed]"
        echo "[31m[1mERROR:[0m"
        echo ""

        exit -1
    fi

    # Success
    rm ${temp_script_name}

    if [[ ${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME} == DefaultEnv ]]
    then
        echo ""
        echo ""
        ${_python_binary} -m RepositoryBootstrap.Impl.PanelPrint "The repository has been setup for development. Please run Activate.sh within a new terminal window to begin development with this repository." "bold green"
        echo ""
        echo ""
    else
        echo ""
        echo ""
        ${_python_binary} -m RepositoryBootstrap.Impl.PanelPrint "The repository has been setup for development. Please run Activate.${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}.sh within a new terminal window to begin development with this repository." "bold green"
        echo ""
        echo ""
    fi
fi

export LD_LIBRARY_PATH=${prev_ld_library_path}
unset PYTHONPATH
