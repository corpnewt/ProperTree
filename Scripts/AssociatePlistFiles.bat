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
popd
echo Checking if ProperTree.bat exists in registry...
reg query "HKCR\Applications\ProperTree.bat" > nul 2>&1
if not "%errorlevel%"=="0" (
    echo  - Already exists.  Removing...
    reg delete "HKCR\Applications\ProperTree.bat" /f nul 2>&1
    reg delete "HKCR\.plist_auto_file" /f nul 2>&1
    reg delete "HKCR\.plist" /f nul 2>&1
    reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts" /v "Applications\ProperTree.bat_.plist" /f nul 2>&1
)
set arg=\"%path%\ProperTree.bat\" \"%%1\"
echo Adding registry values...
echo.
reg add "HKCR\Applications\ProperTree.bat\shell\Open" /t REG_SZ /d "Open with ProperTree" /f
reg add "HKCR\Applications\ProperTree.bat\shell\Open\command" /t REG_SZ /d "%arg%" /f
reg add "HKCR\.plist" /t REG_SZ /d ".plist_auto_file" /f
reg add "HKCR\.plist_auto_file\shell\Open" /t REG_SZ /d "Open with ProperTree" /f
reg add "HKCR\.plist_auto_file\shell\Open\command" /t REG_SZ /d "%arg%" /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts" /v "Applications\ProperTree.bat_.plist" /t REG_DWORD /d 0 /f
echo.
echo Press [enter] to exit...
pause > nul
exit /b