// background.js

// バックグラウンド処理とPythonサーバー連携
const SERVER_PORT = 8745;
const SERVER_URL = `http://localhost:${SERVER_PORT}`;
let serverRunning = false;
let retryCount = 0;
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // 1秒

// サーバーステータスのチェック（改善版）
async function checkServerStatus(silent = false) {
    try {
        if (!silent) {
            console.log('Checking server status...');
        }
        
        const response = await fetch(`${SERVER_URL}/ping`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            serverRunning = data.status === 'ok';
            
            if (!silent) {
                console.log('Server status:', serverRunning ? 'running' : 'not running');
            }
            
            retryCount = 0; // リセット
            return serverRunning;
        }
        
        throw new Error(`Server responded with status: ${response.status}`);
    } catch (error) {
        if (!silent) {
            console.error('Server check failed:', error.message);
        }
        
        // リトライロジック
        if (retryCount < MAX_RETRIES) {
            retryCount++;
            
            if (!silent) {
                console.log(`Retrying... (${retryCount}/${MAX_RETRIES})`);
            }
            
            await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
            return checkServerStatus(silent);
        }
        
        serverRunning = false;
        return false;
    }
}

// 有効なファイル名に変換する関数
function sanitizeFilename(filename) {
    // Windowsで使用できない文字を削除または置換
    return filename
        .replace(/[\\/:*?"<>|]/g, '') // 使用できない文字を削除
        .replace(/\s+/g, ' ') // 連続する空白を1つに
        .trim(); // 先頭と末尾の空白を削除
}

// サーバーへの動画ダウンロードリクエスト
async function requestDownload(url, resolution, format, retryCount = 0) {
    const MAX_RETRIES = 3;
    const RETRY_DELAY = 2000; // 2秒
    
    try {
        console.log('Sending download request:', { url, resolution, format });
        
        // リクエスト前にサーバー状態を確認
        const serverStatus = await checkServerStatus(true);
        if (!serverStatus) {
            throw new Error('サーバーが応答していません。サーバーを起動してください。');
        }
        
        const response = await fetch(`${SERVER_URL}/download`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                resolution: resolution,
                format: format
            })
        });
        
        const data = await response.json();
        console.log('Server response:', data);
        
        // エラー応答の処理
        if (data.status === 'error') {
            throw new Error(data.message || 'ダウンロードに失敗しました');
        }
        
        // ストリームURLを処理
        const sanitizedTitle = sanitizeFilename(data.title || 'video');
        const filename = `${sanitizedTitle}.${data.ext}`;
        
        // 映像と音声が別々のURLとして返された場合
        if (data.requires_merge) {
            console.log('Requires merging video and audio');
            // サーバー側でマージをリクエスト
            const mergeResponse = await fetch(`${SERVER_URL}/merge`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: data.title,
                    video_url: data.video_url,
                    audio_url: data.audio_url,
                    format: data.ext
                })
            });
            
            const mergeResult = await mergeResponse.json();
            if (mergeResult.status === 'error') {
                throw new Error(mergeResult.message || 'ファイルの結合に失敗しました');
            }
            
            // 結合されたファイルをダウンロード
            await chrome.downloads.download({
                url: mergeResult.file_url,
                filename: filename,
                saveAs: false,
                conflictAction: 'uniquify'
            });
        } else {
            // 単一のURLが返された場合
            console.log('Downloading single URL:', data.url);
            await chrome.downloads.download({
                url: data.url,
                filename: filename,
                saveAs: false,
                conflictAction: 'uniquify'
            });
        }
        
        return {
            success: true,
            message: 'ダウンロードを開始しました'
        };
    } catch (error) {
        console.error('Download request failed:', error.message);
        
        // リトライ処理
        if (retryCount < MAX_RETRIES) {
            console.log(`Retrying download (${retryCount + 1}/${MAX_RETRIES})...`);
            await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
            return requestDownload(url, resolution, format, retryCount + 1);
        }
        
        throw error;
    }
}



// メッセージリスナー
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('Received message:', message);
    
    if (message.action === 'download') {
        const videoUrl = `https://www.youtube.com/watch?v=${message.videoId}`;
        
        (async () => {
            try {
                // サーバー状態を確認（サイレントモード）
                const isServerRunning = await checkServerStatus(true);
                if (!isServerRunning) {
                    throw new Error('サーバーが応答していません。native_host/start.batを実行してください。');
                }
                
                const result = await requestDownload(videoUrl, message.resolution, message.format);
                sendResponse(result);
            } catch (error) {
                console.error('Error:', error.message);
                sendResponse({ error: error.message });
            }
        })();
        
        return true; // 非同期レスポンスを示す
    }
    
    if (message.action === 'check_server') {
        checkServerStatus()
            .then(isRunning => {
                sendResponse({ serverRunning: isRunning });
            })
            .catch(error => {
                console.error('Server check error:', error.message);
                sendResponse({ serverRunning: false, error: error.message });
            });
        
        return true; // 非同期レスポンスを示す
    }
    
    if (message.action === 'check_server_status') {
        checkServerStatus()
            .then(isRunning => {
                sendResponse({ serverRunning: isRunning });
            })
            .catch(error => {
                console.error('Server status check error:', error.message);
                sendResponse({ serverRunning: false, error: error.message });
            });
        
        return true; // 非同期レスポンスを示す
    }
    
    if (message.action === 'start_server') {
        // このメッセージハンドラーはダミーです
        // 実際のサーバー起動処理はネイティブメッセージングかNativeホストで行う必要があります
        sendResponse({ success: false, message: 'サーバー起動機能は実装されていません' });
        return true;
    }
});

// サーバーステータスの定期チェック
let statusCheckInterval;

function startStatusCheck() {
    if (!statusCheckInterval) {
        // 初回チェック
        checkServerStatus(true);
        
        // 30秒ごとにチェック
        statusCheckInterval = setInterval(() => checkServerStatus(true), 30000);
    }
}

function stopStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
}

// 拡張機能の起動時と停止時の処理
chrome.runtime.onStartup.addListener(startStatusCheck);
chrome.runtime.onSuspend.addListener(stopStatusCheck);

// バックグラウンドスクリプトロード時に開始
startStatusCheck();
