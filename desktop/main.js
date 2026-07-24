const { app, BrowserWindow, shell, dialog } = require('electron')
const path = require('path')

// electron-updater는 패키징된 앱에서만 동작 (개발 실행 시 없어도 무방)
let autoUpdater = null
try {
  autoUpdater = require('electron-updater').autoUpdater
} catch (e) {
  autoUpdater = null
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1024,
    minHeight: 700,
    title: 'BRAUMM 사무 도구',
    backgroundColor: '#eceae6',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.setMenuBarVisibility(false)
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'))

  // 외부 링크는 기본 브라우저로
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) {
      shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })

  return win
}

function setupAutoUpdate() {
  if (!autoUpdater) return
  autoUpdater.autoDownload = true
  autoUpdater.on('update-downloaded', (info) => {
    dialog
      .showMessageBox({
        type: 'info',
        buttons: ['지금 재시작', '나중에'],
        defaultId: 0,
        title: '업데이트 준비 완료',
        message: `새 버전(${info.version})이 준비되었습니다. 지금 재시작하여 적용할까요?`,
      })
      .then((res) => {
        if (res.response === 0) autoUpdater.quitAndInstall()
      })
  })
  autoUpdater.on('error', () => {
    // 업데이트 확인 실패는 조용히 무시 (오프라인 등)
  })
  try {
    autoUpdater.checkForUpdatesAndNotify()
  } catch (e) {
    // 무시
  }
}

app.whenReady().then(() => {
  createWindow()
  setupAutoUpdate()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
