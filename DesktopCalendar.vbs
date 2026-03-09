Set FSO = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

' Install dependencies silently first
WshShell.Run "cmd /c pip install -r requirements.txt --quiet 2>nul", 0, True

' Launch the app without a console window
WshShell.Run "python main.py", 0, False
