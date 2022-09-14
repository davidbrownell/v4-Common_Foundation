#!/bin/bash
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
# |          --verbose                        : Verbose output.
# |          --debug                          : Includes debug output (in adddition to verbose output).
# |
# |          --name <unique_environment_name> : Setup an environment with a unique name. This allows for the
# |                                             creation of side-by-side environments that are otherwise identical.
# |                                             It is very rare to setup an environment with a unique name.
# |
# ----------------------------------------------------------------------
set -e                                      # Exit on error
set +v                                      # Disable output

if [[ "${DEVELOPMENT_ENVIRONMENT_FOUNDATION}" == "" ]]; then
    echo ""
    echo "[31m[1mERROR:[0m Please run this script within an activated environment."
    echo "[31m[1mERROR:[0m"
    echo ""

    exit -1
fi

pushd "$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )" > /dev/null
source $DEVELOPMENT_ENVIRONMENT_FOUNDATION/RepositoryBootstrap/Impl/Setup.sh "$@"
popd > /dev/null
