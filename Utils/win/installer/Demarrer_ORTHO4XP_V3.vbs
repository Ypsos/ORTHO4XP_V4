' ============================================================
' Copyright (c) 2024-2026 Roland (Ypsos) - GPLv3
' CREDIT - AUTEUR / AUTHOR : Roland (Ypsos) - Novembre 2026
' Cette notice doit etre conservee / This notice must be retained.
' ============================================================
' Demarrer ORTHO4XP V3 (raccourci du menu Demarrer et du Bureau).
'  - Prerequis deja installes (venv present) : lance Ortho4XP sans
'    fenetre noire.
'  - Sinon (premiere fois, ou reparation) : lance l'installation des
'    prerequis (LANCEUR_INSTALL_WINDOWS.bat), qui ouvre Ortho4XP a la fin.
' Start ORTHO4XP V3. Without prerequisites, runs their installation first.
' ============================================================
Option Explicit
Dim ws, fso, d, py, la, bat
Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
d = fso.GetParentFolderName(WScript.ScriptFullName)
py = d & "\venv\Scripts\pythonw.exe"
la = d & "\Ortho4XP_Launcher.py"
bat = d & "\LANCEUR_INSTALL_WINDOWS.bat"
ws.CurrentDirectory = d
If fso.FileExists(py) And fso.FileExists(la) Then
  ws.Run Chr(34) & py & Chr(34) & " " & Chr(34) & la & Chr(34), 1, False
ElseIf fso.FileExists(bat) Then
  ws.Run Chr(34) & bat & Chr(34), 1, False
Else
  MsgBox "ORTHO4XP V3 : installation incomplete. Reinstallez avec ORTHO4XP_V3_Windows_Setup.exe" & vbCrLf & _
         "ORTHO4XP V3: incomplete installation. Reinstall with ORTHO4XP_V3_Windows_Setup.exe", 48, "ORTHO4XP V3"
End If
