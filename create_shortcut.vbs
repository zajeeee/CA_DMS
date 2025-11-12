Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = oWS.SpecialFolders("Desktop") & "\CA_DMS.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)

' Get the current directory
Set fso = CreateObject("Scripting.FileSystemObject")
sCurrentDir = fso.GetAbsolutePathName(".")

' Set shortcut properties
oLink.TargetPath = sCurrentDir & "\CA_DMS.bat"
oLink.WorkingDirectory = sCurrentDir
oLink.Description = "Document Management System - CA_DMS"
oLink.IconLocation = sCurrentDir & "\static\roxas_logo.ico"
oLink.WindowStyle = 1

' Save the shortcut
oLink.Save

WScript.Echo "Shortcut created successfully on Desktop!"
WScript.Echo "Icon: " & oLink.IconLocation

