@REM ----------------------------------------------------------------------
@REM |
@REM |  Setup.cmd
@REM |
@REM |  David Brownell <db@DavidBrownell.com>
@REM |      2022-08-07 14:56:51
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
@REM    DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME
@REM

set PYTHONPATH=%~dp0..\..;%~dp0..\..\Libraries\Python\Common_Foundation\src

set _DEVELOPMENT_ENVIRONMENT_FIRST_ARG=%~1
shift /1

set _DEVELOPMENT_ENVIRONMENT_CLA=

:GetRemainingArgs
if "%~1" NEQ "" (
    set _DEVELOPMENT_ENVIRONMENT_CLA=%_DEVELOPMENT_ENVIRONMENT_CLA% %~1
    shift /1
    goto GetRemainingArgs
)

REM Invoke custom functionality if the first arg is a positional argument
if "%_DEVELOPMENT_ENVIRONMENT_FIRST_ARG%" NEQ "" (
    if "%_DEVELOPMENT_ENVIRONMENT_FIRST_ARG:~,1%" NEQ "-" (
        if "%_DEVELOPMENT_ENVIRONMENT_FIRST_ARG:~,1%" NEQ "/" (

            REM If here, we are invoking special functionality within the setup file; pass all arguments as they
            REM were originally provided.
            %~dp0..\..\Tools\Python\v3.10.6\Windows\x64\%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%\python -m RepositoryBootstrap.Impl.Setup %_DEVELOPMENT_ENVIRONMENT_FIRST_ARG% "%CD%" %_DEVELOPMENT_ENVIRONMENT_CLA%
            set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=%ERRORLEVEL%

            goto Exit
        )
    )
)

REM Create a temporary file that contains output produced by the python script. This lets us quickly bootstrap
REM to the python environment while still executing OS-specific commands.
call :CreateTempScriptName

REM Generate...
echo.
%~dp0..\..\Tools\Python\v3.10.6\Windows\x64\%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%\python -m RepositoryBootstrap.Impl.Setup "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%" "%CD%" %_DEVELOPMENT_ENVIRONMENT_FIRST_ARG% %_DEVELOPMENT_ENVIRONMENT_CLA%
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_GENERATION_ERROR_LEVEL=%ERRORLEVEL%

REM Invoke...
if exist "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%" (
    call "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%"
)
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_EXECUTION_ERROR_LEVEL=%ERRORLEVEL%

REM Process errors...
if "%_DEVELOPMENT_ENVIRONMENT_SCRIPT_GENERATION_ERROR_LEVEL%" NEQ "0" (
    @echo.
    @echo [31m[1mERROR:[0m Errors were encountered and the repository has not been setup for development.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [RepositoryBootstrap\Impl\Setup.py failed]
    @echo [31m[1mERROR:[0m

    goto ErrorExit
)

if "%_DEVELOPMENT_ENVIRONMENT_SCRIPT_EXECUTION_ERROR_LEVEL%" NEQ "0" (
    @echo.
    @echo [31m[1mERROR:[0m Errors were encountered and the repository has not been setup for development.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME% failed]
    @echo [31m[1mERROR:[0m
    @echo.

    goto ErrorExit
)

REM Success
del %_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%

if "%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%" == "DefaultEnv" (
    @echo.
    @echo.
    %~dp0..\..\Tools\Python\v3.10.6\Windows\x64\%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%\python -m RepositoryBootstrap.Impl.PanelPrint "The repository has been setup for development. Please run Activate.cmd within a new terminal window to begin development with this repository." "bold green"
    @echo.
    @echo.

    goto AfterPanel
)

@echo.
@echo.
%~dp0..\..\Tools\Python\v3.10.6\Windows\x64\%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%\python -m RepositoryBootstrap.Impl.PanelPrint "The repository has been setup for development. Please run Activate.%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%.cmd within a new terminal window to begin development with this repository." "bold green"
@echo.
@echo.

:AfterPanel

set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=0
goto Exit

@REM ----------------------------------------------------------------------
:ErrorExit
set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=-1
goto Exit

@REM ----------------------------------------------------------------------
:Exit
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_EXECUTION_ERROR_LEVEL=
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_GENERATION_ERROR_LEVEL=
set _DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME=
set _DEVELOPMENT_ENVIRONMENT_CLA=
set _DEVELOPMENT_ENVIRONMENT_FIRST_ARG=

set PYTHONPATH=

exit /B %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR%

@REM ----------------------------------------------------------------------
@REM |
@REM |  Internal Functions
@REM |
@REM ----------------------------------------------------------------------
:CreateTempScriptName
setlocal EnableDelayedExpansion
set _filename=%CD%\Setup-!RANDOM!-!Time:~6,5!.cmd
endlocal & set _DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME=%_filename%

if exist "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%" goto CreateTempScriptName
goto :EOF
