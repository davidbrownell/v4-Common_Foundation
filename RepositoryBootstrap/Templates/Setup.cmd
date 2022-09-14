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
@REM |          --verbose                        : Verbose output.
@REM |          --debug                          : Includes debug output (in adddition to verbose output).
@REM |
@REM |          --name <unique_environment_name> : Setup an environment with a unique name. This allows for the
@REM |                                             creation of side-by-side environments that are otherwise identical.
@REM |                                             It is very rare to setup an environment with a unique name.
@REM |
@REM ----------------------------------------------------------------------

if "%DEVELOPMENT_ENVIRONMENT_FOUNDATION%"=="" (
    @echo.
    @echo [31m[1mERROR:[0m Please run this script within an activated environment.
    @echo [31m[1mERROR:[0m
    @echo.

    goto end
)

pushd "%~dp0"
call "%DEVELOPMENT_ENVIRONMENT_FOUNDATION%\RepositoryBootstrap\Impl\Setup.cmd" %*
set _DEVELOPMENT_ENVIRONMENT_SETUP_ERROR=%ERRORLEVEL%
popd

if %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR% NEQ 0 (exit /B %_DEVELOPMENT_ENVIRONMENT_SETUP_ERROR%)

:end
