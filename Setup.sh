#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  Setup.sh
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 16:14:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
set -e                                      # Exit on error
set +v                                      # Disable output

# ----------------------------------------------------------------------
# |
# |  Run as:
# |      Setup.cmd [--configuration <config_name>] [--verbose] [--debug] [--name <unique_environment_name>]
# |
# |      Where:
# |          --configuration <config_name>    : Name of the configuration to setup (this value can appear
# |                                             multiple times on the command line). All available
# |                                             configurations are setup if none are explicitly provided.
# |
# |          --force                          : Force setup.
# |          --verbose                        : Verbose output.
# |          --debug                          : Includes debug output (in adddition to verbose output).
# |
# |          --name <unique_environment_name> : Setup an environment with a unique name. This allows for the
# |                                             creation of side-by-side environments that are otherwise identical.
# |                                             It is very rare to setup an environment with a unique name.
# |
# |          --interactive/--no-interactive   : Set the default value for `is_interactive` for those repositories that
# |                                             provide those capabilities during setup.
# |
# |          --search-depth <value>           : Limit searches for other repositories to N levels deep. This value
# |                                             can help to decrease the overall search times when a dependency
# |                                             repository is not on the system. Coversely, this value can be set
# |                                             to a higher value to not artifically limit searches when a dependency
# |                                             repsitory is on the system but not found using default values.
# |          --max-num-searches <value>       : Limits the maximum number of searches performed when looking for
# |                                             dependency repositories.
# |          --required-ancestor-dir <value>  : Restrict searches to this directory when searching for dependency
# |                                             repositories (this value can appear multiple times on the command
# |                                             line).
# |
# |          --no-hooks                       : Do not install Source Control Management (SCM) hooks for this repository
# |                                             (pre-commit, post-commit, etc.).
# |
# ----------------------------------------------------------------------

# Root is required the first time that this script is invoked (as it updates ldconfig). Root is not
# required if the environment has already been setup.
if [[ $EUID -ne 0 ]] && [[ -z "${DEVELOPMENT_ENVIRONMENT_FOUNDATION}" ]]; then
    echo ""
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m Please run this script as root (via sudo)."
    echo "[31m[1mERROR:[0m"
    echo ""

    exit -1
fi

# ----------------------------------------------------------------------
# Begin bootstrap customization (1 of 2)
#   The following steps are unique to the setup of this repository, as this repository serves as the
#   foundation for all others.

pushd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )" > /dev/null

source ./RepositoryBootstrap/Impl/CommonFunctions.sh
bootstrap_func

prev_development_environment_foundation=${DEVELOPMENT_ENVIRONMENT_FOUNDATION}
prev_development_environment_environment_name=${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}

export DEVELOPMENT_ENVIRONMENT_FOUNDATION=$(dirname "$(readlink_func "${BASH_SOURCE[0]}")")

# Only run the foundation setup if we are in a standard setup scenario
initial_char="$(echo $1 | head -c 1)"
if [[ "${initial_char}" == "" || "${initial_char}" == "-" || "${initial_char}" == "/" ]]
then
    # Get the tools unique name

    # This should match the value in RepositoryBootstrap/Constants.py:DEFAULT_ENVIRONMENT_NAME
    tools_unique_name=DefaultEnv
    next_is_name=0

    ARGS=()

    for var in "$@"; do
        if [[ $next_is_name == 1 ]]; then
            tools_unique_name=$var
            next_is_name=0
        elif [[ $var == --name ]]; then
            next_is_name=1
        else
            ARGS+=("$var")
        fi
    done

    # This should match the value in RepositoryBootstrap/Constants.py:DE_ENVIRONMENT_NAME
    export DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME=${tools_unique_name}
    set -- ${ARGS[@]}

    echo ""
    echo "----------------------------------------------------------------------"
    echo "|"
    echo "|  Setting up foundational tools"
    echo "|"
    echo "----------------------------------------------------------------------"
    echo ""

    this_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

    if [[ ${is_darwin} -eq 1 ]]
    then
        # ----------------------------------------------------------------------
        # |  Python v3.10.6
        source ${this_dir}/Tools/Python/v3.10.6/Darwin/Setup.sh "${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}"
    else
        # ----------------------------------------------------------------------
        # |  7zip
        source ${this_dir}/Tools/7zip/v22.1/Linux/Setup.sh "${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}"

        # ----------------------------------------------------------------------
        # |  libffi
        source ${this_dir}/Tools/libffi/v3.4.2/Linux/x64/Setup.sh "${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}"

        # ----------------------------------------------------------------------
        # |  openssl
        source ${this_dir}/Tools/openssl/v1.1.1/Linux/x64/Setup.sh "${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}"

        # ----------------------------------------------------------------------
        # |  sqlite
        source ${this_dir}/Tools/sqlite/v3.39.3/Linux/x64/Setup.sh "${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}"

        # ----------------------------------------------------------------------
        # |  Python v3.10.6
        source ${this_dir}/Tools/Python/v3.10.6/Linux/x64/Setup.sh "${DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME}"
    fi
fi

# End bootstrap customization (1 of 2)
# ----------------------------------------------------------------------

if [[ "${DEVELOPMENT_ENVIRONMENT_FOUNDATION}" = "" ]]
then
    echo "[31m[1mERROR:[0m"
    echo "[31m[1mERROR:[0m Please run this script within an activated environment."
    echo "[31m[1mERROR:[0m"

    exit -1
fi

pushd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )" > /dev/null
source $DEVELOPMENT_ENVIRONMENT_FOUNDATION/RepositoryBootstrap/Impl/Setup.sh "$@"
popd > /dev/null

# ----------------------------------------------------------------------
# Begin bootstrap customization (2 of 2)

if [[ "${prev_development_environment_foundation}" != "" ]]; then
    export DEVELOPMENT_ENVIRONMENT_FOUNDATION=${prev_development_environment_foundation}
else
    unset DEVELOPMENT_ENVIRONMENT_FOUNDATION
fi

if [[ "${prev_development_environment_environment_name}" != "" ]]; then
    export DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME=${prev_development_environment_environment_name}
else
    unset DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME
fi

popd > /dev/null

# End bootstrap customization (2 of 2)
# ----------------------------------------------------------------------
