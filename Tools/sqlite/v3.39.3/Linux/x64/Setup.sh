#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  Setup.sh
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 23:47:11
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

setup_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
pushd ${setup_dir} > /dev/null       # +dir

echo "Setting up sqlite v3.39.3..."

if [[ ! -d "$1" ]]
then
    echo "  Unpacking content..."

    temp_dir=/tmp/sqlite

    [[ ! -d ${temp_dir} ]] || rm -Rfd ${temp_dir}
    mkdir -p ${temp_dir}

    pushd ${temp_dir} > /dev/null           # +temp_dir

    tar -xzf ${setup_dir}/install.tgz
    mkdir -p "${setup_dir}/$1"
    mv * "${setup_dir}/$1"

    popd > /dev/null                        # -temp_dir
    rmdir ${temp_dir}
fi

# Link to the originally compiled location
if [[ ! -e /opt/Common_Foundation/sqlite/3.39.3 ]]
then
    [[ -d /opt/Common_Foundation/sqlite ]] || mkdir -p "/opt/Common_Foundation/sqlite"
    ln -fsd "${setup_dir}/$1" /opt/Common_Foundation/sqlite/3.39.3
fi

echo "DONE!"
echo

popd > /dev/null                            # -dir
