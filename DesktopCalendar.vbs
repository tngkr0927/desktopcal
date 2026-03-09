Set FSO = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

' Install dependencies and launch using conda environment
WshShell.Run "cmd /c conda activate base && pip install -r requirements.txt --quiet 2>nul && python main.py", 0, False
