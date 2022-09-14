@REM ----------------------------------------------------------------------
@REM |
@REM |  Setup.cmd
@REM |
@REM |  David Brownell <db@DavidBrownell.com>
@REM |      2022-08-07 12:26:27
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

@REM The following environment variables are used by this script and must be populated
@REM prior to its invocation:
@REM
@REM    _DEVELOPMENT_ENVIRONMENT_SETUP_TEMPORARY_7ZIP_EXE: Full path to 7za.exe
@REM

pushd "%~dp0"
set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=0

echo Setting up Python 3.10.6...

@REM The following code is written so that we only commit the contents of the extraction after
@REM we know that everything is good. Unfortunately, Windows and/or 7zip are making this difficult
@REM to do due to "access denied" errors. Ideally, we would extract to a temp directory and rename
@REM that directory after extraction is successful. However, there seems to be a periodic timing
@REM issue at play where we are unable to rename the directory due to access is denied errors.
@REM as a work around, extract to the final location and write a file to that location once
@REM extraction has completed successfully.

if exist "%1\SuccessfulInstallation.txt" goto Done

@REM ----------------------------------------------------------------------
echo   Verifying content...
%_DEVELOPMENT_ENVIRONMENT_SETUP_TEMPORARY_7ZIP_EXE% t install.7z >NUL 2>NUL
if %ERRORLEVEL% NEQ 0 (
    set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=%ERRORLEVEL%
    echo     'install.7z' is not in a valid state.
    echo   DONE!
    goto Done
)
echo   DONE!
echo.

echo   Unpacking content...

%_DEVELOPMENT_ENVIRONMENT_SETUP_TEMPORARY_7ZIP_EXE% x -y "-o%1" install.7z
set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=%ERRORLEVEL%
echo.
echo.
echo   DONE!
echo.

if %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR% NEQ 0 goto Done

echo Installation was successful. > "%1\SuccessfulInstallation.txt"

@REM ----------------------------------------------------------------------
:Done
echo DONE!

popd

if %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR% NEQ 0 (
    @echo [31m[1mERROR:[0m
    @echo [31m[1mErrors[0m were encountered while setting up Python 3.10.6.
    @echo [31m[1mERROR:[0m
)

exit /B %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR%
