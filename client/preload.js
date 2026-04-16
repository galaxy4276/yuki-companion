const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('yukiAPI', {
  // 설정값 가져오기
  getConfig: () => ipcRenderer.invoke('get-config'),

  // 마우스 이벤트 무시 설정
  setIgnoreMouse: (ignore) => ipcRenderer.send('set-ignore-mouse', ignore),

  // 드래그로 창 이동
  moveWindow: (dx, dy) => ipcRenderer.send('move-window', { dx, dy }),

  // 채팅 창 토글
  toggleChat: () => ipcRenderer.send('toggle-chat'),

  // 오버레이 이벤트 수신
  onSpeechBubble: (fn) => ipcRenderer.on('speech-bubble', (_, text) => fn(text)),
  onPlayAudio:    (fn) => ipcRenderer.on('play-audio', (_, b64) => fn(b64)),

  // 채팅 창 → 메인으로 오디오 중계
  relayAudio: (b64) => ipcRenderer.send('play-audio', b64),
  showSpeechBubble: (text) => ipcRenderer.send('show-speech-bubble', text),
  hideChat: () => ipcRenderer.send('hide-chat'),
  onError: (fn) => ipcRenderer.on('error', (_, payload) => fn(payload)),
  onAvatarEmotion: (fn) => ipcRenderer.on('avatar-emotion', (_, payload) => fn(payload)),
  emitAvatarEmotion: (payload) => ipcRenderer.send('avatar-emotion', payload),
  onGlobalPttToggle: (fn) => ipcRenderer.on('global-ptt-toggle', () => fn()),
})
