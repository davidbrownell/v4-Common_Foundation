#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  Deactivate.sh
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 23:59:24
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
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

if [[ "${DEVELOPMENT_ENVIRONMENT_FOUNDATION}" = ="" ]]
then
    echo ""
    echo "[31m[1mERROR:[0m ERROR: It does not appear that this environment has been activated."
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m     [DEVELOPMENT_ENVIRONMENT_FOUNDATION was not defined]"
    echo "[31m[1mERROR:[0m"

    should_continue=0
fi

echo ""

# Ensure that the script is being invoked via source (as it modifies the current environment)
if [[ ${should_continue} == 1 && ${0##*/} == Deactivate.sh ]]
then
    echo ""
    echo "[31m[1mERROR:[0m This script deactivates removes all environment customizations applied during activation."
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m Because this process makes changes to environment variables, it must be run within the current context."
    echo "[31m[1mERROR:[0m To do this, please source (run) the script as follows:"
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m     source ./Deactivate.sh"
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m         - or -"
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m     . ./Deactivate.sh"
    echo "[31m[1mERROR:[0m"
    echo ""

    should_continue=0
fi

# Generate...
if [[ ${should_continue} == 1 ]]
then
    temp_script_name=$(mktemp_func)
    [[ ! -e ${temp_script_name} ]] || rm -f "${temp_script_name}"

    python -m RepositoryBootstrap.Impl.Deactivate "${temp_script_name}" "$@"
    generation_error=$?

    if [[ -e ${temp_script_name} ]]
    then
        chmod u+x ${temp_script_name}
        source ${temp_script_name}
    fi
    execution_error=$?

    if [[ ${generation_error} != 0 ]]
    then
        echo ""
        echo "[31m[1mERROR:[0m Errors were encountered and the environment has not been successfully deactivated."
        echo "[31m[1mERROR:[0m"
        echo "[31m[1mERROR:[0m     [${DEVELOPMENT_ENVIRONMENT_FOUNDATION}/RepositoryBootstrap/Impl/Dectivate.py failed]"
        echo "[31m[1mERROR:[0m"
        echo ""

        should_continue=0

    elif [[ ${execution_error} != 0 ]]
    then
        echo ""
        echo "[31m[1mERROR:[0m Errors were encountered and the environment has not been successfully deactivated."
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
    echo "[31m[1m-------------------------------------------[0m"
    echo "[31m[1m|                                         |[0m"
    echo "[31m[1m|  The environment has been deactivated.  |[0m"
    echo "[31m[1m|                                         |[0m"
    echo "[31m[1m-------------------------------------------[0m"
    echo ""
    echo ""
fi
