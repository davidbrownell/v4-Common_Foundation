@REM ----------------------------------------------------------------------
@REM |
@REM |  Setup.cmd
@REM |
@REM |  David Brownell <db@DavidBrownell.com>
@REM |      2022-08-07 12:38:42
@REM |
@REM ----------------------------------------------------------------------
@REM |
@REM |  Copyright David Brownell 2022
@REM |  Distributed under the Boost Software License, Version 1.0. See
@REM |  accompanying file LICENSE_1_0.txt or copy at
@REM |  http://www.boost.org/LICENSE_1_0.txt.
@REM |
@REM ----------------------------------------------------------------------
@echo off

pushd "%~dp0"

echo Setting up 7Zip v22.01...

if not exist "%1" (
    echo   Unpacking content...

    if exist ".\unzipping" rmdir /S /Q .\unzipping

    mkdir .\unzipping
    tar xf install.tgz -C .\unzipping

    REM The 'unzipping' dir will not exist if powershell does not exist. However,
    REM that condition doesn't generate an error so we need to determine success
    REM by testing that the expected dir is there or not.

    if not exist ".\unzipping" (
        echo.
        echo     Please ensure that PowerShell is available. To do this:
        echo.
        echo        1^) Start Menu -^> "Developer Tools"
        echo        2^) Under "Use developer features", check "Developer mode"
        echo        3^) Under "PowerShell", check:
        echo                Change execution policy to allow local
        echo                PowerShell scripts to run without signing.
        echo                Require signing for remote scripts.
        echo        4^) Click "Apply"
        echo.
        goto Done
    )

    mkdir "%1"

    pushd .\unzipping
    xcopy /E /Q /Y . "..\%1"
    popd

    rmdir /S /Q .\unzipping
)

echo DONE!
echo.

:Done
popd
