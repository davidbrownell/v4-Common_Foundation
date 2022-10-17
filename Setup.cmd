@REM ----------------------------------------------------------------------
@REM |
@REM |  Setup.cmd
@REM |
@REM |  David Brownell <db@DavidBrownell.com>
@REM |      2022-08-07 13:30:07
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

@REM ----------------------------------------------------------------------
@REM |
@REM |  Run as:
@REM |      Setup.cmd [--configuration <config_name>] [--verbose] [--debug] [--name <unique_environment_name>]
@REM |
@REM |      Where:
@REM |          --configuration <config_name>    : Name of the configuration to setup (this value can appear
@REM |                                             multiple times on the command line). All available
@REM |                                             configurations are setup if none are explicitly provided.
@REM |
@REM |          --force                          : Force setup.
@REM |          --verbose                        : Verbose output.
@REM |          --debug                          : Includes debug output (in adddition to verbose output).
@REM |
@REM |          --name <unique_environment_name> : Setup an environment with a unique name. This allows for the
@REM |                                             creation of side-by-side environments that are otherwise identical.
@REM |                                             It is very rare to setup an environment with a unique name.
@REM |
@REM |          --interactive/--no-interactive   : Set the default value for `is_interactive` for those repositories that
@REM |                                             provide those capabilities during setup.
@REM |
@REM |          --search-depth <value>           : Limit searches for other repositories to N levels deep. This value
@REM |                                             can help to decrease the overall search times when a dependency
@REM |                                             repository is not on the system. Coversely, this value can be set
@REM |                                             to a higher value to not artifically limit searches when a dependency
@REM |                                             repsitory is on the system but not found using default values.
@REM |          --max-num-searches <value>       : Limits the maximum number of searches performed when looking for
@REM |                                             dependency repositories.
@REM |          --required-ancestor-dir <value>  : Restrict searches to this directory when searching for dependency
@REM |                                             repositories (this value can appear multiple times on the command
@REM |                                             line).
@REM |
@REM |          --no-hooks                       : Do not install Source Control Management (SCM) hooks for this repository
@REM |                                             (pre-commit, post-commit, etc.).
@REM |
@REM ----------------------------------------------------------------------

@REM ----------------------------------------------------------------------
@REM Begin bootstrap customization (1 of 3)
@REM   The following steps are unique to setup of this repository, as this repsitory serves as the
@REM   foundation for all others.

set _PREV_DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME=%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%
set _PREV_DEVELOPMENT_ENVIRONMENT_FOUNDATION=%DEVELOPMENT_ENVIRONMENT_FOUNDATION%

@REM This should match the value in RepositoryBootstrap/Constants.py:DEFAULT_ENVIRONMENT_NAME
set DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME=DefaultEnv
set DEVELOPMENT_ENVIRONMENT_FOUNDATION=%~dp0

set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=0

@REM Only run the foundation setup if we are in a standard setup scenario
set _SETUP_FIRST_ARG=%~1

if "%_SETUP_FIRST_ARG%" NEQ "" (
    if "%_SETUP_FIRST_ARG:~,1%" NEQ "/" (
        if "%_SETUP_FIRST_ARG:~,1%" NEQ "-" (
            goto AfterFoundationSetup
        )
    )
)

set _SETUP_CLA=

@REM Note that the following loop has been crafted to work around batch's crazy
@REM expansion rules. Modify at your own risk!
:GetRemainingArgs_Begin

if "%~1"=="" goto GetRemainingArgs_End

set _ARG=%~1

if "%_ARG:~,6%"=="--name" goto GetRemainingArgs_Name

@REM If here, we are looking at an arg that should be passed to the script
set _SETUP_CLA=%_SETUP_CLA% "%_ARG%"
goto GetRemainingArgs_Continue

:GetRemainingArgs_Name
@REM If here, we are looking at a name argument
shift /1
set DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME=%1
shift /1
goto GetRemainingArgs_Continue

:GetRemainingArgs_Continue
shift /1
goto GetRemainingArgs_Begin

:GetRemainingArgs_End

echo.
echo ----------------------------------------------------------------------
echo ^|
echo ^|  Setting up foundational tools
echo ^|
echo ----------------------------------------------------------------------
echo.

@REM ----------------------------------------------------------------------
@REM | 7zip
if %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR%==0 (
    call "%~dp0Tools\7zip\v22.1\Windows\Setup.cmd" "%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%"
    set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=%ERRORLEVEL%

    set _DEVELOPMENT_ENVIRONMENT_SETUP_TEMPORARY_7ZIP_EXE=%~dp0Tools\7zip\v22.1\Windows\%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%\7z.exe
)

@REM ----------------------------------------------------------------------
@REM | Python v3.10.6
if %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR%==0 (
    call "%~dp0Tools\Python\v3.10.6\Windows\x64\Setup.cmd" "%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%"
    set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=%ERRORLEVEL%
)

@REM ----------------------------------------------------------------------
if %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR% NEQ 0 (
    @echo.
    @echo [31m[1mERROR:[0m Errors were encountered and the repository has not been setup for development.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [Foundation Setup]
    @echo [31m[1mERROR:[0m

    goto end
)

echo.
echo ----------------------------------------------------------------------
echo.

:AfterFoundationSetup

@REM End bootstrap customization (1 of 3)
@REM ----------------------------------------------------------------------

if "%DEVELOPMENT_ENVIRONMENT_FOUNDATION%"=="" (
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m Please run this script within an activated environment.
    @echo [31m[1mERROR:[0m

    goto end
)

pushd "%~dp0"
call "%DEVELOPMENT_ENVIRONMENT_FOUNDATION%\RepositoryBootstrap\Impl\Setup.cmd" %_SETUP_CLA%
set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=%ERRORLEVEL%
popd

@REM ----------------------------------------------------------------------
@REM Begin bootstrap customization (2 of 3)

set DEVELOPMENT_ENVIRONMENT_FOUNDATION=%_PREV_DEVELOPMENT_ENVIRONMENT_FOUNDATION%
set DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME=%_PREV_DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%

:end
set _ARG=
set _SETUP_CLA=
set _ENVIRONMENT_NAME=
set _SETUP_FIRST_ARG=
set _PREV_DEVELOPMENT_ENVIRONMENT_FOUNDATION=
set _PREV_DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME=
set _DEVELOPMENT_ENVIRONMENT_SETUP_TEMPORARY_7ZIP_EXE=

@REM End bootstrap customization (2 of 3)
@REM ----------------------------------------------------------------------

if %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR% NEQ 0 (exit /B %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR%)

@REM ----------------------------------------------------------------------
@REM Begin bootstrap customization (3 of 3)

@REM :end

@REM End bootstrap customization (3 of 3)
@REM ----------------------------------------------------------------------
