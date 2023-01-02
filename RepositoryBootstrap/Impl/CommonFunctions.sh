#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  CommonFunctions.sh
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 16:51:20
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------

# Provide common functionality that differs between Darwin and other Linuxes

if [[ ${OSTYPE} == *darwin* ]]
then
    export is_darwin=1

    # Perform OS-specific bootstrap functionality
    function bootstrap_func() {
        echo "----------------------------------------------------------------------"
        echo "|                                                                    |"
        echo "|                    Bootstrapping for OSX                           |"
        echo "|                                                                    |"
        echo "----------------------------------------------------------------------"

        echo "----------------------------------------------------------------------"
        echo "|  Processing coreutils"
        [[ $(sudo -u ${SUDO_USER} brew list --versions coreutils) ]] || sudo -u ${SUDO_USER} brew install coreutils
        echo

        echo "----------------------------------------------------------------------"
        echo "|  Processing p7zip"
        [[ $(sudo -u ${SUDO_USER} brew list --versions p7zip) ]] || sudo -u ${SUDO_USER} brew install p7zip
        echo
    }

    # Proxy for `readlink`.
    #
    #   Args:
    #       $1: filename of link to read
    #
    function readlink_func() {
        echo $(greadlink -f $1)
    }

    # Proxy for `ln` when creating a link to a directory.
    #
    #   Args:
    #       $1: target
    #       $2: link name
    #
    function ln_dir_func() {
        ln -fs $1 $2
    }

    # Proxy for `ln` when creating a link to a file.
    #
    #   Args:
    #       $1: target
    #       $2: link name
    #
    function ln_file_func() {
        ln -fs $1 $2

    }

    # Makes a temp file.
    #
    #   Args:
    #       None
    #
    function mktemp_func() {
        mktemp TempFile.XXXXXX
    }

else
    export is_darwin=0

    function bootstrap_func() {
        : # Nothing to do here
    }

    # Proxy for `readlink`.
    #
    #   Args:
    #       $1: filename of link to read
    #
    function readlink_func() {
        echo $(readlink -f $1)
    }

    # Proxy for `ln` when creating a link to a directory.
    #
    #   Args:
    #       $1: target
    #       $2: link name
    #
    function ln_dir_func() {
        ln -fsd $1 $2
    }

    # Proxy for `ln` when creating a link to a file.
    #
    #   Args:
    #       $1: target
    #       $2: link name
    #
    function ln_file_func() {
        ln -fs $1 $2
    }

    # Makes a temp file.
    #
    #   Args:
    #       None
    #
    function mktemp_func() {
        mktemp
    }
fi
