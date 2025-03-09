chcp 65001
@echo off
title YouTube動画ダウンローダー セットアップ
echo ===================================================
echo  YouTube動画ダウンローダー セットアップウィザード
echo ===================================================
echo.

REM Pythonがインストールされているか確認
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [エラー] Pythonが見つかりません。
    echo Pythonをインストールしてから再度実行してください。
    echo https://www.python.org/downloads/ からPython 3.8以上をインストールしてください。
    echo.
    pause
    exit /b 1
)

echo [情報] Pythonが見つかりました。セットアップを続行します...
echo.

REM セットアップフォルダの作成
set INSTALL_DIR=%LOCALAPPDATA%\YouTubeDownloader
if not exist "%INSTALL_DIR%" (
    echo [情報] インストールディレクトリを作成しています...
    mkdir "%INSTALL_DIR%"
)

REM 拡張機能用のディレクトリ作成
set EXTENSION_DIR=%INSTALL_DIR%\extension
if not exist "%EXTENSION_DIR%" (
    mkdir "%EXTENSION_DIR%"
)

REM yt-dlp.exeのコピー
echo [情報] yt-dlp.exeをコピーしています...
copy "%~dp0yt-dlp.exe" "%INSTALL_DIR%\yt-dlp.exe" > nul
if %errorlevel% neq 0 (
    echo [エラー] yt-dlp.exeのコピーに失敗しました。
    pause
    exit /b 1
)

REM インストーラースクリプトの実行
echo [情報] 必要なPythonパッケージをインストールしています...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

REM installer.pyをコピーして実行
copy "%~dp0installer.py" "%INSTALL_DIR%\installer.py" > nul
python "%INSTALL_DIR%\installer.py" "%INSTALL_DIR%"

REM 拡張機能ファイルのコピー
echo [情報] 拡張機能ファイルをコピーしています...
copy "%~dp0manifest.json" "%EXTENSION_DIR%\" > nul
copy "%~dp0background.js" "%EXTENSION_DIR%\" > nul
copy "%~dp0content.js" "%EXTENSION_DIR%\" > nul
copy "%~dp0popup.html" "%EXTENSION_DIR%\" > nul
copy "%~dp0popup.js" "%EXTENSION_DIR%\" > nul
copy "%~dp0styles.css" "%EXTENSION_DIR%\" > nul

REM サーバー起動スクリプトの作成
echo [情報] サーバー起動スクリプトを作成しています...
echo @echo off > "%INSTALL_DIR%\start_server.bat"
echo title YouTube動画ダウンローダー サーバー >> "%INSTALL_DIR%\start_server.bat"
echo chcp 65001 >> "%INSTALL_DIR%\start_server.bat"
echo echo サーバーを起動しています... >> "%INSTALL_DIR%\start_server.bat"
echo cd /d "%INSTALL_DIR%" >> "%INSTALL_DIR%\start_server.bat"
echo python server.py >> "%INSTALL_DIR%\start_server.bat"
echo pause >> "%INSTALL_DIR%\start_server.bat"

REM Chrome拡張機能のインストール手順
echo.
echo ===================================================
echo  セットアップ完了！
echo ===================================================
echo.
echo 1. Chromeを開き、chrome://extensions/ にアクセスしてください
echo 2. 「デベロッパーモード」を有効にしてください
echo 3. 「パッケージ化されていない拡張機能を読み込む」をクリックして、
echo    次のフォルダを選択してください：
echo    %EXTENSION_DIR%
echo.
echo 4. サーバーを起動するには、以下のパスのstart_server.batを実行してください：
echo    %INSTALL_DIR%\start_server.bat
echo.
echo ※注意: 拡張機能を使用する前に必ずサーバーを起動してください
echo.
pause
exit /b 0
