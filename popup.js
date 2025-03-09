// popup.js

document.addEventListener('DOMContentLoaded', function() {
  // 設定の読み込みと表示
  loadSettings();
  
  // サーバーステータスの確認
  checkServerStatus();
  
  // サーバー起動ボタンの設定
  document.getElementById('start-server').addEventListener('click', startServer);
  
  // 設定変更イベントの設定
  document.getElementById('default-resolution').addEventListener('change', saveSettings);
  document.getElementById('default-format').addEventListener('change', saveSettings);
  
  // ダウンロードパス設定の初期化
  loadDownloadPath();
  
  // パス設定ボタンのイベントリスナー
  document.getElementById('browse-path').addEventListener('click', browseFolder);
  document.getElementById('save-path').addEventListener('click', saveDownloadPath);
});

// 設定の読み込み
function loadSettings() {
  chrome.storage.sync.get({
      defaultResolution: '1080',
      defaultFormat: 'mp4',
      downloadPath: ''
  }, function(items) {
      document.getElementById('default-resolution').value = items.defaultResolution;
      document.getElementById('default-format').value = items.defaultFormat;
      
      // ダウンロードパスの表示
      const downloadPathInput = document.getElementById('download-path');
      if (items.downloadPath) {
          downloadPathInput.value = items.downloadPath;
      } else {
          downloadPathInput.value = 'デフォルトのダウンロードフォルダ';
      }
  });
}

// 設定の保存
function saveSettings() {
  const resolution = document.getElementById('default-resolution').value;
  const format = document.getElementById('default-format').value;
  
  chrome.storage.sync.set({
      defaultResolution: resolution,
      defaultFormat: format
  }, function() {
      // 保存成功時の処理
      const statusElement = document.createElement('div');
      statusElement.className = 'save-status';
      statusElement.textContent = '設定を保存しました';
      
      // 既存のステータス要素を削除
      const existingStatus = document.querySelector('.save-status');
      if (existingStatus) {
          existingStatus.remove();
      }
      
      // ステータス要素を追加
      document.querySelector('.settings-container').appendChild(statusElement);
      
      // 2秒後に消す
      setTimeout(() => {
          statusElement.remove();
      }, 2000);
      
      // サーバーに設定を反映
      syncSettingsWithServer(resolution, format);
  });
}

// サーバーと設定を同期
async function syncSettingsWithServer(resolution, format) {
  try {
      const response = await fetch('http://localhost:8745/config', {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify({
              default_resolution: resolution,
              default_format: format
          })
      });
      
      if (!response.ok) {
          console.error('サーバーとの設定同期に失敗しました');
      }
  } catch (error) {
      console.error('サーバーとの通信中にエラーが発生しました:', error);
  }
}

// サーバーステータスの確認
function checkServerStatus() {
  const statusIndicator = document.getElementById('server-status');
  const statusText = document.getElementById('status-text');
  
  // バックグラウンドスクリプトにサーバーステータスの確認を要求
  chrome.runtime.sendMessage({action: 'check_server_status'}, function(response) {
      if (response && response.serverRunning) {
          statusIndicator.className = 'status-indicator status-online';
          statusText.textContent = 'サーバー稼働中';
          document.getElementById('start-server').disabled = true;
      } else {
          statusIndicator.className = 'status-indicator status-offline';
          statusText.textContent = 'サーバー停止中';
          document.getElementById('start-server').disabled = false;
      }
  });
}

// サーバー起動
function startServer() {
  const button = document.getElementById('start-server');
  const statusText = document.getElementById('status-text');
  
  button.disabled = true;
  button.textContent = '起動中...';
  statusText.textContent = 'サーバー起動処理中...';
  
  chrome.runtime.sendMessage({action: 'start_server'}, function(response) {
      if (response && response.success) {
          document.getElementById('server-status').className = 'status-indicator status-online';
          statusText.textContent = 'サーバー稼働中';
          button.textContent = 'サーバー起動済み';
      } else {
          document.getElementById('server-status').className = 'status-indicator status-offline';
          statusText.textContent = 'サーバー起動失敗';
          button.disabled = false;
          button.textContent = '再試行';
      }
  });
}

// ダウンロードパスの読み込み
async function loadDownloadPath() {
  try {
      const response = await fetch('http://localhost:8745/config');
      const config = await response.json();
      
      const downloadPathInput = document.getElementById('download-path');
      if (config.config && config.config.download_path) {
          downloadPathInput.value = config.config.download_path;
      }
  } catch (error) {
      console.error('設定の読み込みに失敗しました:', error);
  }
}

// フォルダ選択ダイアログを開く
function browseFolder() {
  const input = document.createElement('input');
  input.type = 'file';
  input.webkitdirectory = true;
  
  input.addEventListener('change', (event) => {
      if (event.target.files.length > 0) {
          const path = event.target.files[0].path;
          document.getElementById('download-path').value = path.substring(0, path.lastIndexOf('\\'));
      }
  });
  
  input.click();
}

// ダウンロードパスの保存
async function saveDownloadPath() {
  const path = document.getElementById('download-path').value;
  if (!path) {
      alert('ダウンロード先フォルダを選択してください。');
      return;
  }
  
  try {
      const response = await fetch('http://localhost:8745/config', {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify({
              download_path: path
          })
      });
      
      if (response.ok) {
          // 保存成功時の処理
          const statusElement = document.createElement('div');
          statusElement.className = 'save-status';
          statusElement.textContent = 'ダウンロードパスを保存しました';
          
          // 既存のステータス要素を削除
          const existingStatus = document.querySelector('.save-status');
          if (existingStatus) {
              existingStatus.remove();
          }
          
          // ステータス要素を追加
          document.querySelector('.settings-container').appendChild(statusElement);
          
          // 2秒後に消す
          setTimeout(() => {
              statusElement.remove();
          }, 2000);
          
          // Chromeストレージにも保存
          chrome.storage.sync.set({
              downloadPath: path
          });
      } else {
          throw new Error('設定の保存に失敗しました。');
      }
  } catch (error) {
      console.error('設定の保存に失敗しました:', error);
      alert('設定の保存に失敗しました: ' + error.message);
  }
}
