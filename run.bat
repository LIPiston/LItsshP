@echo off
rem Launch LItsshP with the project virtualenv when one exists.
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo LItsshP needs a virtualenv at .venv
    echo.
    echo   py -3 -m venv .venv
    echo   .venv\Scripts\python -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

pushd "%ROOT%"
"%PYTHON%" -m app.main %*
set "CODE=%ERRORLEVEL%"
popd

if not "%CODE%"=="0" pause
exit /b %CODE%
