const { contextBridge, ipcRenderer } = require('electron')

// 렌더러(도구 화면)에서 안전하게 호출할 수 있는 메일 기능만 노출한다.
// 비밀번호 원문은 렌더러로 절대 넘기지 않고, 메인 프로세스에서 암호화 보관/사용한다.
contextBridge.exposeInMainWorld('braumm', {
  isDesktop: true,
  hasMailPassword: () => ipcRenderer.invoke('mail:has'),
  saveMailPassword: (pw) => ipcRenderer.invoke('mail:save', pw),
  clearMailPassword: () => ipcRenderer.invoke('mail:clear'),
  sendMail: (payload) => ipcRenderer.invoke('mail:send', payload),
  saveBackup: (data) => ipcRenderer.invoke('data:save', data),
  loadBackup: () => ipcRenderer.invoke('data:load'),
  openBackupFolder: () => ipcRenderer.invoke('data:folder'),
  savePdf: (opts) => ipcRenderer.invoke('pdf:save', opts),
})
