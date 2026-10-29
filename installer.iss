; installer.iss
; Компиляция: iscc installer.iss

#define MyAppName "DesktopPet"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "Tenrai Production"
#define MyAppExeName "DesktopPet.exe"
#define MyAppSettingsExeName "DesktopPetSettings.exe"
#define MyAppId "{{8F3A2B1C-4D5E-6F70-8A9B-C0D1E2F3A4B5}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=DesktopPet-{#MyAppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64os
; Иконка в "Установке и удалении программ"
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Основные файлы (оба exe)
Source: "dist\DesktopPet\DesktopPet.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\DesktopPet\DesktopPetSettings.exe"; DestDir: "{app}"; Flags: ignoreversion
; Общие библиотеки PyInstaller
Source: "dist\DesktopPet\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; Ресурсы (спрайты, звуки, модели, commands.toml)
Source: "dist\DesktopPet\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
; Иконка и инструкция
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "readme.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[InstallDelete]
; Очищаем старую папку assets перед установкой новой версии, чтобы не оставалось мусора
Type: filesandordirs; Name: "{app}\assets"

[Icons]
; Ярлыки для питомца
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Настройки {#MyAppName}"; Filename: "{app}\{#MyAppSettingsExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
; Запускаем питомца после установки
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
; Открываем readme
Filename: "{app}\readme.txt"; Description: "Открыть инструкцию"; Flags: shellexec nowait postinstall skipifsilent
; Открываем папку установки (по галочке)
Filename: "{app}"; Description: "Открыть папку установки"; Flags: shellexec nowait postinstall skipifsilent unchecked

[UninstallDelete]
; При удалении программы стираем папку с настройками пользователя (%APPDATA%\DesktopPet)
Type: filesandordirs; Name: "{userappdata}\{#MyAppName}"

[Code]
const
  UninstallKey =
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\' +
    '{8F3A2B1C-4D5E-6F70-8A9B-C0D1E2F3A4B5}_is1';

function GetPreviousVersion(): String;
var
  Version: String;
begin
  Version := '';
  if not RegQueryStringValue(HKLM, UninstallKey, 'DisplayVersion', Version) then
    RegQueryStringValue(HKCU, UninstallKey, 'DisplayVersion', Version);
  Result := Version;
end;

function CompareVersions(V1, V2: String): Integer;
var
  P1, P2, N1, N2: Integer;
begin
  repeat
    P1 := Pos('.', V1);
    P2 := Pos('.', V2);

    if P1 = 0 then N1 := StrToIntDef(V1, 0)
    else N1 := StrToIntDef(Copy(V1, 1, P1 - 1), 0);

    if P2 = 0 then N2 := StrToIntDef(V2, 0)
    else N2 := StrToIntDef(Copy(V2, 1, P2 - 1), 0);

    if N1 < N2 then begin Result := -1; Exit; end;
    if N1 > N2 then begin Result := 1; Exit; end;

    if (P1 = 0) and (P2 = 0) then begin Result := 0; Exit; end;

    if P1 = 0 then V1 := '0' else V1 := Copy(V1, P1 + 1, Length(V1));
    if P2 = 0 then V2 := '0' else V2 := Copy(V2, P2 + 1, Length(V2));
  until False;
end;

function InitializeSetup(): Boolean;
var
  PrevVersion: String;
  Cmp: Integer;
  Msg: String;
begin
  Result := True;
  PrevVersion := GetPreviousVersion();

  if PrevVersion = '' then
    Exit;

  Cmp := CompareVersions(PrevVersion, '{#MyAppVersion}');

  if Cmp = 0 then
  begin
    Msg := 'DesktopPet версии ' + PrevVersion + ' уже установлен.' + #13#10 +
           'Переустановить?';
    if MsgBox(Msg, mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end
  else if Cmp > 0 then
  begin
    Msg := 'Установлена более новая версия DesktopPet (' + PrevVersion + ').' + #13#10 +
           'Установить поверх неё {#MyAppVersion}?';
    if MsgBox(Msg, mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end
  else
  begin
    Msg := 'Будет выполнено обновление DesktopPet с ' + PrevVersion +
           ' до {#MyAppVersion}.' + #13#10 +
           'Продолжить?';
    if MsgBox(Msg, mbInformation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;