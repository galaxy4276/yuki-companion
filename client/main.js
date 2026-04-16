const { app, BrowserWindow, ipcMain, screen, Tray, Menu, nativeImage, globalShortcut, desktopCapturer } = require('electron')
const path = require('path')

const SERVER_URL = 'http://125.242.221.180:8002'
const WS_URL    = 'ws://125.242.221.180:8002/ws'

let mainWin = null
let chatWin = null
let tray    = null

// ─── 메인 오버레이 윈도우 (투명 캐릭터) ─────────────────────────
function createOverlay() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize

  mainWin = new BrowserWindow({
    width:  400,
    height: 600,
    x: width - 420,      // 우측 하단
    y: height - 620,
    transparent:  true,
    frame:        false,
    alwaysOnTop:  true,
    hasShadow:    false,
    resizable:    false,
    skipTaskbar:  true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
    },
  })

  mainWin.loadFile(path.join(__dirname, 'renderer', 'overlay.html'))
  mainWin.webContents.openDevTools({ mode: 'detach' })
  mainWin.setAlwaysOnTop(true, 'screen-saver')  // 최상단 레벨
  mainWin.setVisibleOnAllWorkspaces(true)         // 모든 데스크톱에 표시

  // 투명 영역 클릭 통과
  mainWin.setIgnoreMouseEvents(true, { forward: true })

  // 캐릭터 영역에 마우스가 올라오면 클릭 통과 해제
  ipcMain.on('set-ignore-mouse', (_, ignore) => {
    mainWin.setIgnoreMouseEvents(ignore, { forward: true })
  })

  // 드래그로 창 이동
  ipcMain.on('move-window', (_, { dx, dy }) => {
    const [x, y] = mainWin.getPosition()
    mainWin.setPosition(x + dx, y + dy)
  })
}

// ─── 채팅 윈도우 (별도 패널) ─────────────────────────────────────
function createChatWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize

  chatWin = new BrowserWindow({
    width:  360,
    height: 500,
    x: width - 800,
    y: height - 540,
    frame:       false,
    transparent: false,
    alwaysOnTop: true,
    show:        false,  // 처음엔 숨김
    skipTaskbar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
    },
  })

  chatWin.loadFile(path.join(__dirname, 'renderer', 'chat.html'))
}

// ─── 트레이 아이콘 ───────────────────────────────────────────────
function createTray() {
  const icon = nativeImage.createFromPath(path.join(__dirname, 'assets', 'tray.png'))
  tray = new Tray(icon)
  tray.setToolTip('유키 AI 동반자')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '채팅 창 열기',  click: () => chatWin?.show() },
    { label: '채팅 창 닫기',  click: () => chatWin?.hide() },
    { type: 'separator' },
    { label: '캐릭터 숨기기', click: () => mainWin?.hide() },
    { label: '캐릭터 보이기', click: () => mainWin?.show() },
    { type: 'separator' },
    { label: '종료',          click: () => app.quit() },
  ]))
  tray.on('click', () => chatWin?.isVisible() ? chatWin?.hide() : chatWin?.show())
}

// ─── IPC: 오버레이 ↔ 채팅 메시지 중계 ───────────────────────────
ipcMain.on('show-speech-bubble', (_, text) => {
  mainWin?.webContents.send('speech-bubble', text)
})

ipcMain.on('play-audio', (_, b64) => {
  mainWin?.webContents.send('play-audio', b64)
  chatWin?.webContents.send('play-audio', b64)
})

ipcMain.on('toggle-chat', () => {
  chatWin?.isVisible() ? chatWin?.hide() : chatWin?.show()
})

ipcMain.on('hide-chat', () => chatWin?.hide())

ipcMain.on('avatar-emotion', (_, payload) => {
  mainWin?.webContents.send('avatar-emotion', payload)
})

ipcMain.handle('get-config', () => ({ WS_URL, SERVER_URL }))

ipcMain.handle('capture-screen', async () => {
  const sources = await desktopCapturer.getSources({ types: ['screen'], thumbnailSize: { width: 1280, height: 800 } })
  if (sources.length === 0) return null
  const thumb = sources[0].thumbnail.toJPEG(70)
  return thumb.toString('base64')
})

// ─── 앱 시작 ─────────────────────────────────────────────────────
app.whenReady().then(() => {
  createOverlay()
  createChatWindow()
  createTray()
  globalShortcut.register('Alt+Shift+Space', () => {
    chatWin?.show()
    chatWin?.webContents.send('global-ptt-toggle')
  })
  globalShortcut.register('Alt+Shift+S', async () => {
    chatWin?.webContents.send('screen-capture-trigger')
  })
})

app.on('will-quit', () => { globalShortcut.unregisterAll() })

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
