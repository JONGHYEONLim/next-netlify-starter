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
// - 실시간 백업 1개(braumm-autobackup.json) + 날짜별 백업(backups/braumm-YYYY-MM-DD.json, 최근 30일)
const backupsDir = () => path.join(app.getPath('userData'), 'backups')

// 인쇄용 전체덮기 CSS: 흰 시트가 A4 전체를 덮게 하여 뒤 배경(베이지)이 절대 안 보이게 함
var PRINT_CSS =
  'html,body{background:#fff !important;margin:0 !important;padding:0 !important;}' +
  '.topbar,.panel,.overlay,.toolbar,.no-print,.single .h1,.single .sub,.single .card{display:none !important;}' +
  '.layout,.single,.preview-wrap{padding:0 !important;margin:0 !important;background:#fff !important;display:block !important;}' +
  '.sheet{width:210mm !important;min-height:297mm !important;padding:12mm !important;margin:0 !important;box-shadow:none !important;background:#fff !important;}' +
  '.cert{width:297mm !important;min-height:210mm !important;padding:10mm !important;margin:0 !important;box-shadow:none !important;background:#fff !important;}'

// PDF 생성 공용: 인쇄 시 앱 배경(베이지)이 새지 않도록 흰 시트로 전체를 덮은 뒤 캡처
async function makePDF(wc, opts) {
  let cssKey
  try {
    cssKey = await wc.insertCSS(PRINT_CSS)
  } catch (e) {}
  try {
    return await wc.printToPDF(opts)
  } finally {
    if (cssKey) {
      try { await wc.removeInsertedCSS(cssKey) } catch (e) {}
    }
  }
}
ipcMain.handle('data:save', (evt, data) => {
  try {
    const json = JSON.stringify(data)
    // 원자적 쓰기: 임시파일에 쓴 뒤 교체 (쓰기 도중 정전 등에도 원본 보존)
    const tmp = backupPath() + '.tmp'
    fs.writeFileSync(tmp, json)
    fs.renameSync(tmp, backupPath())
    // 날짜별 백업
    const dir = backupsDir()
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
    const d = new Date()
    const p2 = (n) => String(n).padStart(2, '0')
    const stamp = d.getFullYear() + '-' + p2(d.getMonth() + 1) + '-' + p2(d.getDate())
    fs.writeFileSync(path.join(dir, 'braumm-' + stamp + '.json'), json)
    // 최근 30개만 유지
    const files = fs.readdirSync(dir).filter((f) => f.startsWith('braumm-') && f.endsWith('.json')).sort()
    while (files.length > 30) {
      const f = files.shift()
      try { fs.unlinkSync(path.join(dir, f)) } catch (e) {}
    }
    return { ok: true }
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) }
  }
})
ipcMain.handle('data:load', () => {
  try {
    if (fs.existsSync(backupPath())) return JSON.parse(fs.readFileSync(backupPath(), 'utf8'))
    // 실시간 백업이 없으면 가장 최근 날짜별 백업에서 복구
    const dir = backupsDir()
    if (fs.existsSync(dir)) {
      const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json')).sort()
      if (files.length) return JSON.parse(fs.readFileSync(path.join(dir, files[files.length - 1]), 'utf8'))
    }
    return null
  } catch (e) {
    return null
  }
})
// ===== 벡터 PDF로 직접 저장 (Windows 인쇄 대화상자 우회 → 글자 벡터, 시트만 깔끔) =====
ipcMain.handle('pdf:save', async (evt, opts) => {
  try {
    opts = opts || {}
    const wc = BrowserWindow.fromWebContents(evt.sender).webContents
    const pdfOpts = {
      printBackground: true,
      pageSize: 'A4',
      generateTaggedPDF: true,
      margins: { top: 0, bottom: 0, left: 0, right: 0 },
    }
    if (opts.landscape) pdfOpts.landscape = true
    const pdf = await makePDF(wc, pdfOpts)
    const res = await dialog.showSaveDialog(BrowserWindow.fromWebContents(evt.sender), {
      title: 'PDF로 저장',
      defaultPath: (opts.filename || 'document') + '.pdf',
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    })
    if (res.canceled || !res.filePath) return { ok: false, canceled: true }
    fs.writeFileSync(res.filePath, pdf)
    shell.showItemInFolder(res.filePath)
    return { ok: true, path: res.filePath }
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) }
  }
})
ipcMain.handle('data:folder', () => {
  try {
    const dir = app.getPath('userData')
    shell.openPath(dir)
    return { ok: true, dir }
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) }
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
    const pdf = await makePDF(wc, {
      printBackground: true,
      pageSize: 'A4',
      margins: { top: 0, bottom: 0, left: 0, right: 0 },
      generateTaggedPDF: true,
    })

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
