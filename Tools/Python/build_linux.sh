#!/bin/bash
# ----------------------------------------------------------------------
# |
# |  build_linux.sh
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 14:20:07
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
set -x                                      # statements

# Builds python code using docker
#
# Docker command:
#
#   CentOS 8 Image
#   --------------
#       [Linux Host]     docker run -it --rm -v `pwd`/..:/local centos:8 bash /local/Python/build_linux.sh <3.10.6>
#       [Windows Host]   docker run -it --rm -v %cd%\..:/local  centos:8 bash /local/Python/build_linux.sh <3.10.6>
#
#   CentOS 7 Image
#   --------------
#       [Linux Host]     docker run -it --rm -v `pwd`/..:/local centos:7 bash /local/Python/build_linux.sh <3.10.6>
#       [Windows Host]   docker run -it --rm -v %cd%\..:/local  centos:7 bash /local/Python/build_linux.sh <3.10.6>
#
#   CentOS 6.10 Image [OFFICIAL RELEASE]
#   ------------------------------------
#       [Linux Host]     docker run -it --rm -v `pwd`/..:/local centos:6.10 bash /local/Python/build_linux.sh <3.10.6>
#       [Windows Host]   docker run -it --rm -v %cd%\..:/local  centos:6.10 bash /local/Python/build_linux.sh <3.10.6>
#
#   Holy Build Box Image
#   --------------------
#   NOTE THAT THIS DOESN'T WORK RIGHT NOW with optimizations, errors during build
#
#       [Linux Host]     docker run -it --rm -v `pwd`/..:/local phusion/holy-build-box-64 bash /local/Python/build_linux.sh <3.10.6>
#       [Windows Host]   docker run -it --rm -v %cd%\..:/local  phusion/holy-build-box-64 bash /local/Python/build_linux.sh <3.10.6>
#

if [[ "$1" == "3.10.6" ]]
then
    PYTHON_VERSION=3.10.6
    PYTHON_VERSION_SHORT=3.10
    PYTHON_VERSION_SHORTER=3

    OPENSSL_VERSION=1.1.1
    OPENSSL_VERSION_SHORT=1.1
    OPENSSL_VERSION_SHORTER=1

    LIBFFI_VERSION=3.4.2

    SQLITE_VERSION=3.39.3
    SQLITE_VERSION_RAW=3390300
else
    echo "Invalid python version; expected 3.10.6"
    exit
fi

is_centos_8=0
is_centos_7=0
is_centos_6=0
is_hbb=0

if [[ -e /hbb_exe/activate-exec ]];
then
    is_hbb=1
elif [[ `cat /etc/centos-release` == *release[[:space:]]8* ]]
then
    is_centos_8=1
elif [[ `cat /ect/centos-release` == *release[[:space:]]7* ]]
then
    is_centos_7=1
elif [[ `cat /etc/centos-release` == *6.10* ]]
then
    is_centos_6=1
fi

UpdateEnvironment()
{
    set +x
    echo "# ----------------------------------------------------------------------"
    echo "# |"
    echo "# |  Updating Development Environment"
    echo "# |"
    echo "# ----------------------------------------------------------------------"
    set -x

    if [[ ${is_hbb} == 1 ]];
    then
        /hbb_exe/activate-exec
    else
        if [[ ${is_centos_8} == 1 ]];
        then
            pushd /etc/yum.repos.d/ > /dev/null

            sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-*
            sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-*

            popd > /dev/null
        elif [[ ${is_centos_6} == 1 ]];
        then
            if [[ ! -e updated_centos6_repo_sentinel ]];
            then
                curl https://www.getpagespeed.com/files/centos6-eol.repo --output /etc/yum.repos.d/CentOS-Base.repo
                touch updated_centos6_repo_sentinel
            fi
        fi

        yum update -y
        yum groupinstall -y "Development Tools"
    fi

    yum install -y \
        bzip2-devel \
        gdbm-devel \
        libffi-devel \
        ncurses-devel \
        readline-devel \
        sqlite-devel \
        tk-devel \
        xz-devel \
        zlib-devel

    if [[ ${is_centos_8} == 1 ]];
    then
        yum install -y \
            python2

        [[ -e /usr/bin/python ]] || ln /usr/bin/python2 /usr/bin/python
    elif [[ ${is_centos_6} == 1 ]];
    then
        yum install -y \
            libuuid \
            libuuid-devel \
            sqlite-devel \
            uuid-devel
    fi
}

BuildOpenSSL()
{
    set +x
    echo "# ----------------------------------------------------------------------"
    echo "# |"
    echo "# |  Building OpenSSL"
    echo "# |"
    echo "# ----------------------------------------------------------------------"
    set -x

    [[ ! -e openssl-${OPENSSL_VERSION} ]] || rm -rfd openssl-${OPENSSL_VERSION}
    [[ ! -e /opt/Common_Foundation/openssl/${OPENSSL_VERSION} ]] || rm -rfd /opt/Common_Foundation/openssl/${OPENSSL_VERSION}

    curl -L https://www.openssl.org/source/old/${OPENSSL_VERSION}/openssl-${OPENSSL_VERSION}.tar.gz | gunzip -c | tar xf -

    pushd openssl-${OPENSSL_VERSION} > /dev/null

    ./config \
        --prefix=/opt/Common_Foundation/openssl/${OPENSSL_VERSION} \
        shared

    make clean
    make
    make install

    pushd /opt/Common_Foundation/openssl/${OPENSSL_VERSION} > /dev/null

    pushd lib > /dev/null
    [[ -e libcrypto.so.${OPENSSL_VERSION_SHORTER} ]] || ln -fs libcrypto.so.${OPENSSL_VERSION_SHORT} libcrypto.so.${OPENSSL_VERSION_SHORTER}
    [[ -e libssl.so.${OPENSSL_VERSION_SHORTER} ]] || ln -fs libssl.so.${OPENSSL_VERSION_SHORT} libssl.so.${OPENSSL_VERSION_SHORTER}
    popd > /dev/null

    tar czf - * > /local/openssl/v${OPENSSL_VERSION}/Linux/x64/install.tgz
    popd > /dev/null
    popd > /dev/null
}

BuildLibFFI()
{
    set +x
    echo "# ----------------------------------------------------------------------"
    echo "# |"
    echo "# |  Building libffi"
    echo "# |"
    echo "# ----------------------------------------------------------------------"
    set -

    [[ ! -e libffi-${LIBFFI_VERSION} ]] || rm -rfd libffi-${LIBFFI_VERSION}
    [[ ! -e /opt/Common_Foundation/libffi/${LIBFFI_VERSION} ]] || rm -rfd /opt/Common_Foundation/libffi/${LIBFFI_VERSION}

    curl -L https://github.com/libffi/libffi/releases/download/v${LIBFFI_VERSION}/libffi-${LIBFFI_VERSION}.tar.gz | tar zx

    pushd libffi-${LIBFFI_VERSION}

    ./configure \
        --prefix=/opt/Common_Foundation/libffi/${LIBFFI_VERSION} \
        --enable-portable-binary

    make clean
    make
    make install

    pushd /opt/Common_Foundation/libffi/${LIBFFI_VERSION} > /dev/null
    tar czf - * > /local/libffi/v${LIBFFI_VERSION}/Linux/x64/install.tgz
    popd > /dev/null
    popd > /dev/null
}

BuildSqlite()
{
    set +x
    echo "# ----------------------------------------------------------------------"
    echo "# |"
    echo "# |  Building sqlite"
    echo "# |"
    echo "# ----------------------------------------------------------------------"
    set -x

    [[ ! -e sqlite-src-${SQLITE_VERSION_RAW}.zip ]] || rm -f sqlite-src-${SQLITE_VERSION_RAW}.zip
    [[ ! -e sqlite-src-${SQLITE_VERSION_RAW} ]] || rm -rfd sqlite-src-${SQLITE_VERSION_RAW}
    [[ ! -e /opt/Common_Foundation/sqlite/${SQLITE_VERSION} ]] || rm -rfd /opt/Common_Foundation/sqlite/${SQLITE_VERSION}

    curl -L https://www.sqlite.org/2022/sqlite-src-${SQLITE_VERSION_RAW}.zip -o sqlite-src-${SQLITE_VERSION_RAW}.zip
    unzip -q sqlite-src-${SQLITE_VERSION_RAW}
    rm -f sqlite-src-${SQLITE_VERSION_RAW}.zip

    pushd sqlite-src-${SQLITE_VERSION_RAW} > /dev/null

    ./configure --prefix=/opt/Common_Foundation/sqlite/${SQLITE_VERSION}

    make clean
    make
    make install

    pushd /opt/Common_Foundation/sqlite/${SQLITE_VERSION} > /dev/null
    tar czf - * > /local/sqlite/v${SQLITE_VERSION}/Linux/x64/install.tgz
    popd > /dev/null
    popd > /dev/null
}

BuildPython()
{
    set +x
    echo "# ----------------------------------------------------------------------"
    echo "# |"
    echo "# |  Building Python"
    echo "# |"
    echo "# ----------------------------------------------------------------------"
    set -x

    [[ ! -e Python-${PYTHON_VERSION} ]] || rm -rfd Python-${PYTHON_VERSION}
    [[ ! -e /opt/Common_Foundation/python/${PYTHON_VERSION} ]] || rm -rfd /opt/Common_Foundation/python/${PYTHON_VERSION}

    curl -L https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz | gunzip -c | tar xf -

    pushd Python-${PYTHON_VERSION} > /dev/null

    # I tried to do this "the right way" with sed, but sed operates on lines at a time and there are
    # duplicated lines in the file that we are attempting to modify. Using a python script instead.

    # Update Setup
    [[ -e ./Modules/Setup.bak ]] || cp ./Modules/Setup ./Modules/Setup.bak
    [[ -e ./setup.py.bak ]] || cp ./setup.py ./setup.py.bak
    [[ ! -e ./update_setup_files.py ]] || rm ./update_setup_files.py

    if [[ ${PYTHON_VERSION} == 3.10.6 ]];
    then
        cat <<EOF >> update_setup_files.py
import re
import sys
import textwrap

# ./Modules/Setup
with open("./Modules/Setup.bak") as f:
    content = f.read()

regex = re.compile(
    r"^# OPENSSL=/path/to/openssl/directory\s+(?:#[^\n]+\n)+$",
    re.DOTALL | re.MULTILINE,
)

new_content = regex.sub(
    textwrap.dedent(
        """\\
        OPENSSL=/opt/Common_Foundation/openssl/{version}
        _ssl _ssl.c \\\\
            -I{dollar_sign}(OPENSSL)/include -L{dollar_sign}(OPENSSL)/lib \\\\
            -lssl -lcrypto
        _hashlib _hashopenssl.c \\\\
            -I{dollar_sign}(OPENSSL)/include -L{dollar_sign}(OPENSSL)/lib \\\\
            -lcrypto
        """,
    ).format(
        version=sys.argv[1],
        dollar_sign="$",
    ),
    content,
)

assert new_content != content

with open("./Modules/Setup", "w") as f:
    f.write(new_content)
EOF
    else
        error "Update this for the new version of python!"
        return -1
    fi

    python update_setup_files.py ${OPENSSL_VERSION}

    cpp_flags="\
-I/opt/Common_Foundation/sqlite/${SQLITE_VERSION}/include \
"

    export CPPFLAGS="${CPPFLAGS} ${cpp_flags}"

    ld_flags="\
-L/opt/Common_Foundation/openssl/${OPENSSL_VERSION}/lib \
-L/opt/Common_Foundation/libffi/${LIBFFI_VERSION}/lib64 \
-L/opt/Common_Foundation/sqlite/${SQLITE_VERSION}/lib \
-Wl,-rpath,/opt/Common_Foundation/openssl/${OPENSSL_VERSION}/lib \
-Wl,-rpath,/opt/Common_Foundation/libffi/${LIBFFI_VERSION}/lib64 \
-Wl,-rpath,/opt/Common_Foundation/sqlite/${SQLITE_VERSION}/lib \
"
    export LDFLAGS="${LDFLAGS} ${ld_flags}"

    if [[ ${is_hbb} == 1 ]] || [[ ${is_centos_7} == 1 ]];
    then
        ./configure \
            --prefix=/opt/Common_Foundation/python/${PYTHON_VERSION} \
            --enable-shared \
            --enable-ipv6 \
            --with-openssl=/opt/Common_Foundation/openssl/${OPENSSL_VERSION} \
            --with-openssl-rpath=auto
    else
        ./configure \
            --prefix=/opt/Common_Foundation/python/${PYTHON_VERSION} \
            --enable-shared \
            --enable-optimizations \
            --enable-ipv6 \
            --with-openssl=/opt/Common_Foundation/openssl/${OPENSSL_VERSION} \
            --with-openssl-rpath=auto
    fi

    make clean
    make
    make altinstall

    if [[ ${is_hbb} == 1 ]];
    then
        env LIBCHECK_ALLOW="libpython${PYTHON_VERSION_SHORT}|libssl|libcrypto" /hbb/bin/libcheck /opt/Common_Foundation/python/${PYTHON_VERSION}/bin/python${PYTHON_VERSION_SHORT}
    fi

    pushd /opt/Common_Foundation/python/${PYTHON_VERSION} > /dev/null

    pushd ./bin > /dev/null

    ln -fs python${PYTHON_VERSION_SHORT} python
    ln -fs python${PYTHON_VERSION_SHORT} python${PYTHON_VERSION_SHORTER}

    popd > /dev/null

    export PATH=/opt/Common_Foundation/python/${PYTHON_VERSION}/bin:${PATH}
    export LD_LIBRARY_PATH=/opt/Common_Foundation/python/${PYTHON_VERSION}/lib:${LD_LIBRARY_PATH}

    python -m ensurepip --default-pip
    python -m pip install --upgrade pip==22.2.*

    # These values should match the values found in ../../Setup_custom.py
    python -m pip install \
        colorama==0.4.* \
        inflect==6.0.* \
        requests==2.28.* \
        rich==12.5.* \
        semantic_version==2.10.* \
        setuptools==63.2.* \
        typer==0.6.* \
        virtualenv==20.16.* \
        wheel==0.37.* \
        wrapt==1.14.*

    python -m pip install \
        distro==1.7.*

    tar czf - * > /local/Python/v${PYTHON_VERSION}/Linux/x64/install.tgz

    popd > /dev/null
    popd > /dev/null
}

[[ -d /src ]] || mkdir /src
pushd /src > /dev/null

UpdateEnvironment
BuildOpenSSL
BuildLibFFI
BuildSqlite
BuildPython

popd > /dev/null

set +x
echo "DONE!"
