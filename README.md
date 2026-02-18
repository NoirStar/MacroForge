<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/PySide6-Qt-41CD52?style=for-the-badge&logo=qt&logoColor=white"/>
  <img src="https://img.shields.io/badge/ADB-Android-3DDC84?style=for-the-badge&logo=android&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge"/>
</p>

# ⚒️ MacroForge

**ADB 기반 모바일 게임 매크로 자동화 도구**

Android 에뮬레이터(BlueStacks, LDPlayer, Nox, MuMu) 또는 실제 디바이스에서 동작하는 범용 게임 매크로 빌더입니다.
이미지 인식과 ADB 명령을 활용하여, 에뮬레이터 창이 가려져 있거나 최소화 상태에서도 매크로가 정상 동작합니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| 🖼️ **이미지 매칭 매크로** | OpenCV 기반 템플릿 매칭으로 화면 요소 자동 인식 및 클릭 |
| 📐 **좌표 기반 매크로** | 직접 좌표를 지정하여 탭/스와이프 자동화 |
| ⏳ **조건부 대기** | 특정 이미지가 나타날 때까지 대기 후 동작 |
| 🔀 **조건 분기** | 이미지 유무에 따라 다른 스텝으로 분기 |
| 🔁 **백그라운드 액션** | 메인 매크로와 독립적으로 동작하는 주기적 반복 작업 |
| 🎯 **다중 에뮬레이터 지원** | BlueStacks, LDPlayer, Nox, MuMu 등 ADB 지원 에뮬레이터 범용 |
| 🤖 **휴먼라이저** | 클릭 좌표 오프셋, 딜레이 랜덤화로 매크로 탐지 회피 |
| 🖥️ **실시간 미리보기** | 에뮬레이터 화면을 실시간으로 확인 |
| 💾 **매크로 저장/로드** | YAML 기반 매크로 스크립트 저장 및 공유 |

---

## 🚀 시작하기

### 요구 사항

- **Python 3.10+**
- **Android 에뮬레이터** (ADB 활성화 필요) 또는 실제 Android 디바이스

### 설치

```bash
# 저장소 클론
git clone https://github.com/<your-username>/MacroForge.git
cd MacroForge

# 의존성 설치
pip install -r requirements.txt
```

### 실행

```bash
python main.py
```

또는 Windows에서 `MacroForge.bat` 더블클릭

---

## 🔌 에뮬레이터별 ADB 설정

| 에뮬레이터 | ADB 설정 위치 | 기본 포트 |
|-----------|-------------|----------|
| **BlueStacks** | 설정 → 고급 → Android 디버그 브리지(ADB) 활성화 | `5555` |
| **LDPlayer** | 설정 → 기타 → ADB 디버그 열기 | `5555` |
| **Nox Player** | 설정 → 일반 → ROOT 켜기 | `62001` |
| **MuMu Player** | 설정 → 기타 → ADB 연결 열기 | `7555` |
| **실제 디바이스** | 개발자 옵션 → USB 디버깅 활성화 | 자동 감지 |

> `config.yaml`의 `adb.port` 값을 에뮬레이터에 맞게 변경하세요.

---

## 📁 프로젝트 구조

```
MacroForge/
├── main.py                  # 엔트리포인트
├── config.yaml              # 전역 설정
├── requirements.txt         # Python 의존성
├── MacroForge.bat           # Windows 런처
├── assets/templates/        # 이미지 매칭 템플릿
├── saved_macros/            # 저장된 매크로 스크립트
├── src/
│   ├── core/                # ADB, 화면 캡처, 이미지 매칭, 입력 시뮬레이션
│   ├── macros/              # 매크로 데이터 모델, 스크립트 엔진
│   ├── ui/                  # PySide6 UI (메인 윈도우, 매크로 빌더, 로그)
│   └── utils/               # 설정 관리, 로거, 휴먼라이저
└── tools/                   # 자동 다운로드되는 ADB (platform-tools)
```

---

## ⚙️ 설정 (`config.yaml`)

```yaml
adb:
  adb_path: "auto"          # auto = ADB 자동 탐색/다운로드
  host: "127.0.0.1"
  port: 5555                # 에뮬레이터에 맞게 변경

image_matching:
  confidence_threshold: 0.85 # 이미지 매칭 신뢰도 (0.0~1.0)
  use_grayscale: true        # 그레이스케일 매칭 (성능 향상)

humanizer:
  click_offset_range: 5      # 클릭 좌표 랜덤 오프셋 (px)
  min_delay: 0.3             # 클릭 간 최소 딜레이 (초)
  max_delay: 1.2             # 클릭 간 최대 딜레이 (초)
```

---

## 🛠️ 기술 스택

- **PySide6** — Qt 기반 모던 다크 UI
- **OpenCV** — 멀티스케일 이미지 템플릿 매칭
- **ADB (Android Debug Bridge)** — 에뮬레이터/디바이스 제어
- **qtawesome** — Material Design 아이콘
- **PyYAML** — 매크로 스크립트 직렬화

---

## 📜 라이선스

MIT License — 자유롭게 사용, 수정, 배포하세요.
