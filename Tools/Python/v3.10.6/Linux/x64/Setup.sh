#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  Setup.sh
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 15:58:36
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

echo "Setting up Python v3.10.6..."

if [[ ! -d "$1" ]]
then
    echo "  Unpacking content..."

    temp_dir=/tmp/python

    [[ ! -d ${temp_dir} ]] || rm -Rfd ${temp_dir}
    mkdir -p ${temp_dir}

    pushd ${temp_dir} > /dev/null           # +temp_dir

    tar -xzf ${setup_dir}/install.tgz
    mkdir -p "${setup_dir}/$1"
    mv * "${setup_dir}/$1"

    popd > /dev/null                        # -temp_dir
    rmdir ${temp_dir}
fi

echo "  Finalizing..."

# Link to the originally compiled location
if [[ ! -e /opt/Common_Foundation/python/3.10.6 ]]
then
    [[ -d /opt/Common_Foundation/python ]] || mkdir -p "/opt/Common_Foundation/python"
    ln -fsd "${setup_dir}/$1" /opt/Common_Foundation/python/3.10.6
fi

# Convert sep in '-', then remove the initial '-'
conf_file=$(echo $(pwd)/$1/bin/python3.10 | tr / - | cut -c 2-).conf

if [[ ! -e /etc/ld.so.conf.d/${conf_file} ]]
then

cat > /etc/ld.so.conf.d/${conf_file} << END
/opt/Common_Foundation/python/3.10.6/lib
END

    ldconfig
fi

echo "DONE!"
echo ""

setup_python_binary=$(pwd)/$1/bin/python3

popd > /dev/null                            # -dir
