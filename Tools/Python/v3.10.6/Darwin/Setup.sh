#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  Setup.sh
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-13 22:48:47
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

source ${DEVELOPMENT_ENVIRONMENT_FOUNDATION}/RepositoryBootstrap/Impl/CommonFunctions.sh

if [[ ! $(pkgutil --pkgs=org.python.Python.PythonApplications-3.10) ]]
then
    echo "Installing python 3.10.6"
    echo
    installer -pkg ${setup_dir}/python-3.10.6-macos11.pkg -target /
    echo "DONE!"
    echo
    echo
fi

if [[ ! -e  "/Library/Frameworks/Python.framework/Versions/3.10/bin/python" ]]
then
    ln_file_func "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3" "/Library/Frameworks/Python.framework/Versions/3.10/bin/python"
fi

if [[ ! -e  "/Library/Frameworks/Python.framework/Versions/3.10/bin/pip" ]]
then
    ln_file_func "/Library/Frameworks/Python.framework/Versions/3.10/bin/pip3" "/Library/Frameworks/Python.framework/Versions/3.10/bin/pip"
fi

setup_python_binary=/Library/Frameworks/Python.framework/Versions/3.10/bin/python3

/Library/Frameworks/Python.framework/Versions/3.10/bin/pip3 install --disable-pip-version-check \
    setuptools==63.2.0 \
    virtualenv==20.16.3 \
    wheel==0.37.1 \
    colorama==0.4.5 \
    distro==1.7.0 \
    inflect==6.0.0 \
    requests==2.28.1 \
    rich==12.6.0 \
    semantic_version==2.10.0 \
    typer==0.6.1 \
    wrapt==1.14.1

popd > /dev/null                            # -dir
