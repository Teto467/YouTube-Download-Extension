import os
import subprocess
import logging
import sys
import json
import platform
import shutil
import re
import io
import codecs
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import threading
import time
import atexit

# コンソール出力のエンコーディングを設定
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server.log", encoding='utf-8'),
        logging.StreamHandler(stream=sys.stdout)  # 明示的にstdoutを使用
    ]
)
logger = logging.getLogger(__name__)

# アプリケーション初期化
app = Flask(__name__)
CORS(app)  # CORS対応

# グローバル設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
YTDLP_PATH = os.path.join(BASE_DIR, 'yt-dlp')
if platform.system() == 'Windows':
    YTDLP_PATH += '.exe'

# デフォルト設定 - ユーザーディレクトリに直接保存するよう変更
DEFAULT_CONFIG = {
    "download_path": os.path.expanduser("~"),  # ユーザーディレクトリに変更
    "default_resolution": "best",
    "default_format": "mp4",
    "auto_update": True,
    "last_update_check": None
}

# ファイル名のサニタイズ関数
def sanitize_filename(filename):
    """ファイル名から不正な文字を除去する"""
    # Windows禁止文字を削除
    sanitized = re.sub(r'[\\/*?:"<>|]', '', filename)
    # 連続する空白を1つに置換
    sanitized = re.sub(r'\s+', ' ', sanitized)
    # 前後の空白を削除
    return sanitized.strip()

# 設定の読み込み
def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # デフォルト設定にある項目で、読み込んだ設定にないものはデフォルト値を使用
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            # 設定ファイルがない場合はデフォルト設定を保存して返す
            save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
    except Exception as e:
        logger.error(f"設定ファイルの読み込み中にエラーが発生しました: {e}")
        return DEFAULT_CONFIG.copy()

# 設定の保存
def save_config(config):
    try:
        # 保存前にダウンロードパスの存在確認と作成
        download_path = config.get('download_path', DEFAULT_CONFIG['download_path'])
        if not os.path.exists(download_path):
            os.makedirs(download_path, exist_ok=True)
            logger.info(f"ダウンロードパスを作成しました: {download_path}")
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"設定ファイルの保存中にエラーが発生しました: {e}")
        return False

# FFmpegが利用可能かチェックし、必要に応じてインストール
def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        if result.returncode == 0:
            logger.info("FFmpegが利用可能です")
            return True
    except:
        logger.warning("FFmpegが見つかりません。自動インストールを試みます...")
        
    try:
        # Windows用FFmpegのダウンロードと設置
        if platform.system() == 'Windows':
            import urllib.request
            import zipfile
            
            ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            zip_path = os.path.join(os.path.dirname(__file__), "ffmpeg.zip")
            extract_path = os.path.join(os.path.dirname(__file__), "ffmpeg")
            
            logger.info("FFmpegをダウンロード中...")
            urllib.request.urlretrieve(ffmpeg_url, zip_path)
            
            logger.info("FFmpegを展開中...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            # PATHに追加
            ffmpeg_bin = os.path.join(extract_path, "ffmpeg-master-latest-win64-gpl", "bin")
            os.environ["PATH"] += os.pathsep + ffmpeg_bin
            
            # クリーンアップ
            os.remove(zip_path)
            
            logger.info("FFmpegのインストールが完了しました")
            return True
        else:
            logger.error("自動インストールはWindowsのみサポートしています")
            return False
    except Exception as e:
        logger.error(f"FFmpegのインストールに失敗しました: {e}")
        return False

# aria2cが利用可能かチェックし、必要に応じてインストール
def check_aria2c():
    try:
        result = subprocess.run(['aria2c', '--version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        if result.returncode == 0:
            logger.info("aria2cが利用可能です")
            return True
    except:
        logger.warning("aria2cが見つかりません。自動インストールを試みます...")
        
    try:
        # Windows用aria2cのダウンロードと設置
        if platform.system() == 'Windows':
            import urllib.request
            import zipfile
            
            aria2c_url = "https://github.com/aria2/aria2/releases/download/release-1.36.0/aria2-1.36.0-win-64bit-build1.zip"
            zip_path = os.path.join(os.path.dirname(__file__), "aria2c.zip")
            extract_path = os.path.join(os.path.dirname(__file__), "aria2c")
            
            logger.info("aria2cをダウンロード中...")
            urllib.request.urlretrieve(aria2c_url, zip_path)
            
            logger.info("aria2cを展開中...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            # PATHに追加
            aria2c_bin = os.path.join(extract_path, "aria2-1.36.0-win-64bit-build1")
            os.environ["PATH"] += os.pathsep + aria2c_bin
            
            # クリーンアップ
            os.remove(zip_path)
            
            logger.info("aria2cのインストールが完了しました")
            return True
        else:
            logger.error("自動インストールはWindowsのみサポートしています")
            return False
    except Exception as e:
        logger.error(f"aria2cのインストールに失敗しました: {e}")
        return False

# yt-dlpの更新チェック
def check_and_update_ytdlp():
    config = load_config()
    
    # 前回の更新確認から1日以上経過している場合、または強制更新の場合のみ更新を実行
    last_check = config.get('last_update_check', None)
    current_time = datetime.now().timestamp()
    
    if last_check is None or (current_time - last_check) > 86400:  # 86400秒 = 1日
        try:
            logger.info("yt-dlpの更新をチェックしています...")
            update_result = subprocess.run(
                [YTDLP_PATH, '-U'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if "up to date" in update_result.stdout or "up-to-date" in update_result.stdout:
                logger.info("yt-dlpは最新です。")
            else:
                logger.info(f"yt-dlpを更新しました。結果: {update_result.stdout}")
            
            # 最終更新確認時刻を更新
            config['last_update_check'] = current_time
            save_config(config)
            
            return True, update_result.stdout
        except Exception as e:
            logger.error(f"yt-dlpの更新中にエラーが発生しました: {e}")
            return False, str(e)
    else:
        logger.info("前回の更新確認から24時間経過していないため、スキップします。")
        return True, "前回の更新確認から24時間経過していないため、スキップします。"

# 利用可能なフォーマットをチェック
def list_available_formats(url):
    """利用可能な解像度・フォーマットの一覧を取得"""
    cmd = [
        YTDLP_PATH,
        '-F',
        '--no-warnings',
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info(f"利用可能なフォーマット:\n{result.stdout}")
    return result.stdout

# 指定した解像度に最も近いフォーマットIDを選択する関数
def select_format_id_by_resolution(formats_output, target_resolution, format_type):
    """指定した解像度に最も近いフォーマットIDを選択"""
    if target_resolution == 'best':
        return None  # 'best'の場合はフォーマット文字列で指定するためNoneを返す
    
    # 解像度の数値部分を取得
    target_height = int(target_resolution.replace('p', ''))
    best_format_id = None
    best_height = 0
    best_codec = None
    
    # 利用可能なフォーマットから解像度とフォーマットタイプに一致するものを探す
    for line in formats_output.split('\n'):
        # 不要な行はスキップ
        if not re.match(r'^\d+\s', line):
            continue
        
        # フォーマットIDと情報を抽出
        parts = line.split()
        if len(parts) < 3:
            continue
        
        format_id = parts[0]
        
        # 拡張子が一致するか確認
        format_ext = parts[1] if len(parts) > 1 else ""
        if format_type == 'webm' and format_ext != 'webm':
            continue
        if format_type == 'mp4' and format_ext != 'mp4':
            continue
        
        # 映像のみのフォーマットかチェック
        if 'video only' not in line:
            continue
        
        # 解像度を抽出 (例: 1920x1080, 640x360)
        res_match = re.search(r'(\d+)x(\d+)', line)
        if not res_match:
            continue
        
        width = int(res_match.group(1))
        height = int(res_match.group(2))
        
        # コーデック情報を抽出
        codec_match = re.search(r'(av01|vp9|avc1)', line.lower())
        codec = codec_match.group(1) if codec_match else "unknown"
        
        # 指定解像度以下で最大のものを選択
        # AV1 > VP9 > H.264の優先順位で選択
        if height <= target_height:
            # 今までの最適な高さより大きい場合は更新
            if height > best_height:
                best_height = height
                best_format_id = format_id
                best_codec = codec
            # 同じ高さの場合はコーデックの優先度で判定
            elif height == best_height:
                if (best_codec != "av01" and codec == "av01") or \
                   (best_codec not in ["av01", "vp9"] and codec == "vp9"):
                    best_format_id = format_id
                    best_codec = codec
    
    if best_format_id:
        logger.info(f"選択したフォーマットID: {best_format_id} (解像度: {best_height}p, コーデック: {best_codec})")
        return best_format_id
    
    logger.warning(f"指定解像度 {target_resolution} に適合するフォーマットが見つかりませんでした")
    return None

# YouTubeビデオから利用可能な解像度のリストを取得
def get_available_resolutions(formats_output):
    """YouTubeビデオから利用可能な解像度のリストを取得する"""
    try:
        # 出力から解像度を抽出
        resolutions = set()
        for line in formats_output.split('\n'):
            # 解像度を含む行を探す (例: "137 mp4 1920x1080 1080p 4359k...")
            match = re.search(r'(\d+)x(\d+)\s+(\d+)p', line)
            if match:
                resolutions.add(int(match.group(3)))  # 解像度値（例：1080）
        
        # 数値としてソート
        res_list = sorted(list(resolutions), reverse=True)
        logger.info(f"利用可能な解像度: {', '.join([f'{r}p' for r in res_list])}")
        return res_list
    except Exception as e:
        logger.error(f"解像度リストの取得中にエラーが発生しました: {e}")
        return []

# メインのルート
@app.route('/')
def index():
    return jsonify({"status": "running", "message": "YouTube Downloader Server is running"})

# PINGエンドポイント
@app.route('/ping', methods=['GET'])
def ping():
    """サーバーの状態確認用エンドポイント"""
    return jsonify({"status": "ok"})

# バージョン情報の取得
@app.route('/version')
def get_version():
    try:
        result = subprocess.run(
            [YTDLP_PATH, '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            return jsonify({
                "status": "success",
                "yt_dlp_version": version,
                "server_version": "1.0.0"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"yt-dlpバージョンの取得に失敗しました: {result.stderr}"
            }), 500
    except Exception as e:
        logger.error(f"バージョン情報の取得中にエラーが発生しました: {e}")
        return jsonify({
            "status": "error",
            "message": f"バージョン情報の取得中にエラーが発生しました: {str(e)}"
        }), 500

# 更新チェック
@app.route('/update', methods=['POST'])
def update_ytdlp():
    try:
        success, message = check_and_update_ytdlp()
        if success:
            return jsonify({
                "status": "success",
                "message": message
            })
        else:
            return jsonify({
                "status": "error",
                "message": message
            }), 500
    except Exception as e:
        logger.error(f"更新処理中にエラーが発生しました: {e}")
        return jsonify({
            "status": "error",
            "message": f"更新処理中にエラーが発生しました: {str(e)}"
        }), 500

# 設定の取得
@app.route('/config', methods=['GET'])
def get_config():
    config = load_config()
    return jsonify({
        "status": "success",
        "config": config
    })

# 設定の更新
@app.route('/config', methods=['POST'])
def update_config():
    try:
        config = load_config()
        data = request.json
        
        # 受け取ったデータでconfigを更新
        if 'download_path' in data:
            config['download_path'] = data['download_path']
        if 'default_resolution' in data:
            config['default_resolution'] = data['default_resolution']
        if 'default_format' in data:
            config['default_format'] = data['default_format']
        if 'auto_update' in data:
            config['auto_update'] = data['auto_update']
        
        # 設定を保存
        if save_config(config):
            return jsonify({
                "status": "success",
                "message": "設定を更新しました。",
                "config": config
            })
        else:
            return jsonify({
                "status": "error",
                "message": "設定の保存に失敗しました。"
            }), 500
    except Exception as e:
        logger.error(f"設定更新中にエラーが発生しました: {e}")
        return jsonify({
            "status": "error",
            "message": f"設定更新中にエラーが発生しました: {str(e)}"
        }), 500

# 動画情報の取得
@app.route('/info', methods=['POST'])
def get_video_info():
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({
                "status": "error",
                "message": "URLが指定されていません。"
            }), 400
        
        # yt-dlpで動画情報を取得
        result = subprocess.run(
            [YTDLP_PATH, '-J', '--no-warnings', url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"動画情報の取得に失敗しました: {result.stderr}")
            return jsonify({
                "status": "error",
                "message": f"動画情報の取得に失敗しました: {result.stderr}"
            }), 500
        
        # 動画情報をJSONとしてパース
        try:
            video_info = json.loads(result.stdout)
            
            # 必要な情報だけを抽出
            simplified_info = {
                "title": video_info.get("title", "不明なタイトル"),
                "description": video_info.get("description", ""),
                "thumbnail": video_info.get("thumbnail", ""),
                "duration": video_info.get("duration", 0),
                "upload_date": video_info.get("upload_date", ""),
                "uploader": video_info.get("uploader", "不明なアップローダー"),
                "view_count": video_info.get("view_count", 0),
                "available_formats": []
            }
            
            # 利用可能なフォーマットを簡略化
            formats = video_info.get("formats", [])
            resolution_set = set()
            
            for fmt in formats:
                if fmt.get("vcodec") != "none" and fmt.get("height") is not None:
                    resolution = fmt.get("height")
                    resolution_set.add(resolution)
            
            # 解像度を数値として並べ替え
            simplified_info["available_resolutions"] = sorted(list(resolution_set), reverse=True)
            
            return jsonify({
                "status": "success",
                "video_info": simplified_info
            })
        except json.JSONDecodeError as e:
            logger.error(f"動画情報のJSONパースに失敗しました: {e}")
            return jsonify({
                "status": "error",
                "message": f"動画情報のJSONパースに失敗しました: {str(e)}"
            }), 500
            
    except Exception as e:
        logger.error(f"動画情報の取得中にエラーが発生しました: {e}")
        return jsonify({
            "status": "error",
            "message": f"動画情報の取得中にエラーが発生しました: {str(e)}"
        }), 500

# 動画のダウンロード - 修正バージョン（フォーマットIDを直接指定）
@app.route('/download', methods=['POST'])
def download_video():
    try:
        # FFmpegの確認
        if not check_ffmpeg():
            return jsonify({
                "status": "error",
                "message": "FFmpegがインストールされていないため、音声の変換ができません。"
            }), 500
        
        data = request.json
        url = data.get('url')
        resolution = data.get('resolution', 'best')
        format_type = data.get('format', 'mp4')
        
        logger.info(f"リクエスト: URL={url}, 解像度={resolution}, フォーマット={format_type}")
        
        if not url:
            return jsonify({
                "status": "error",
                "message": "URLが指定されていません。"
            }), 400
        
        # 利用可能なフォーマットとコーデック情報を取得
        format_output = list_available_formats(url)
        
        # 利用可能な解像度を取得して表示
        available_resolutions = get_available_resolutions(format_output)
        
        # ユーザーのダウンロードディレクトリを取得
        download_path = os.path.expanduser("~")
        
        # サニタイズされたファイル名を生成
        info_cmd = [YTDLP_PATH, '-j', '--no-warnings', url]
        info_result = subprocess.run(info_cmd, capture_output=True, text=True)
        if info_result.returncode != 0:
            return jsonify({
                "status": "error",
                "message": f"動画情報の取得に失敗しました: {info_result.stderr}"
            }), 500
            
        video_info = json.loads(info_result.stdout)
        video_title = sanitize_filename(video_info.get('title', 'video'))
        file_path = os.path.join(download_path, f"{video_title}.{format_type}")
        
        # MP3の場合は音声のみ
        if format_type == 'mp3':
            cmd = [
                YTDLP_PATH,
                '-f', 'bestaudio',
                '-x', '--audio-format', 'mp3',
                '--audio-quality', '0',
                '--add-metadata',  # メタデータを追加
                '--embed-thumbnail',  # サムネイルを埋め込む
                '-o', file_path,
                '--no-playlist',
                '--no-warnings',
                url
            ]
        else:
            # 具体的なフォーマットIDを取得
            format_id = select_format_id_by_resolution(format_output, resolution, format_type)
            
            if format_id and resolution != 'best':
                # フォーマットIDが見つかった場合は直接指定
                if format_type == 'mp4':
                    cmd = [
                        YTDLP_PATH,
                        '-f', f'{format_id}+bestaudio[ext=m4a]/bestaudio',
                        '--merge-output-format', 'mp4',
                        '--no-playlist',
                        '--no-warnings',
                        '--add-metadata',  # メタデータを追加
                        '--write-thumbnail',  # サムネイルも保存
                        '-o', file_path,
                        url
                    ]
                elif format_type == 'webm':
                    cmd = [
                        YTDLP_PATH,
                        '-f', f'{format_id}+bestaudio[ext=webm]/bestaudio',
                        '--merge-output-format', 'webm',
                        '--no-playlist',
                        '--no-warnings',
                        '--ignore-errors',  # エラーを無視して処理を続行
                        '--add-metadata',  # メタデータを追加
                        '--write-thumbnail',  # サムネイルも保存
                        '-o', file_path,
                        url
                    ]
            else:
                # フォーマットIDが見つからない場合やbestの場合は一般的なフォーマット指定
                if format_type == 'mp4':
                    # 最高解像度のMP4
                    cmd = [
                        YTDLP_PATH,
                        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                        '--merge-output-format', 'mp4',
                        '--no-playlist',
                        '--no-warnings',
                        '--add-metadata',
                        '--write-thumbnail',
                        '-o', file_path,
                        url
                    ]
                elif format_type == 'webm':
                    # 最高解像度のWebM
                    cmd = [
                        YTDLP_PATH,
                        '-f', 'bestvideo[ext=webm]+bestaudio[ext=webm]/bestvideo+bestaudio/best',
                        '--merge-output-format', 'webm',
                        '--no-playlist',
                        '--no-warnings',
                        '--ignore-errors',
                        '--add-metadata',
                        '--write-thumbnail',
                        '-o', file_path,
                        url
                    ]
        
        # コマンドを出力（デバッグ用）
        logger.info(f"実行コマンド: {' '.join(cmd)}")
        
        # ダウンロードの実行
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"ダウンロードに失敗しました: {result.stderr}")
            return jsonify({
                "status": "error",
                "message": f"ダウンロードに失敗しました: {result.stderr}"
            }), 500
        
        # ダウンロード結果を詳細に出力
        logger.info(f"ダウンロード結果: {result.stdout}")
        
        # ファイルが存在するか確認
        if not os.path.exists(file_path):
            logger.warning(f"指定パス {file_path} にファイルが見つかりません。別の名前で保存された可能性があります。")
            
            # 拡張子違いのファイルを探す
            dir_name = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # 拡張子リスト
            extensions = ['mp4', 'webm', 'mkv', 'mp3', 'm4a']
            
            for ext in extensions:
                alt_path = os.path.join(dir_name, f"{base_name}.{ext}")
                if os.path.exists(alt_path):
                    logger.info(f"別の拡張子で見つかりました: {alt_path}")
                    file_path = alt_path
                    break
            else:
                return jsonify({
                    "status": "error",
                    "message": "ダウンロードファイルが見つかりません"
                }), 500
        
        # ファイルURLを生成してレスポンス
        file_url = f"file:///{file_path.replace(os.sep, '/')}"
        return jsonify({
            "status": "success",
            "url": file_url,
            "title": video_title,
            "ext": os.path.splitext(file_path)[1][1:],
            "file_path": file_path,
            "resolution": resolution,
            "format": format_type
        })
            
    except Exception as e:
        logger.error(f"ダウンロード処理中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"ダウンロード処理中にエラーが発生しました: {str(e)}"
        }), 500

# 映像と音声を結合するエンドポイント
@app.route('/merge', methods=['POST'])
def merge_streams():
    try:
        data = request.json
        video_url = data.get('video_url')
        audio_url = data.get('audio_url')
        title = data.get('title', 'video')
        format_type = data.get('format', 'mp4')
        
        if not video_url or not audio_url:
            return jsonify({
                "status": "error",
                "message": "ビデオURLとオーディオURLの両方が必要です"
            }), 400
        
        # ユーザーのダウンロードディレクトリを取得
        download_path = os.path.expanduser("~")
        sanitized_title = sanitize_filename(title)
        output_file = os.path.join(download_path, f"{sanitized_title}.{format_type}")
        
        # 一時ファイル名を生成
        temp_video = os.path.join(download_path, f"temp_video_{int(time.time())}.{format_type}")
        temp_audio = os.path.join(download_path, f"temp_audio_{int(time.time())}.m4a")
        
        # 映像と音声を別々にダウンロード
        for url, output in [(video_url, temp_video), (audio_url, temp_audio)]:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(output, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # FFmpegで結合
        merge_cmd = [
            'ffmpeg',
            '-i', temp_video,
            '-i', temp_audio,
            '-c', 'copy',
            '-map', '0:v',
            '-map', '1:a',
            '-y',
            output_file
        ]
        
        result = subprocess.run(merge_cmd, capture_output=True, text=True)
        
        # 一時ファイルを削除
        try:
            os.remove(temp_video)
            os.remove(temp_audio)
        except:
            pass
        
        if result.returncode != 0:
            return jsonify({
                "status": "error",
                "message": f"ファイルの結合に失敗しました: {result.stderr}"
            }), 500
        
        # 結合されたファイルのURLを返す
        file_url = f"file:///{output_file.replace(os.sep, '/')}"
        return jsonify({
            "status": "success",
            "file_url": file_url,
            "file_path": output_file
        })
        
    except Exception as e:
        logger.error(f"ストリーム結合中にエラーが発生しました: {e}")
        return jsonify({
            "status": "error",
            "message": f"ストリーム結合中にエラーが発生しました: {str(e)}"
        }), 500

# 利用可能なフォーマットIDを取得するエンドポイント
@app.route('/formats', methods=['POST'])
def get_format_ids():
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({
                "status": "error",
                "message": "URLが指定されていません。"
            }), 400
        
        # フォーマット情報を取得
        format_output = list_available_formats(url)
        
        # 各解像度のフォーマットIDを抽出
        resolutions = {}
        for line in format_output.split('\n'):
            if not re.match(r'^\d+\s', line):
                continue
                
            parts = line.split()
            if len(parts) < 3:
                continue
                
            format_id = parts[0]
            format_ext = parts[1] if len(parts) > 1 else ""
            
            # 解像度を抽出
            res_match = re.search(r'(\d+)x(\d+)', line)
            if not res_match:
                continue
                
            height = int(res_match.group(2))
            
            # 映像のみのフォーマットを対象
            if 'video only' not in line:
                continue
                
            # コーデック情報
            codec_match = re.search(r'(av01|vp9|avc1)', line.lower())
            codec = codec_match.group(1) if codec_match else "unknown"
            
            # 解像度ごとにフォーマット情報を保存
            if height not in resolutions:
                resolutions[height] = []
                
            resolutions[height].append({
                "format_id": format_id,
                "ext": format_ext,
                "codec": codec,
                "info": line
            })
        
        # 解像度でソート
        sorted_resolutions = {}
        for height in sorted(resolutions.keys(), reverse=True):
            sorted_resolutions[f"{height}p"] = resolutions[height]
        
        return jsonify({
            "status": "success",
            "formats": sorted_resolutions
        })
        
    except Exception as e:
        logger.error(f"フォーマットID取得中にエラーが発生しました: {e}")
        return jsonify({
            "status": "error",
            "message": f"フォーマットID取得中にエラーが発生しました: {str(e)}"
        }), 500

# サーバー状態の確認
@app.route('/status')
def server_status():
    return jsonify({
        "status": "running",
        "time": datetime.now().isoformat(),
        "yt_dlp_exists": os.path.exists(YTDLP_PATH)
    })

# サーバー起動時の処理
def on_startup():
    # 設定読み込みとダウンロードディレクトリの作成
    config = load_config()
    download_path = config.get('download_path', DEFAULT_CONFIG['download_path'])
    
    if not os.path.exists(download_path):
        try:
            os.makedirs(download_path, exist_ok=True)
            logger.info(f"ダウンロードディレクトリを作成しました: {download_path}")
        except Exception as e:
            logger.error(f"ダウンロードディレクトリの作成に失敗しました: {e}")
    
    # FFmpegとaria2cの確認
    check_ffmpeg()
    check_aria2c()
    
    # 自動更新が有効なら更新チェック
    if config.get('auto_update', DEFAULT_CONFIG['auto_update']):
        threading.Thread(target=check_and_update_ytdlp).start()

# サーバー終了時の処理
def on_shutdown():
    logger.info("サーバーを終了します。")

if __name__ == '__main__':
    on_startup()
    atexit.register(on_shutdown)
    
    # コマンドライン引数でポート指定があれば使用
    port = 8745  # デフォルトポート
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    
    try:
        logger.info(f"サーバーを開始します。ポート: {port}")
        app.run(host='127.0.0.1', port=port, debug=False)
    except Exception as e:
        logger.error(f"サーバー起動中にエラーが発生しました: {e}")
        sys.exit(1)
