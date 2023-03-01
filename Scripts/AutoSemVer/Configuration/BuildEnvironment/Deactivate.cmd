@echo off
pushd "%~dp0"
call "C:\Code\v4\Common\Foundation\RepositoryBootstrap\Impl\Deactivate.cmd" %*
set _DEVELOPMENT_ENVIRONMENT_DEACTIVATE_ERROR=%ERRORLEVEL%
popd
if %_DEVELOPMENT_ENVIRONMENT_DEACTIVATE_ERROR% NEQ 0 (exit /B %_DEVELOPMENT_ENVIRONMENT_DEACTIVATE_ERROR%)