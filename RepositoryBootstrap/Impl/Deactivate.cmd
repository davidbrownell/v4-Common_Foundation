@REM ----------------------------------------------------------------------
@REM |
@REM |  Deactivate.cmd
@REM |
@REM |  David Brownell <db@DavidBrownell.com>
@REM |      2022-08-11 14:55:22
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

if "%DEVELOPMENT_ENVIRONMENT_FOUNDATION%"=="" (
    @echo.
    @echo [31m[1mERROR:[0m ERROR: It does not appear that this environment has been activated.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [DEVELOPMENT_ENVIRONMENT_FOUNDATION was not defined]
    @echo [31m[1mERROR:[0m

    goto ErrorExit
)

set PYTHONPATH=%DEVELOPMENT_ENVIRONMENT_FOUNDATION%

REM Create a temporary file that contains output produced by the python script. This lets us quickly bootstrap
REM to the python environment while still executing OS-specific commands.
call :CreateTempScriptName

REM Generate...
python -m RepositoryBootstrap.Impl.Deactivate "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%" %*
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_GENERATION_ERROR_LEVEL=%ERRORLEVEL%

REM Invoke...
if exist "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%" (
    call "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%"
)
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_EXECUTION_ERROR_LEVEL=%ERRORLEVEL%

REM Process errors...
if "%_DEVELOPMENT_ENVIRONMENT_SCRIPT_GENERATION_ERROR_LEVEL%" NEQ "0" (
    @echo.
    @echo [31m[1mERROR:[0m Errors were encountered and the environment has not been successfully deactivated.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [%DEVELOPMENT_ENVIRONMENT_FOUNDATION%\RepositoryBootstrap\Impl\Deactivate.py failed]
    @echo [31m[1mERROR:[0m

    goto ErrorExit
)

if "%_DEVELOPMENT_ENVIRONMENT_SCRIPT_EXECUTION_ERROR_LEVEL%" NEQ "0" (
    @echo.
    @echo [31m[1mERROR:[0m Errors were encountered and the environment has not been successfully deactivated.
    @echo [31m[1mERROR:[0m
    @echo [31m[1mERROR:[0m     [_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME% failed]
    @echo [31m[1mERROR:[0m

    goto ErrorExit
)

REM Cleanup
del "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%"

@echo.
@echo [31m[1m-------------------------------------------[0m
@echo [31m[1m^|                                         ^|[0m
@echo [31m[1m^|  The environment has been deactivated.  ^|[0m
@echo [31m[1m^|                                         ^|[0m
@echo [31m[1m-------------------------------------------[0m
@echo.
@echo.

goto Exit

@REM ----------------------------------------------------------------------
:ErrorExit
set _DEVELOPMENT_ENVIRONMENT_DEACTIVATE_ERROR=-1
goto Exit

@REM ----------------------------------------------------------------------
:Exit

set _DEVELOPMENT_ENVIRONMENT_SCRIPT_EXECUTION_ERROR_LEVEL=
set _DEVELOPMENT_ENVIRONMENT_SCRIPT_GENERATION_ERROR_LEVEL=
set _DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME=
set PYTHONPATH=

exit /B %_DEVELOPMENT_ENVIRONMENT_DEACTIVATE_ERROR%

@REM ---------------------------------------------------------------------------
:CreateTempScriptName
setlocal EnableDelayedExpansion
set _filename=%CD%\Deactivate-!RANDOM!-!Time:~6,5!.cmd
endlocal & set _DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME=%_filename%

if exist "%_DEVELOPMENT_ENVIRONMENT_TEMP_SCRIPT_NAME%" goto CreateTempScriptName
goto :EOF
