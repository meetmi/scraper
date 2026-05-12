Set WinScriptHost = CreateObject("WScript.Shell")
' Replace the first path with your Python.exe and the second with your script.py
WinScriptHost.Run "C:\Users\DELL\Documents\Scraper", 0
Set WinScriptHost = Nothing