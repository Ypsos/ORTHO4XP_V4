; ============================================================
; Copyright (c) 2024-2026 Roland (Ypsos)
;
; CRÉDIT — AUTEUR : Roland (Ypsos) — Novembre 2026
; Module conçu et spécifié par Roland (Ypsos) pour Ortho4XP V3.
; Cette notice d'auteur et de copyright doit être conservée
; conformément à la GPLv3.
; ============================================================
; CREDIT — AUTHOR: Roland (Ypsos) — November 2026
; This authorship and copyright notice must be retained (GPLv3).
; ============================================================
; Installateur Windows d'ORTHO4XP V3 (Inno Setup 6).
; Fabriqué AUTOMATIQUEMENT par GitHub (.github/workflows/build-windows-setup.yml),
; sur le même principe que le DMG macOS : rien à faire à la main.
;
; Ce que fait l'installateur (sans droits administrateur) :
;   1. copie ORTHO4XP_V3 dans le dossier choisi (par défaut C:\ORTHO4XP_V3) ;
;      refuse « Program Files » (Ortho4XP écrit dans son propre dossier)
;      et les disques FAT32 (fichiers > 4 Go impossibles) ;
;   2. installe Python 3.12 (embarqué, pour l'utilisateur seul) s'il manque ;
;   3. lance l'installation des prérequis existante (INSTALL_PREREQUIS.py :
;      venv + modules), qui ouvre ensuite Ortho4XP ;
;   4. crée les raccourcis menu Démarrer (+ Bureau en option).
; Mise à jour : réinstaller par-dessus CONSERVE Ortho4XP.cfg,
; custom_theme.json, les tuiles, les images et toutes les données.
; Désinstallation : retire les fichiers du programme et le venv ;
; tuiles, images et données de l'utilisateur sont CONSERVÉES.
; ============================================================

#ifndef AppVersion
  #define AppVersion "3.0"
#endif
; Racine du dépôt (ce fichier est dans Utils\win\installer\)
#ifndef SrcDir
  #define SrcDir "..\..\.."
#endif
; Chemin de l'installateur Python officiel à embarquer (fourni par GitHub)
#ifndef PyInstaller
  #define PyInstaller ""
#endif
#ifndef OutDir
  #define OutDir "Output"
#endif

; Fichiers et dossiers JAMAIS copiés depuis le dépôt (git, recettes, caches,
; lanceurs macOS, sauvegardes « copie », données utilisateur éventuelles).
; Ortho4XP.cfg / custom_theme.json sont installés à part (jamais écrasés).
#define Excl "\.git,\.github,__pycache__,*.pyc,.DS_Store,\venv,\dist,\build,*copie*,*.app,\custom_theme.json,\Ortho4XP.cfg,\Ortho4XP.cfg.bak,\Ortho4XP.log,\ortho4xp_install.log,\Tiles,\Orthophotos,\OSM_data,\Masks,\Elevation_data,\Geotiffs,\Previews,\tmp,\Rapports,\Utils\win\installer\Output"

[Setup]
AppId={{8E4F3A2B-6C1D-4E5F-9A7B-0C2D3E4F5A6B}
AppName=ORTHO4XP V3
AppVersion={#AppVersion}
AppVerName=ORTHO4XP V3 ({#AppVersion})
AppPublisher=Roland (Ypsos)
AppPublisherURL=https://github.com/Ypsos/ORTHO4XP_V3
AppSupportURL=https://github.com/Ypsos/ORTHO4XP_V3
DefaultDirName={sd}\ORTHO4XP_V3
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UsePreviousAppDir=yes
DirExistsWarning=no
CloseApplications=yes
OutputDir={#OutDir}
OutputBaseFilename=ORTHO4XP_V3_Windows_Setup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
UninstallDisplayName=ORTHO4XP V3
LicenseFile={#SrcDir}\AVERTISSEMENT_LICENCE_LEGAL.MD

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
fr.DesktopIcon=Créer un raccourci sur le Bureau
en.DesktopIcon=Create a desktop shortcut
fr.InstallPython=Installer Python 3.12 (nécessaire, absent de cet ordinateur)
en.InstallPython=Install Python 3.12 (required, missing on this computer)
fr.InstallingPython=Installation de Python 3.12… (une à deux minutes)
en.InstallingPython=Installing Python 3.12… (one to two minutes)
fr.RunPrereq=Terminer l'installation (modules Python) et ouvrir Ortho4XP
en.RunPrereq=Finish the installation (Python modules) and open Ortho4XP
fr.Repair=ORTHO4XP V3 - Réparer les prérequis
en.Repair=ORTHO4XP V3 - Repair prerequisites
fr.NoProgramFiles=Ortho4XP écrit ses tuiles et ses images dans son propre dossier : il ne peut pas être installé dans « Program Files ».%n%nChoisissez par exemple C:\ORTHO4XP_V3 ou un dossier sur un autre disque.
en.NoProgramFiles=Ortho4XP writes its tiles and images in its own folder: it cannot be installed in "Program Files".%n%nChoose for example C:\ORTHO4XP_V3 or a folder on another disk.
fr.NoFat=Ce disque est au format FAT32 : il refuse les fichiers de plus de 4 Go, la construction des tuiles échouerait.%n%nChoisissez un disque au format NTFS.
en.NoFat=This disk is FAT32: it refuses files over 4 GB, tile building would fail.%n%nChoose an NTFS disk.
fr.ExFat=Ce disque est au format exFAT : Ortho4XP fonctionnera, mais plus lentement qu'avec un disque NTFS.%n%nContinuer quand même ?
en.ExFat=This disk is exFAT: Ortho4XP will work, but more slowly than on an NTFS disk.%n%nContinue anyway?
fr.Update=Une installation d'ORTHO4XP V3 existe déjà dans ce dossier.%n%nElle sera mise à jour : vos réglages (Ortho4XP.cfg), vos tuiles, vos images et vos données sont conservés.
en.Update=An ORTHO4XP V3 installation already exists in this folder.%n%nIt will be updated: your settings (Ortho4XP.cfg), tiles, images and data are kept.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"
#if PyInstaller != ""
Name: "installpython"; Description: "{cm:InstallPython}"; Check: NeedPython
#endif

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Excludes: "{#Excl}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Réglage personnel du thème : installé seulement s'il n'existe pas (mise à jour sans perte)
Source: "{#SrcDir}\custom_theme.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
; Démarrage sans fenêtre noire (raccourcis)
Source: "Demarrer_ORTHO4XP_V3.vbs"; DestDir: "{app}"; Flags: ignoreversion
#if PyInstaller != ""
Source: "{#PyInstaller}"; DestDir: "{tmp}"; DestName: "python_setup.exe"; Flags: deleteafterinstall; Tasks: installpython
#endif

[Icons]
Name: "{autoprograms}\ORTHO4XP V3"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\Demarrer_ORTHO4XP_V3.vbs"""; WorkingDir: "{app}"
Name: "{autoprograms}\{cm:Repair}"; Filename: "{app}\LANCEUR_INSTALL_WINDOWS.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\ORTHO4XP V3"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\Demarrer_ORTHO4XP_V3.vbs"""; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
#if PyInstaller != ""
Filename: "{tmp}\python_setup.exe"; Parameters: "/quiet InstallAllUsers=0 InstallLauncherAllUsers=0 PrependPath=1 Include_tcltk=1 Include_pip=1 Include_launcher=1 Include_test=0 Include_doc=0 Shortcuts=0"; StatusMsg: "{cm:InstallingPython}"; Tasks: installpython; Flags: waituntilterminated
#endif
; Python connu (registre) : lancement direct de l'installation des prérequis
Filename: "{code:PythonExe}"; Parameters: """{app}\INSTALL_PREREQUIS.py"""; WorkingDir: "{app}"; Description: "{cm:RunPrereq}"; Flags: postinstall nowait skipifsilent; Check: HavePython
; Sinon : le lanceur existant (il guide l'utilisateur si Python manque)
Filename: "{app}\LANCEUR_INSTALL_WINDOWS.bat"; WorkingDir: "{app}"; Description: "{cm:RunPrereq}"; Flags: postinstall nowait skipifsilent shellexec; Check: not HavePython

[UninstallDelete]
; Seulement ce que l'installation a fabriqué ; les données de l'utilisateur restent
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\src\__pycache__"
Type: files; Name: "{app}\Lanceur ORTHO4XP.vbs"

[Code]
function GetVolumeInformation(lpRootPathName: String; lpVolumeNameBuffer: String;
  nVolumeNameSize: DWORD; var lpVolumeSerialNumber: DWORD;
  var lpMaximumComponentLength: DWORD; var lpFileSystemFlags: DWORD;
  lpFileSystemNameBuffer: String; nFileSystemNameSize: DWORD): Integer;
  external 'GetVolumeInformationW@kernel32.dll stdcall';

{ Chemin de python.exe 3.12 (sinon 3.11) d'après le registre officiel PEP 514 }
function FindPython(): String;
var
  Versions: array[0..1] of String;
  Roots: array[0..2] of Integer;
  I, J: Integer;
  P: String;
begin
  Result := '';
  Versions[0] := '3.12';
  Versions[1] := '3.11';
  Roots[0] := HKCU;
  Roots[1] := HKLM64;
  Roots[2] := HKLM32;
  for I := 0 to 1 do
    for J := 0 to 2 do
    begin
      P := '';
      if RegQueryStringValue(Roots[J], 'Software\Python\PythonCore\' + Versions[I] + '\InstallPath', '', P) then
      begin
        P := AddBackslash(P) + 'python.exe';
        if FileExists(P) then
        begin
          Result := P;
          Exit;
        end;
      end;
    end;
end;

function NeedPython(): Boolean;
begin
  Result := (FindPython() = '');
end;

function HavePython(): Boolean;
begin
  Result := (FindPython() <> '');
end;

{ pythonw.exe (sans fenêtre noire) s'il existe à côté de python.exe }
function PythonExe(Param: String): String;
var
  W: String;
begin
  Result := FindPython();
  if Result <> '' then
  begin
    W := ExtractFilePath(Result) + 'pythonw.exe';
    if FileExists(W) then
      Result := W;
  end;
end;

function FileSystemOf(Dir: String): String;
var
  Root, VolName, FsName: String;
  Serial, MaxLen, Flags: DWORD;
begin
  Result := '';
  Root := AddBackslash(ExtractFileDrive(Dir));
  if Root = '\' then Exit;
  SetLength(VolName, 261);
  SetLength(FsName, 261);
  if GetVolumeInformation(Root, VolName, 261, Serial, MaxLen, Flags, FsName, 261) <> 0 then
  begin
    if Pos(#0, FsName) > 0 then
      FsName := Copy(FsName, 1, Pos(#0, FsName) - 1);
    Result := Uppercase(Trim(FsName));
  end;
end;

function StartsWithDir(Path, Base: String): Boolean;
begin
  Base := AddBackslash(Lowercase(Base));
  Path := AddBackslash(Lowercase(Path));
  Result := (Base <> '\') and (Copy(Path, 1, Length(Base)) = Base);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Dir, Fs: String;
begin
  Result := True;
  if CurPageID <> wpSelectDir then Exit;
  Dir := WizardDirValue();
  { 1) jamais dans Program Files (Ortho4XP écrit dans son dossier) }
  if StartsWithDir(Dir, ExpandConstant('{commonpf64}')) or
     StartsWithDir(Dir, ExpandConstant('{commonpf32}')) then
  begin
    SuppressibleMsgBox(CustomMessage('NoProgramFiles'), mbError, MB_OK, IDOK);
    Result := False;
    Exit;
  end;
  { 2) format du disque }
  Fs := FileSystemOf(Dir);
  if (Fs = 'FAT32') or (Fs = 'FAT') then
  begin
    SuppressibleMsgBox(CustomMessage('NoFat'), mbError, MB_OK, IDOK);
    Result := False;
    Exit;
  end;
  if Fs = 'EXFAT' then
  begin
    if SuppressibleMsgBox(CustomMessage('ExFat'), mbConfirmation, MB_YESNO, IDYES) <> IDYES then
    begin
      Result := False;
      Exit;
    end;
  end;
  { 3) mise à jour d'une installation existante : on rassure }
  if FileExists(AddBackslash(Dir) + 'Ortho4XP.py') then
    SuppressibleMsgBox(CustomMessage('Update'), mbInformation, MB_OK, IDOK);
end;
