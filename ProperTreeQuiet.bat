<!-- : Begin batch script

@echo off
set "script_name=%~n0"
REM Check if we have "Quiet" at the end of our name
if /i not "%script_name:~-5%" == "quiet" (
    echo This script is intended to be a quiet version of the target
    echo script, however its name does not end in "quiet" so the target
    echo script cannot be located.
    echo.
    echo Press [enter] to quit.
    pause > nul
    exit /b
)
set "target_name=%script_name:~0,-5%.bat"
if not exist "%~dp0%target_name%" (
    echo Could not find %target_name%.
    echo Please make sure to run this script from the same directory
    echo as %target_name%.
    echo.
    echo Press [enter] to quit.
    pause > nul
    exit /b
)
cscript //nologo "%~f0?.wsf" //job:QUIET "%~dp0%target_name%" %*
exit /b

----- Begin wsf script --->

<package>
    <job id="QUIET">
        <script language="VBScript">
            dim self_path: self_path = WScript.ScriptFullName
            If StrComp(Right(self_path,5),"?.wsf",vbTextCompare)=0 Then: self_path = Left(self_path,Len(self_path)-5): End If
            Set argument_list = CreateObject("System.Collections.ArrayList")
            For Each argument_item in WScript.Arguments
                If StrComp(argument_item,"--self",vbTextCompare)=0 Then: argument_item = self_path: End If
                Call argument_list.Add(argument_item)
            Next
            If argument_list.Count=0 Then: Call argument_list.Add(self_path): End If
            For Each a in argument_list
                If args<>"" Then: args = args & " ": End If
                args = args & chr(34) & a & chr(34)
            Next            
            CreateObject("Wscript.Shell").Run args, 0, False
        </script>
    </job>
</package>