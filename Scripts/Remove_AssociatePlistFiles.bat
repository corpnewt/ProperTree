@echo off

:checkPrivileges
NET FILE 1>NUL 2>NUL
if '%errorlevel%' == '0' ( goto gotPrivileges ) else ( goto getPrivileges )

:getPrivileges
if '%~1'=='ELEV' (shift & goto main)
ECHO.

setlocal DisableDelayedExpansion
set "batchPath=%~0"
setlocal EnableDelayedExpansion
ECHO Set UAC = CreateObject^("Shell.Application"^) > "%temp%\OEgetPrivileges.vbs"
ECHO UAC.ShellExecute "!batchPath!", "ELEV", "", "runas", 1 >> "%temp%\OEgetPrivileges.vbs"
"%temp%\OEgetPrivileges.vbs"
exit /B

:gotPrivileges
@echo off
setlocal enableDelayedExpansion
cls
REM Get one directory up
pushd %~dp0
cd ..\
set "path=%cd%"
set "regpath=%ComSpec:cmd.exe=%reg.exe"
popd
echo Checking if ProperTree.bat exists in registry...
"!regpath!" query "HKCR\Applications\ProperTree.bat" > nul 2>&1
if "%errorlevel%"=="0" (
    echo  - Removing registry values...
    echo.
    "!regpath!" delete "HKCR\Applications\ProperTree.bat" /f 2> nul
    "!regpath!" delete "HKCR\.plist_auto_file" /f 2> nul
    "!regpath!" delete "HKCR\.plist" /f 2> nul
    "!regpath!" delete "HKCU\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts" /v "Applications\ProperTree.bat_.plist" /f 2> nul
)
echo.
echo Press [enter] to exit...
pause > nul
exit /b
