#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  Enlists and setups a repository and its dependencies.
# |
# |  Run as:
# |      Bootstrap.sh <common code dir> [--name <unique_environment_name>] [Optional Setup.cmd args]*
# |
# |      Where:
# |          <common code dir>                : Name of the directory in which common dependencies are enlisted.
# |                                             This location can be reused across multiple projects and
# |                                             enlistments.
# |
# |          --name <unique_environment_name> : Setup an environment with a unique name. This allows for the
# |                                             creation of side-by-side environments that are otherwise identical.
# |                                             It is very rare to setup an environment with a unique name.
# |
# |          [Optional Setup.sh args]         : Any additional args passed to Setup.cmd for the respository
# |                                             and its dependencies. See Setup.cmd for more information on
# |                                             the possible arguments and their use.
# |
# ----------------------------------------------------------------------
set -e                                      # Exit on error
set +v                                      # Disable output

should_continue=1

if [[ ${should_continue} == 1 && ${DEVELOPMENT_ENVIRONMENT_REPOSITORY_ACTIVATED_KEY} ]]; then
    echo ""
    echo "[31m[1mERROR:[0m ERROR: Please run this script from a standard (non-activated) command prompt."
    echo "[31m[1mERROR:[0m"
    echo ""

    should_continue=0
fi

if [[ ${should_continue} == 1 ]]; then
    # Parse the args
    name=""
    next_is_name=0

    no_hooks_arg=""
    force_arg=""
    verbose_arg=""
    debug_arg=""

    ARGS=()

    for var in "${@:2}"; do
        if [[ $next_is_name == 1 ]]; then
            name=$var
            next_is_name=0
        elif [[ $var == --name ]]; then
            next_is_name=1
        else
            ARGS+=("$var")
        fi

        if [[ $var == --no-hooks ]]; then
            no_hooks_arg=$var
        elif [[ $var == --force ]]; then
            force_arg=$var
        elif [[ $var == --verbose ]]; then
            verbose_arg=$var
        elif [[ $var == --debug ]]; then
            debug_arg=$var
        fi
    done

    if [[ ! -z "${name}" ]]; then
        name_arg="--name ${name}"
    else
        name_arg=""
    fi
fi

if [[ ${should_continue} == 1 ]]; then
    "./Setup.sh" ${name_arg} ${no_hooks_arg} ${force_arg} ${verbose_arg} ${debug_arg}
fi
