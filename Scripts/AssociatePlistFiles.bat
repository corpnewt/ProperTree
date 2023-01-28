<!-- : Begin batch script

@echo off
setlocal enableDelayedExpansion

:checkPrivileges
net file 1>nul 2>nul
if "%errorlevel%" == "0" ( goto gotPrivileges ) else ( goto getPrivileges )

:getPrivileges
cscript //nologo "%~f0?.wsf" //job:ADMIN "--self" %*
exit /b

:gotPrivileges
cls
REM See if we have a custom script passed
set "target=ProperTree.bat"
set "name=ProperTree"
if NOT "%~1" == "" (
    set "target=%~nx1"
    set "name=%~n1"
)
REM Get one directory up
pushd %~dp0
cd ..\
REM Ensure the target exists
if NOT EXIST "%target%" (
    echo Could not find %target%.
    echo Please make sure to run this script from ProperTree's Scripts Folder.
    echo.
    echo Press [enter] to quit.
    pause > nul
    exit /b
)
set "path=%cd%"
set "regpath=%ComSpec:cmd.exe=%reg.exe"
popd
echo Checking if %target% exists in registry...
"!regpath!" query "HKCR\Applications\%target%" > nul 2>&1
if "%errorlevel%"=="0" (
    echo  - Already exists.  Removing...
    echo.
    "!regpath!" delete "HKCR\Applications\%target%" /f 2> nul
    "!regpath!" delete "HKCR\.plist_auto_file" /f 2> nul
    "!regpath!" delete "HKCR\.plist" /f 2> nul
    "!regpath!" delete "HKCU\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts" /v "Applications\%target%_.plist" /f 2> nul
)
set arg=\"%path%\%target%\" \"%%1\"
echo.
echo Adding registry values...
echo.
"!regpath!" add "HKCR\Applications\%target%\shell\Open" /t REG_SZ /d "Open with %name%" /f
"!regpath!" add "HKCR\Applications\%target%\shell\Open\command" /t REG_SZ /d "%arg%" /f
"!regpath!" add "HKCR\.plist" /t REG_SZ /d ".plist_auto_file" /f
"!regpath!" add "HKCR\.plist_auto_file\shell\Open" /t REG_SZ /d "Open with %name%" /f
"!regpath!" add "HKCR\.plist_auto_file\shell\Open\command" /t REG_SZ /d "%arg%" /f
"!regpath!" add "HKCU\Software\Microsoft\Windows\CurrentVersion\ApplicationAssociationToasts" /v "Applications\%target%_.plist" /t REG_DWORD /d 0 /f
echo.
echo Press [enter] to exit...
pause > nul
exit /b

----- Begin wsf script --->

<package>
    <job id="ADMIN">
        <script language="VBScript">
            dim self_path: self_path = WScript.ScriptFullName
            If StrComp(Right(self_path,5),"?.wsf",vbTextCompare)=0 Then: self_path = Left(self_path,Len(self_path)-5): End If
            Set argument_list = CreateObject("System.Collections.ArrayList")
            For Each argument_item in WScript.Arguments
                If StrComp(argument_item,"--self",vbTextCompare)=0 Then: argument_item = self_path: End If
                Call argument_list.Add(argument_item)
            Next
            If argument_list.Count=0 Then: Call argument_list.Add(self_path): End If
            dim target_exe: target_exe = "cmd.exe"
            If StrComp(Right(argument_list(0),4),".exe",vbTextCompare)=0 Then
                target_exe = argument_list(0)
                Call argument_list.RemoveAt(0)
            ElseIf StrComp(Right(argument_list(0),4),".bat",vbTextCompare)=0 or StrComp(Right(argument_list(0),4),".cmd",vbTextCompare)=0 Then
                Call argument_list.Insert(0,"/c")
            End If
            dim args: args = ""
            For Each a in argument_list
                if args<>"" Then: args = args & " ": End If
                args = args & chr(34) & a & chr(34)
            Next
            CreateObject("Shell.Application").ShellExecute target_exe, args, , "runas", 5
        </script>
    </job>
</package>