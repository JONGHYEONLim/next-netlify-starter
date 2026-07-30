const { app, BrowserWindow, shell, dialog, ipcMain, safeStorage } = require('electron')
const path = require('path')
const fs = require('fs')

// electron-updater는 패키징된 앱에서만 동작 (개발 실행 시 없어도 무방)
let autoUpdater = null
try {
  autoUpdater = require('electron-updater').autoUpdater
} catch (e) {
  autoUpdater = null
}

let mainWindow = null
const credPath = () => path.join(app.getPath('userData'), 'mail.cred')
const backupPath = () => path.join(app.getPath('userData'), 'braumm-autobackup.json')

// ===== 자동 백업: 저장할 때마다 데이터 파일로 기록 (localStorage 유실 대비) =====
ipcMain.handle('data:save', (evt, data) => {
  try {
    fs.writeFileSync(backupPath(), JSON.stringify(data))
    return { ok: true }
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) }
  }
})
ipcMain.handle('data:load', () => {
  try {
    if (!fs.existsSync(backupPath())) return null
    return JSON.parse(fs.readFileSync(backupPath(), 'utf8'))
  } catch (e) {
    return null
  }
})

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1024,
    minHeight: 700,
    title: 'BRAUMM 사무 도구',
    backgroundColor: '#eceae6',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  mainWindow.setMenuBarVisibility(false)
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'))

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) {
      shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })

  return mainWindow
}

// ===== 메일 비밀번호 (앱 비밀번호) 안전 저장 =====
ipcMain.handle('mail:has', () => {
  try {
    return fs.existsSync(credPath())
  } catch (e) {
    return false
  }
})

ipcMain.handle('mail:save', (evt, pw) => {
  try {
    if (!pw) return { ok: false, error: '비밀번호가 비어 있습니다.' }
    if (!safeStorage.isEncryptionAvailable()) {
      return { ok: false, error: '이 PC에서 암호화 저장을 사용할 수 없습니다.' }
    }
    const enc = safeStorage.encryptString(String(pw))
    fs.writeFileSync(credPath(), enc)
    return { ok: true }
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) }
  }
})

ipcMain.handle('mail:clear', () => {
  try {
    if (fs.existsSync(credPath())) fs.unlinkSync(credPath())
    return { ok: true }
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) }
  }
})

// ===== 메일 발송 (현재 문서를 PDF로 만들어 첨부) =====
ipcMain.handle('mail:send', async (evt, p) => {
  try {
    if (!fs.existsSync(credPath())) {
      return { ok: false, error: '메일 앱 비밀번호가 저장되어 있지 않습니다. 이메일 설정에서 먼저 저장하세요.' }
    }
    const pass = safeStorage.decryptString(fs.readFileSync(credPath()))

    // 현재 창을 인쇄용(@media print) 레이아웃으로 PDF 생성 → 시트만 담김
    const wc = BrowserWindow.fromWebContents(evt.sender).webContents
    const pdf = await wc.printToPDF({ printBackground: true, pageSize: 'A4' })

    // nodemailer는 필요할 때만 로드
    const nodemailer = require('nodemailer')
    const transporter = nodemailer.createTransport({
      host: 'smtp.gmail.com',
      port: 465,
      secure: true,
      auth: { user: p.from, pass },
    })

    const info = await transporter.sendMail({
      from: p.fromName ? `${p.fromName} <${p.from}>` : p.from,
      to: p.to,
      cc: p.cc || undefined,
      bcc: p.bcc || undefined,
      subject: p.subject,
      text: p.body || '',
      attachments: [{ filename: (p.filename || 'document') + '.pdf', content: pdf }],
    })
    return { ok: true, id: info.messageId }
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) }
  }
})

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
  autoUpdater.on('error', () => {})
  try {
    autoUpdater.checkForUpdatesAndNotify()
  } catch (e) {}
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
