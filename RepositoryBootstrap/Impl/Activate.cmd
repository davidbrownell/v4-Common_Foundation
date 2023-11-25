@REM ----------------------------------------------------------------------
@REM |
@REM |  Activate.cmd
@REM |
@REM |  David Brownell <db@DavidBrownell.com>
@REM |      2022-08-10 11:26:26
@REM |
@REM ----------------------------------------------------------------------
@REM |
@REM |  Copyright David Brownell 2022-23
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

REM Read the bootstrap data
if not exist "%CD%\Generated\Windows\%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%\EnvironmentBootstrap.data" (
    @echo.
    @echo [31m[1mERROR:[0m It appears that Setup.cmd has not been run for this repository. Please run Setup.cmd and run this script again.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [%CD%\Generated\Windows\%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%\EnvironmentBootstrap.data was not found]
    @echo [31m[1mERROR:[0m
    @echo.

    goto ErrorExit
)

for /f "tokens=1,2 delims==" %%a in (%CD%\Generated\Windows\%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%\EnvironmentBootstrap.data) do (
    if "%%a"=="foundation_repo" set DEVELOPMENT_ENVIRONMENT_FOUNDATION=%%~fb
    if "%%a"=="is_mixin_repo" set _DEVELOPMENT_ENVIRONMENT_IS_MIXIN_REPOSITORY=%%b
    if "%%a"=="is_configurable" set _DEVELOPMENT_ENVIRONMENT_IS_CONFIGURABLE_REPOSITORY=%%b
)

@REM Get a python version to use for activation

@REM Note that this environment name must match the value assoeciated with DE_ORIGINAL_PATH found in ../Constants.py
set DEVELOPMENT_ENVIRONMENT_ORIGINAL_PATH=%PATH%

set PATH=%DEVELOPMENT_ENVIRONMENT_FOUNDATION%\Tools\Python\v3.10.6\Windows\x64\%DEVELOPMENT_ENVIRONMENT_ENVIRONMENT_NAME%;%PATH%
set PYTHONPATH=%DEVELOPMENT_ENVIRONMENT_FOUNDATION%;%DEVELOPMENT_ENVIRONMENT_FOUNDATION%\Libraries\Python\Common_Foundation\src;%DEVELOPMENT_ENVIRONMENT_FOUNDATION%\Libraries\Python\Common_FoundationEx\src

@REM ----------------------------------------------------------------------
@REM |  List configurations if requested
if "%1" NEQ "ListConfigurations" goto AfterListConfigurations
set _DEVELOPMENT_ENVIRONMENT_CLA=
shift /1

:GetRemainingArgs_ListConfigurations
if "%1" NEQ "" (
    set _DEVELOPMENT_ENVIRONMENT_CLA=%_DEVELOPMENT_ENVIRONMENT_CLA% %1
    shift /1
    goto GetRemainingArgs_ListConfigurations
)

python -m RepositoryBootstrap.Impl.Activate ListConfigurations "%CD%" %_DEVELOPMENT_ENVIRONMENT_CLA%
goto Exit

:AfterListConfigurations

@REM If here, we are in a verified activation scenario. Set the previous value to this value, knowing that that is the value
@REM that will be committed.
set _DEVELOPMENT_ENVIRONMENT_PREVIOUS_FOUNDATION=%DEVELOPMENT_ENVIRONMENT_FOUNDATION%

@REM ----------------------------------------------------------------------
@REM |  Only allow one activated environment at a time (unless we are activating a mixin repo)
if "%_DEVELOPMENT_ENVIRONMENT_IS_MIXIN_REPOSITORY%" NEQ "1" if "%DEVELOPMENT_ENVIRONMENT_REPOSITORY%" NEQ "" if /i "%DEVELOPMENT_ENVIRONMENT_REPOSITORY%" NEQ "%CD%" (
    @echo.
    @echo [31m[1mERROR:[0m Only one repository can be activated within an environment at a time, and it appears as if one is already active. Please open a new terminal and run this script again.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [DEVELOPMENT_ENVIRONMENT_REPOSITORY is already defined as "%DEVELOPMENT_ENVIRONMENT_REPOSITORY%"]
    @echo [31m[1mERROR:[0m

    goto ErrorExit
)

@REM ----------------------------------------------------------------------
@REM |  A mixin repository can't be activated in isolation
if "%_DEVELOPMENT_ENVIRONMENT_IS_MIXIN_REPOSITORY%"=="1" if "%DEVELOPMENT_ENVIRONMENT_REPOSITORY_ACTIVATED_KEY%"=="" (
    @echo.
    @echo [31m[1mERROR:[0m A mixin repository cannot be activated in isolation. Activate another repository before activating this one.
    @echo [31m[1mERROR:[0m
    @echo.

    goto ErrorExit
)

@REM ----------------------------------------------------------------------
@REM |  Prepare the args
if "%_DEVELOPMENT_ENVIRONMENT_IS_CONFIGURABLE_REPOSITORY%" NEQ "0" (
    if "%1" == "" (
        @echo.
        @echo [31m[1mERROR:[0m This repository is configurable, which means that it can be activated in a variety of different ways. Please run this script again with a configuration name provided on the command line.
        @echo [31m[1mERROR:[0m
        @echo [31m[1mERROR:[0m     Available configurations are:
        @echo [31m[1mERROR:[0m
        python -m RepositoryBootstrap.Impl.Activate ListConfigurations "%CD%" --display-format command_line
        @echo [31m[1mERROR:[0m
        @echo.

        goto ErrorExit
    )

    if "%DEVELOPMENT_ENVIRONMENT_REPOSITORY_CONFIGURATION%" NEQ "" (
        if "%DEVELOPMENT_ENVIRONMENT_REPOSITORY_CONFIGURATION%" NEQ "%1" (
            @echo.
            @echo [31m[1mERROR:[0m The environment was previously activated with this repository but used a different configuration. Please open a new terminal window and activate this repository with the new configuration.
            @echo [31m[1mERROR:[0m
            @echo [31m[1mERROR:[0m     ["%DEVELOPMENT_ENVIRONMENT_REPOSITORY_CONFIGURATION%" != "%1"]
            @echo [31m[1mERROR:[0m

            goto ErrorExit
        )
    )

    set _DEVELOPMENT_ENVIRONMENT_CLA=%*
    goto AfterClaArgsSet
)

set _DEVELOPMENT_ENVIRONMENT_FIRST_ARG=%1

if "%_DEVELOPMENT_ENVIRONMENT_FIRST_ARG%" NEQ "" (
    if "%_DEVELOPMENT_ENVIRONMENT_FIRST_ARG:~,1%" NEQ "-" (
        if "%_DEVELOPMENT_ENVIRONMENT_FIRST_ARG:~,1%" NEQ "/" (
            @echo.
            @echo [31m[1mERROR:[0m This repository is not configurable, but a configuration name was provided.
            @echo [31m[1mERROR:[0m
            @echo [31m[1mERROR:[0m     [%_DEVELOPMENT_ENVIRONMENT_FIRST_ARG%]
            @echo [31m[1mERROR:[0m

            goto ErrorExit
        )
    )
)

set _DEVELOPMENT_ENVIRONMENT_CLA=None %*

:AfterClaArgsSet

REM Create a temporary file that contains output produced by the python script. This lets us quickly bootstrap
REM to the python environment while still executing OS-specific commands.
call :CreateTempScriptName

@REM ----------------------------------------------------------------------
@REM |  Generate...
echo.

python.exe -m RepositoryBootstrap.Impl.Activate Activate "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%" "%CD%" %_DEVELOPMENT_ENVIRONMENT_CLA%
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_GENERATION_ERROR_LEVEL=%ERRORLEVEL%

@REM ----------------------------------------------------------------------
@REM |  Invoke...
if exist "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%" (
    call "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%"
)
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_EXECUTION_ERROR_LEVEL=%ERRORLEVEL%

@REM ----------------------------------------------------------------------
@REM |  Process Errors...
if "%_DEVELOPMENT_ENVIRONMENT_SCRIPT_GENERATION_ERROR_LEVEL%" NEQ "0" (
    @echo.
    @echo [31m[1mERROR:[0m Errors were encountered and the environment has not been successfully activated for development.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [%DEVELOPMENT_ENVIRONMENT_FOUNDATION%\RepositoryBootstrap\Impl\Activate.py failed]
    @echo [31m[1mERROR:[0m

    goto ErrorExit
)

if "%_DEVELOPMENT_ENVIRONMENT_SCRIPT_EXECUTION_ERROR_LEVEL%" NEQ "0" (
    @echo.
    @echo [31m[1mERROR:[0m Errors were encountered and the environment has not been successfully activated for development.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME% failed]
    @echo [31m[1mERROR:[0m

    goto ErrorExit
)

REM Cleanup
del "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%"

@echo.
python.exe -m RepositoryBootstrap.Impl.PanelPrint "The environment has been activated for the repository and this terminal is ready for development." "bold green"
@echo.
@echo.

set _DEVELOPMENT_ENVIRONMENT_ACTIVATE_ERROR=0
goto Exit

@REM ----------------------------------------------------------------------
:ErrorExit
set _DEVELOPMENT_ENVIRONMENT_ACTIVATE_ERROR=-1
set PATH=%DEVELOPMENT_ENVIRONMENT_ORIGINAL_PATH%

goto Exit

@REM ----------------------------------------------------------------------
:Exit

set DEVELOPMENT_ENVIRONMENT_FOUNDATION=%_DEVELOPMENT_ENVIRONMENT_PREVIOUS_FOUNDATION%
set DEVELOPMENT_ENVIRONMENT_ORIGINAL_PATH=

set _DEVELOPMENT_ENVIRONMENT_SCRIPT_EXECUTION_ERROR_LEVEL=
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_GENERATION_ERROR_LEVEL=
set _DEVELOPMENT_ENVIRONMENT_CLA=
set _DEVELOPMENT_ENVIRONMENT_IS_CONFIGURABLE_REPOSITORY=
set _DEVELOPMENT_ENVIRONMENT_IS_MIXIN_REPOSITORY=
set _DEVELOPMENT_ENVIRONMENT_FIRST_ARG=
set _DEVELOPMENT_ENVIRONMENT_PREVIOUS_FOUNDATION=
set _DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME=

set PYTHONPATH=%_DEVELOPMENT_ENVIRONMENT_PYTHONPATH%
set _DEVELOPMENT_ENVIRONMENT_PYTHONPATH=

exit /B %_DEVELOPMENT_ENVIRONMENT_ACTIVATE_ERROR%

@REM ---------------------------------------------------------------------------
:CreateTempScriptName
setlocal EnableDelayedExpansion
set _filename=%CD%\Activate-!RANDOM!-!Time:~6,5!.cmd
endlocal & set _DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME=%_filename%

if exist "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%" goto CreateTempScriptName
goto :EOF
