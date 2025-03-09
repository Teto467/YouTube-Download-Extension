@echo off
chcp 65001
setlocal

rem ショートカットの名前を定義
set "SHORTCUT_NAME=start_server.lnk"

rem ユーザーのスタートアップフォルダのパスを取得
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

rem ショートカットの完全パス
set "SHORTCUT_PATH=%STARTUP_FOLDER%\%SHORTCUT_NAME%"

echo スタートアップからの登録解除を試みています...
echo.

rem ショートカットが存在するか確認
if exist "%SHORTCUT_PATH%" (
    rem ショートカットを削除
    del "%SHORTCUT_PATH%"
    
    rem 削除後に再度確認して結果を表示
    if exist "%SHORTCUT_PATH%" (
        echo 削除に失敗しました。手動で以下のファイルを削除してください：
        echo %SHORTCUT_PATH%
    ) else (
        echo start_server.batのスタートアップ登録を解除しました。
        echo Windows起動時に自動実行されなくなりました。
    )
) else (
    echo スタートアップに登録されていません。削除するものはありません。
)

echo.
pause
