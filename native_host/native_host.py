import sys, json, subprocess, os, traceback, logging
from typing import Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket
import time
import re
from urllib.parse import parse_qs, urlparse

# デバッグログの設定
log_file = os.path.join(os.path.dirname(__file__), 'native_host.log')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# 既存のハンドラーをクリア
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# ファイルハンドラーの追加
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# コンソールハンドラーの追加
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

def load_config():
    """設定ファイルを読み込む"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'config.json')
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"設定ファイルの読み込みエラー: {str(e)}")
    return {}

def check_ffmpeg():
    """FFmpegが利用可能か確認"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        if result.returncode == 0:
            logging.info("FFmpegが利用可能です")
            return True
    except:
        logging.warning("FFmpegが見つかりません。動画変換に問題が発生する可能性があります。")
    return False

def check_aria2c():
    """aria2cが利用可能か確認"""
    try:
        result = subprocess.run(['aria2c', '--version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        if result.returncode == 0:
            logging.info("aria2cが利用可能です")
            return True
    except:
        logging.info("aria2cが見つかりません。標準ダウンローダーを使用します。")
    return False

# ツール自動インストール関数
def install_ffmpeg():
    """FFmpegを自動インストール"""
    try:
        if os.name == 'nt':  # Windows
            import urllib.request
            import zipfile
            
            logging.info("FFmpegをダウンロードしています...")
            ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            zip_path = os.path.join(os.path.dirname(__file__), "ffmpeg.zip")
            
            urllib.request.urlretrieve(ffmpeg_url, zip_path)
            
            logging.info("FFmpegを展開しています...")
            extract_path = os.path.join(os.path.dirname(__file__), "ffmpeg")
            os.makedirs(extract_path, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
                
            # FFmpegのパスを環境変数に追加
            ffmpeg_bin = os.path.join(extract_path, "ffmpeg-master-latest-win64-gpl", "bin")
            os.environ["PATH"] += os.pathsep + ffmpeg_bin
            
            # ZIPファイルを削除
            os.remove(zip_path)
            
            logging.info(f"FFmpegを {ffmpeg_bin} にインストールしました")
            return True
        else:
            logging.error("自動インストールはWindowsのみサポートしています")
            return False
    except Exception as e:
        logging.error(f"FFmpegのインストールに失敗しました: {e}")
        return False

class DownloadProcess:
    def __init__(self):
        self.process = None
        # 設定からダウンロードパスを取得（ユーザーディレクトリに変更）
        config = load_config()
        self.download_path = config.get('download_path') or os.path.expanduser('~')
        self.yt_dlp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'yt-dlp.exe'))
        logging.info(f"Download path: {self.download_path}")
        logging.info(f"yt-dlp path: {self.yt_dlp_path}")
        
        # FFmpegとaria2cを確認
        self.ffmpeg_available = check_ffmpeg()
        self.aria2c_available = check_aria2c()
        
        # FFmpegが利用できない場合はインストールを試みる
        if not self.ffmpeg_available:
            self.ffmpeg_available = install_ffmpeg()

    def check_yt_dlp(self):
        """yt-dlpの存在とアクセス権を確認"""
        if not os.path.exists(self.yt_dlp_path):
            logging.error(f"yt-dlp.exeが見つかりません: {self.yt_dlp_path}")
            raise FileNotFoundError(f"yt-dlp.exeが見つかりません: {self.yt_dlp_path}")
        try:
            with open(self.yt_dlp_path, 'rb') as f:
                pass
            logging.debug(f"yt-dlp.exeへのアクセス成功: {self.yt_dlp_path}")
        except Exception as e:
            logging.error(f"yt-dlp.exeへのアクセス失敗: {str(e)}")
            raise

    def download_video(self, url: str, resolution: str, fmt: str) -> Dict:
        """動画のストリームURLを取得"""
        process = None
        try:
            logging.info(f"Getting stream URL: url={url}, resolution={resolution}, format={fmt}")
            self.check_yt_dlp()
            
            # フォーマット文字列を構築
            if fmt == 'mp3':
                format_spec = 'bestaudio'
                ext = 'mp3'
            else:
                # 解像度に基づいてformat_specを構築
                if resolution == 'best':
                    if fmt == 'mp4':
                        format_spec = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                    elif fmt == 'webm':
                        format_spec = 'bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best'
                    else:
                        format_spec = 'bestvideo+bestaudio/best'
                else:
                    # 解像度から数値部分を抽出
                    height = resolution.replace('p', '')  # 360p → 360
                    if not height.isdigit():
                        height = 1080
                    
                    if fmt == 'mp4':
                        format_spec = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best'
                    elif fmt == 'webm':
                        format_spec = f'bestvideo[height<={height}][ext=webm]+bestaudio[ext=webm]/best[height<={height}][ext=webm]/best'
                    else:
                        format_spec = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/best'
                ext = fmt
            
            # 動画情報を取得
            info_cmd = [
                self.yt_dlp_path,
                '--dump-json',
                '--no-warnings',
                '--no-playlist',
                url
            ]
            
            info_process = subprocess.run(
                info_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if info_process.returncode != 0:
                return {"success": False, "error": f"動画情報の取得に失敗しました"}
            
            # タイトル取得とサニタイズ
            try:
                video_info = json.loads(info_process.stdout)
                title = video_info.get('title', 'video')
                title = re.sub(r'[\\/*?:"<>|]', '', title)
            except:
                title = 'video'
            
            # ストリームURLを取得
            url_cmd = [
                self.yt_dlp_path,
                '-f', format_spec,
                '--get-url',
                '--no-warnings',
                '--no-playlist',
                url
            ]
            
            url_process = subprocess.run(
                url_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if url_process.returncode != 0:
                return {"success": False, "error": f"ストリームURLの取得に失敗しました"}
            
            # 結果が複数行ある場合（映像と音声が別々）
            stream_urls = url_process.stdout.strip().split('\n')
            video_url = stream_urls[0] if stream_urls else None
            audio_url = stream_urls[1] if len(stream_urls) > 1 else None
            
            if not video_url:
                return {"success": False, "error": "ストリームURLが空です"}
            
            # 映像・音声両方のURLを返す場合
            if audio_url:
                return {
                    "success": True, 
                    "video_url": video_url,
                    "audio_url": audio_url,
                    "title": title, 
                    "ext": ext,
                    "requires_merge": True
                }
            else:
                # 単一のURLの場合
                return {
                    "success": True, 
                    "url": video_url, 
                    "title": title, 
                    "ext": ext,
                    "requires_merge": False
                }
            
        except Exception as e:
            logging.error(f"Error in get_stream_url: {str(e)}")
            logging.error(traceback.format_exc())
            return {"success": False, "error": str(e)}

class DownloadHandler(BaseHTTPRequestHandler):
    downloader = None
    
    def send_error_response(self, status_code, message):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """GETリクエストの処理"""
        if self.path == '/ping':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            return
        elif self.path == '/config':
            try:
                config = load_config()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(config).encode('utf-8'))
                return
            except Exception as e:
                self.send_error_response(500, str(e))
                return
        
        self.send_response(404)
        self.end_headers()
    
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            if self.path == '/config':
                try:
                    config = load_config()
                    if 'download_path' in data:
                        config['download_path'] = data['download_path']
                        if not os.path.exists(data['download_path']):
                            os.makedirs(data['download_path'])
                    
                    # 追加の設定パラメータの保存
                    if 'default_resolution' in data:
                        config['default_resolution'] = data['default_resolution']
                    if 'default_format' in data:
                        config['default_format'] = data['default_format']
                    
                    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'config.json')
                    os.makedirs(os.path.dirname(config_path), exist_ok=True)
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                    
                    if self.downloader:
                        self.downloader.download_path = data.get('download_path', self.downloader.download_path)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
                    return
                except Exception as e:
                    self.send_error_response(500, str(e))
                    return
            
            if not all(k in data for k in ['url', 'resolution', 'format']):
                self.send_error_response(400, "無効なリクエスト形式です")
                return
            
            try:
                if not self.downloader:
                    self.downloader = DownloadProcess()
                
                response = self.downloader.download_video(
                    data['url'],
                    data['resolution'],
                    data['format']
                )
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response_data = json.dumps(response).encode('utf-8')
                
                try:
                    self.wfile.write(response_data)
                except (ConnectionAbortedError, BrokenPipeError) as e:
                    logging.error(f"Connection error while sending response: {str(e)}")
                    # クライアントが切断した場合は静かに終了
                    return
            except Exception as e:
                logging.error(f"Error during download: {str(e)}")
                logging.error(traceback.format_exc())
                self.send_error_response(500, str(e))
        except Exception as e:
            logging.error(f"Error handling request: {str(e)}")
            logging.error(traceback.format_exc())
            try:
                self.send_error_response(500, str(e))
            except (ConnectionAbortedError, BrokenPipeError):
                logging.error("Connection closed while sending error response")
                return
    
    def handle(self):
        try:
            super().handle()
        except (ConnectionAbortedError, BrokenPipeError) as e:
            logging.error(f"Connection error in handler: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error in handler: {str(e)}")
            logging.error(traceback.format_exc())

def find_free_port():
    """利用可能なポート番号を取得"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def create_handler(*args, **kwargs):
    """ハンドラーインスタンスを作成する関数"""
    def _handler(*handler_args):
        DownloadHandler(*handler_args, **kwargs)
    return _handler

def main():
    try:
        logging.info("Starting HTTP server...")
        port = 8745  # 固定ポート番号を使用
        
        # ポート番号をファイルに保存
        port_file = os.path.join(os.path.dirname(__file__), 'server_port.txt')
        with open(port_file, 'w') as f:
            f.write(str(port))
        
        # サーバーの初期化とダウンローダーの設定
        DownloadHandler.downloader = DownloadProcess()
        server = HTTPServer(('localhost', port), DownloadHandler)
        logging.info(f"Server started on port {port}")
        print(f"SERVER_PORT={port}")  # この出力は必須（Chrome拡張機能が読み取ります）
        
        server.serve_forever()
    except Exception as e:
        logging.critical(f"Fatal error in main: {str(e)}")
        logging.critical(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
