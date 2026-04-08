# 유키 Electron 앱 빌드 가이드

## MacOS에서 실행 (개발 모드)

```bash
# 1. 이 디렉토리를 MacOS로 복사
scp -r deveungu@125.242.221.180:/home/deveungu/vtuber-client ~/yuki-companion

# 2. 패키지 설치
cd ~/yuki-companion
npm install

# 3. 실행
npm start
```

## VRM 모델 넣기

`assets/model.vrm` 경로에 VRM 파일을 넣으면 3D 캐릭터가 표시됩니다.
없으면 이모지 폴백 아바타로 자동 전환됩니다.

### 무료 VRM 모델 구하는 곳
- https://hub.vroid.com (VRoid Hub — 무료 모델 다수)
- VRoid Studio로 직접 제작 후 VRM 내보내기

## 앱 빌드 (배포용 .dmg)

```bash
npm run build:mac
# dist/ 폴더에 .dmg 생성
```

## 구조

```
overlay 창 (투명, alwaysOnTop)
  └── VRM 캐릭터 (Three.js + three-vrm)
  └── 말풍선
  └── 드래그로 이동 가능

chat 창 (트레이 클릭 또는 💬 버튼으로 열기)
  └── 채팅 UI
  └── PTT 음성 입력
  └── WebSocket → 서버 125.242.221.180:8002
```

## 서버 주소 변경

`main.js` 상단:
```js
const SERVER_URL = 'http://125.242.221.180:8002'
const WS_URL     = 'ws://125.242.221.180:8002/ws'
```
