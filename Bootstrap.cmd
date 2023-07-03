@echo off
@REM ----------------------------------------------------------------------
@REM |
@REM |  Enlists and setups a repository and its dependencies.
@REM |
@REM |  Run as:
@REM |      Bootstrap.cmd <common code dir> [--name <unique_environment_name>] [Optional Setup.cmd args]*
@REM |
@REM |      Where:
@REM |          <common code dir>                : Name of the directory in which common dependencies are enlisted.
@REM |                                             This location can be reused across multiple projects and
@REM |                                             enlistments.
@REM |
@REM |          --name <unique_environment_name> : Setup an environment with a unique name. This allows for the
@REM |                                             creation of side-by-side environments that are otherwise identical.
@REM |                                             It is very rare to setup an environment with a unique name.
@REM |
@REM |          [Optional Setup.cmd args]        : Any additional args passed to Setup.cmd for the respository
@REM |                                             and its dependencies. See Setup.cmd for more information on
@REM |                                             the possible arguments and their use.
@REM |
@REM ----------------------------------------------------------------------

if "%DEVELOPMENT_ENVIRONMENT_REPOSITORY_ACTIVATED_KEY%" NEQ "" (
    @echo.
    @echo [31m[1mERROR:[0m ERROR: Please run this script from a standard ^(non-activated^) command prompt.
    @echo [31m[1mERROR:[0m
    @echo.

    set _ERRORLEVEL=-1
    goto Exit
)

@REM ----------------------------------------------------------------------
@REM Parse the args

set _NO_HOOKS_ARG=
set _FORCE_ARG=
set _VERBOSE_ARG=
set _DEBUG_ARG=

@REM Note that the following loop has been crafted to work around batch's crazy
@REM expansion rules. Modify at your own risk!
:GetRemainingArgs_Begin

if "%~1"=="" goto GetRemainingArgs_End

set _ARG=%~1

if "%_ARG:~,6%"=="--name" goto GetRemainingArgs_Name

if "%_ARG%"=="--no_hooks" (
    set _NO_HOOKS_ARG=%_ARG%
)
if "%_ARG%"=="--force" (
    set _FORCE_ARG=%_ARG%
)
if "%_ARG%"=="--verbose" (
    set _VERBOSE_ARG=%_ARG%
)
if "%_ARG%"=="--debug" (
    set _DEBUG_ARG=%_ARG%
)

@REM If here, we are looking at an arg that should be passed to the script
set _BOOTSTRAP_CLA=%_BOOTSTRAP_CLA% "%_ARG%"
goto GetRemainingArgs_Continue

:GetRemainingArgs_Name
@REM If here, we are looking at a name argument
shift /1
set _BOOTSTRAP_NAME=%1
goto GetRemainingArgs_Continue

:GetRemainingArgs_Branch
@REM If here, we are looking at a branch argument
shift /1
set _CUSTOM_BRANCH=%1
goto GetRemainingArgs_Continue

:GetRemainingArgs_Continue
shift /1
goto GetRemainingArgs_Begin

:GetRemainingArgs_End

set _BOOTSTRAP_NAME_ARG=
if "%_BOOTSTRAP_NAME%" NEQ "" (
    set _BOOTSTRAP_NAME_ARG=--name "%_BOOTSTRAP_NAME%"
)

@REM ----------------------------------------------------------------------
call %~dp0\Setup.cmd %_BOOTSTRAP_NAME_ARG% %_NO_HOOKS_ARG% %_FORCE_ARG% %_VERBOSE_ARG% %_DEBUG_ARG%
if %ERRORLEVEL% NEQ 0 (
    set _ERRORLEVEL=%ERRORLEVEL%
    goto Exit
)

@REM ----------------------------------------------------------------------
:Exit
set _ARG=
set _DEBUG_ARG=
set _VERBOSE_ARG=
set _FORCE_ARG=
set _NO_HOOKS_ARG=
set _BOOTSTRAP_CLA=
set _BOOTSTRAP_NAME=
set _BOOTSTRAP_NAME_ARG=

exit /B %_ERRORLEVEL%
