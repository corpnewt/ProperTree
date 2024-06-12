@echo off

set "this_script=%~f0"
set "this_dir=%~dp0"
set "args=%*"
set "passed_script=%~1"
set "_script_no_ext=%~nx1"
set "_script_name=%~n1"

setlocal enableDelayedExpansion

goto getPrivileges

:getPrivileges
call :launchScript "!this_script!" "args"
if "%errorlevel%" == "0" (
    goto gotPrivileges
)
exit /b

:gotPrivileges
cls
REM See if we have a custom script passed
set "target=ProperTree.bat"
set "name=ProperTree"
if NOT "!passed_script!" == "" (
    set "target=!_script_no_ext!"
    set "name=!_script_name!"
)
REM Get one directory up
pushd "!this_dir!"
cd ..\
REM Ensure the target exists
if NOT EXIST "!target!" (
    echo Could not find !target!.
    echo Please make sure to run this script from ProperTree's Scripts Folder.
    echo.
    echo Press [enter] to quit.
    pause > nul
    exit /b
)
set "path=%cd%"
set "regpath=%ComSpec:cmd.exe=%reg.exe"
popd
echo Checking if !target! exists in registry...
"!regpath!" query "HKCR\Applications\!target!" > nul 2>&1
if "%errorlevel%"=="0" (
    echo  - Already exists.  Removing...
    echo.
    "!regpath!" delete "HKCR\Applications\!target!" /f 2> nul
    "!regpath!" delete "HKCR\.plist_auto_file" /f 2> nul
    "!regpath!" delete "HKCR\.plist" /f 2> nul
    "!regpath!" delete "HKCU\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts" /v "Applications\!target!_.plist" /f 2> nul
)
set arg=\"%path%\!target!\" \"%%1\"
set "icon=%path%\Scripts\shortcut.ico"
echo.
echo Adding registry values...
echo.
"!regpath!" add "HKCR\Applications\!target!\shell\Open" /t REG_SZ /d "Open with !name!" /f
"!regpath!" add "HKCR\Applications\!target!\shell\Open\command" /t REG_SZ /d "%arg%" /f
"!regpath!" add "HKCR\.plist" /t REG_SZ /d ".plist_auto_file" /f
"!regpath!" add "HKCR\.plist_auto_file\shell\Open" /t REG_SZ /d "Open with !name!" /f
"!regpath!" add "HKCR\.plist_auto_file\shell\Open\command" /t REG_SZ /d "%arg%" /f
"!regpath!" add "HKCR\.plist_auto_file\DefaultIcon" /t REG_SZ /d "%icon%" /f
"!regpath!" add "HKCU\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts" /v "Applications\!target!_.plist" /t REG_DWORD /d 0 /f
echo.
echo Press [enter] to exit...
pause > nul
exit /b

:launchScript <script_path> <args_name>
setlocal enableDelayedExpansion
REM Check if we have admin
net file 1>nul 2>nul
if "%errorlevel%" == "0" (
    exit /b 0
)
REM Let's check what our requirements are in order to launch, and
REM adjust as needed
set "_target=%~1"
set "_args=!%~2!"
REM Let's sanitize our args a bit
if not "!_args!" == "" (
    call :cleanArg "_args" "true"
)
REM And our target
call :cleanArg "_target"
REM Let's build our command
powershell -c "& {$a=@();foreach($x in $args){foreach($y in (Invoke-Expression('Write-Output -- '+$x-replace'\$',\"`0\"))-replace\"`0\",'$$'){$a+='\"{0}\"'-f$y}};$c=$a-join' ';$d='/c \"{0}\"'-f$c;Start-Process '%COMSPEC:'=''%' -Verb RunAs -ArgumentList $d}" '\"!_target!\"!_args!'
endlocal
exit /b 1

:cleanArg <argname> <prepend_space>
REM Escape some problematic chars for powershell
set "%~1=!%~1:`=``!"
set "%~1=!%~1:'=`''!"
set "%~1=!%~1:"=\"!"
set "%~1=!%~1:(=`(!"
set "%~1=!%~1:)=`)!"
set "%~1=!%~1:{=`{!"
set "%~1=!%~1:}=`}!"
set "%~1=!%~1:$=`0!"
set "%~1=!%~1:;=`;!"
if "%~2" == "" (
    set "%~1=!%~1!"
) else (
    set "%~1= !%~1!"
)
exit /b
