@echo off
set "args=%*"
set "script_name=%~n0"
setlocal enableDelayedExpansion
REM Check if we have "Quiet" at the end of our name
if /i not "!script_name:~-5!" == "quiet" (
    echo This script is intended to be a quiet version of the target
    echo script, however its name does not end in "quiet" so the target
    echo script cannot be located.
    echo.
    echo Press [enter] to quit.
    endlocal
    pause > nul
    exit /b
)
set "target_name=!script_name:~0,-5!.bat"
set "target_script=%~dp0!target_name!"
if not exist "%~dp0!target_name!" (
    echo Could not find !target_name!.
    echo Please make sure to run this script from the same directory
    echo as !target_name!.
    echo.
    echo Press [enter] to quit.
    endlocal
    pause > nul
    exit /b
)

call :launchScript "!target_script!" "args"
endlocal
exit /b

:launchScript <script_path> <args_name>
setlocal enableDelayedExpansion
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
powershell -c "& {$a=@();foreach($x in $args){foreach($y in (Invoke-Expression('Write-Output -- '+$x-replace'\$',\"`0\"))-replace\"`0\",'$$'){$a+='\"{0}\"'-f$y}};$c=$a-join' ';$d='/c \"{0}\"'-f$c;Start-Process '%COMSPEC:'=''%' -WindowStyle hidden -ArgumentList $d}" '\"!_target!\"!_args!'
endlocal
exit /b

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
