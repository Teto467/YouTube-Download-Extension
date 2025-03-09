import os
import sys
import shutil
import json
import winreg
from pathlib import Path
import logging

def setup_logging():
    """ロギングの設定"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('install.log', encoding='utf-8')
        ]
    )

def create_directories(install_dir):
    """必要なディレクトリを作成"""
    dirs = [
        'logs',
        'config'
    ]
    for dir_name in dirs:
        path = os.path.join(install_dir, dir_name)
        if not os.path.exists(path):
            os.makedirs(path)
            logging.info(f'ディレクトリを作成しました: {path}')

def create_config(install_dir):
    """設定ファイルの作成"""
    config = {
        'log_dir': os.path.join(install_dir, 'logs'),
        'server_port': 8745
    }
    
    config_path = os.path.join(install_dir, 'config', 'config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    logging.info(f'設定ファイルを作成しました: {config_path}')

def register_native_host(install_dir):
    """ネイティブメッセージングホストの登録"""
    try:
        manifest = {
            "name": "com.youtube.downloader",
            "description": "YouTube動画ダウンローダー",
            "path": os.path.join(install_dir, "server.py"),
            "type": "stdio",
            "allowed_origins": [
                "chrome-extension://*/"
            ]
        }
        
        manifest_path = os.path.join(install_dir, "native_host.json")
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=4, ensure_ascii=False)
        
        key_path = r"Software\Google\Chrome\NativeMessagingHosts\com.youtube.downloader"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, manifest_path)
        
        logging.info('ネイティブメッセージングホストを登録しました')
    except Exception as e:
        logging.error(f'ネイティブメッセージングホストの登録に失敗しました: {e}')
        raise

def create_startup_shortcut(install_dir):
    """スタートアップにショートカットを作成"""
    try:
        import win32com.client
        
        startup_path = os.path.join(
            os.getenv('APPDATA'),
            r'Microsoft\Windows\Start Menu\Programs\Startup',
            'YouTube動画ダウンローダーサーバー.lnk'
        )
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(startup_path)
        shortcut.Targetpath = os.path.join(install_dir, "start_server.bat")
        shortcut.WorkingDirectory = install_dir
        shortcut.save()
        
        logging.info('スタートアップショートカットを作成しました')
    except Exception as e:
        logging.info('スタートアップショートカットの作成をスキップしました（オプション）')

def main():
    """メインのインストール処理"""
    if len(sys.argv) < 2:
        print("インストールディレクトリを指定してください")
        sys.exit(1)
    
    install_dir = sys.argv[1]
    setup_logging()
    
    try:
        logging.info('インストールを開始します...')
        create_directories(install_dir)
        create_config(install_dir)
        register_native_host(install_dir)
        create_startup_shortcut(install_dir)
        logging.info('インストールが完了しました')
    
    except Exception as e:
        logging.error(f'インストール中にエラーが発生しました: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()