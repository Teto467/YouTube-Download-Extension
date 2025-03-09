// content.js
// YouTubeプレイヤーの監視とダウンロードボタンの追加
function addDownloadButton() {
  // プレイヤーのコントロールバー要素を取得
  const playerControls = document.querySelector('.ytp-right-controls');
  
  if (playerControls && !document.querySelector('.ytp-download-button')) {
    // ダウンロードボタン要素を作成
    const downloadButton = document.createElement('button');
    downloadButton.className = 'ytp-button ytp-download-button';
    downloadButton.title = '動画をダウンロード';
    downloadButton.innerHTML = `
      <svg height="100%" viewBox="0 0 36 36" width="100%">
        <path d="M17 12v9h2v-9h-2zm1 12.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z" fill="#fff"></path>
        <path d="M16 4v4h4V4h-4zm2 16l-4-4h2.5v-3h3v3H22l-4 4z" fill="#fff"></path>
      </svg>
    `;
    
    // ダウンロードオプションパネルを作成
    const optionsPanel = document.createElement('div');
    optionsPanel.className = 'ytp-download-menu';
    optionsPanel.style.display = 'none';
    optionsPanel.innerHTML = `
      <div class="format-options">
        <select id="resolution">
          <option value="360">360p</option>
          <option value="720">720p</option>
          <option value="1080" selected>1080p</option>
          <option value="best">最高画質</option>
        </select>
        <select id="format">
          <option value="mp4" selected>MP4</option>
          <option value="webm">WebM</option>
          <option value="mp3">MP3 (音声のみ)</option>
        </select>
        <button id="start-download">
          <span class="button-content">ダウンロード開始</span>
          <div class="download-progress"></div>
        </button>
        <div class="download-status"></div>
      </div>
    `;
    
    // ボタンクリックイベントの追加
    downloadButton.addEventListener('click', () => {
      optionsPanel.style.display = optionsPanel.style.display === 'none' ? 'block' : 'none';
    });
    
    // プレイヤーにボタンを追加
    playerControls.appendChild(downloadButton);
    playerControls.parentNode.appendChild(optionsPanel);
    
    // ダウンロードボタンのイベント設定
    document.getElementById('start-download').addEventListener('click', async () => {
      const button = optionsPanel.querySelector('#start-download');
      const buttonContent = button.querySelector('.button-content');
      const progressBar = button.querySelector('.download-progress');
      const statusDiv = optionsPanel.querySelector('.download-status');
      
      try {
        button.disabled = true;
        buttonContent.innerHTML = '<span class="loading-icon"></span>ダウンロード中...';
        statusDiv.textContent = '準備中...';
        progressBar.style.width = '10%';
        
        const resolution = document.getElementById('resolution').value;
        const format = document.getElementById('format').value;
        const videoId = new URLSearchParams(window.location.search).get('v');
        
        if (!videoId) {
          throw new Error('動画IDが見つかりません。');
        }

        // サーバーステータスのチェック
        const statusCheck = await chrome.runtime.sendMessage({ action: 'check_server' });
        if (!statusCheck || !statusCheck.serverRunning) {
          throw new Error('サーバーが起動していません。native_host/start.batを実行してください。');
        }
        
        progressBar.style.width = '30%';
        statusDiv.textContent = 'ダウンロード開始...';
        
        // ダウンロードリクエストの送信
        const response = await new Promise((resolve, reject) => {
          chrome.runtime.sendMessage({
            action: 'download',
            videoId: videoId,
            resolution: resolution,
            format: format
          }, (response) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else if (response && response.error) {
              reject(new Error(response.error));
            } else {
              resolve(response);
            }
          });
        });

        progressBar.style.width = '100%';
        statusDiv.textContent = 'ダウンロード完了！';
        buttonContent.textContent = '完了';
        
        // 3秒後にパネルを閉じる
        setTimeout(() => {
          optionsPanel.style.display = 'none';
          // UIをリセット
          buttonContent.textContent = 'ダウンロード開始';
          button.disabled = false;
          progressBar.style.width = '0%';
          statusDiv.textContent = '';
        }, 3000);
        
      } catch (error) {
        console.error('Download error:', error);
        let errorMessage = error.message;
        
        // DOMException特有のエラーメッセージを変換
        if (error.name === 'AbortError') {
          errorMessage = 'ダウンロードがキャンセルされました。';
        } else if (error instanceof DOMException) {
          errorMessage = 'ブラウザでエラーが発生しました: ' + error.message;
        }
        
        statusDiv.textContent = 'エラー: ' + errorMessage;
        buttonContent.textContent = 'エラー';
        progressBar.style.width = '0%';
        
        // 5秒後にボタンをリセット
        setTimeout(() => {
          buttonContent.textContent = 'ダウンロード開始';
          button.disabled = false;
          statusDiv.textContent = '';
        }, 5000);
      }
    });

    // ドキュメントクリックイベントでパネルを閉じる
    document.addEventListener('click', (event) => {
      if (!optionsPanel.contains(event.target) && 
          !downloadButton.contains(event.target) && 
          optionsPanel.style.display === 'block') {
        optionsPanel.style.display = 'none';
      }
    });
  }
}

// YouTubeのDOM変更を監視してダウンロードボタンを追加
function initButtonObserver() {
  const observer = new MutationObserver((mutations) => {
    if (document.querySelector('.ytp-right-controls') && !document.querySelector('.ytp-download-button')) {
      addDownloadButton();
    }
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
}

// 初期化
function init() {
  if (window.location.pathname === '/watch') {
    addDownloadButton();
    initButtonObserver();
  }
}

// ページ読み込み時とURLの変更時に実行
init();
window.addEventListener('yt-navigate-finish', init);
