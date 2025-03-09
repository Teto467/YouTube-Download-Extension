@echo off
chcp 65001
setlocal

rem 現在のディレクトリを取得
set "CURRENT_DIR=%~dp0"
set "TARGET_BAT=%CURRENT_DIR%start_server.bat"
set "SHORTCUT_NAME=start_server.lnk"

rem ユーザーのスタートアップフォルダのパスを取得
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

rem ショートカット作成用のVBScriptを作成
echo Creating shortcut for %TARGET_BAT%
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\CreateShortcut.vbs"
echo sLinkFile = "%STARTUP_FOLDER%\%SHORTCUT_NAME%" >> "%TEMP%\CreateShortcut.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\CreateShortcut.vbs"
echo oLink.TargetPath = "%TARGET_BAT%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.WorkingDirectory = "%CURRENT_DIR%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Save >> "%TEMP%\CreateShortcut.vbs"

rem VBScriptを実行してショートカットを作成
cscript //nologo "%TEMP%\CreateShortcut.vbs"
del "%TEMP%\CreateShortcut.vbs"

echo.
echo start_server.batのショートカットをスタートアップフォルダに作成しました。
echo 場所: %STARTUP_FOLDER%\%SHORTCUT_NAME%
echo Windows起動時に自動的に実行されるようになりました。
echo.
pause
