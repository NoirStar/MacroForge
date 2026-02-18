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
| **이미지 매칭 매크로** | OpenCV 기반 템플릿 매칭으로 화면 요소 자동 인식 및 클릭 |
| **좌표 기반 매크로** | 직접 좌표를 지정하여 탭/스와이프 자동화 |
| **조건부 대기** | 특정 이미지가 나타날 때까지 대기 후 동작 |
| **조건 분기** | 이미지 유무에 따라 다른 스텝으로 분기 |
| **매크로 큐** | 여러 매크로를 순서대로 등록하고 순차 실행 |
| **백그라운드 액션** | 메인 매크로와 독립적으로 동작하는 주기적 반복 작업 |
| **다중 에뮬레이터 지원** | BlueStacks, LDPlayer, Nox, MuMu 등 ADB 지원 에뮬레이터 범용 |
| **휴먼라이저** | 클릭 좌표 오프셋, 딜레이 랜덤화로 매크로 탐지 회피 |
| **실시간 미리보기** | 에뮬레이터 화면을 실시간으로 확인 |
| **매크로 저장/로드** | YAML 기반 매크로 스크립트 저장 및 공유 |

---

## 🚀 설치 가이드 (처음부터 따라하기)

> **컴퓨터에 Python이 없어도 괜찮습니다!** 아래 순서대로 따라하면 됩니다.

### 1단계: Python 설치

1. [Python 공식 다운로드 페이지](https://www.python.org/downloads/) 에 접속합니다.
2. **Download Python 3.1x.x** 버튼을 클릭합니다. (3.10 이상이면 아무거나 OK)
3. 다운로드된 설치 파일을 실행합니다.
4. ⚠️ **중요!** 첫 화면 하단의 **"Add python.exe to PATH"** 체크박스를 **반드시 체크**하세요.
5. **Install Now**를 클릭하여 설치를 완료합니다.

> ✅ 설치 확인: `Win + R` → `cmd` 입력 → 열린 창에 `python --version` 입력 → 버전이 표시되면 성공!

### 2단계: MacroForge 다운로드

**방법 A: Git 사용 (Git이 설치되어 있는 경우)**
```bash
git clone https://github.com/NoirStar/MacroForge.git
```

**방법 B: ZIP 다운로드 (Git 없이)**
1. [MacroForge GitHub 페이지](https://github.com/NoirStar/MacroForge) 에 접속
2. 초록색 **Code** 버튼 클릭 → **Download ZIP** 클릭
3. 다운로드된 ZIP 파일을 원하는 폴더에 압축 해제

### 3단계: 필요한 라이브러리 설치

1. 압축 해제한 폴더를 열고, 주소창에 `cmd`를 입력하여 명령 프롬프트를 엽니다.
2. 아래 명령어를 입력합니다:

```bash
pip install -r requirements.txt
```

> 이 명령은 MacroForge에 필요한 모든 라이브러리를 자동으로 설치합니다.

### 4단계: 실행

```bash
python main.py
```

또는 폴더 안의 **`MacroForge.bat`** 파일을 더블클릭하면 바로 실행됩니다.

---

## 🎮 사용법 (퀵스타트)

### 1. 에뮬레이터 연결

1. 사용하는 에뮬레이터를 실행합니다.
2. MacroForge 상단 바에서 **에뮬레이터 종류를 선택**합니다 (BlueStacks, LDPlayer 등).
3. **연결** 버튼을 클릭합니다.
4. `● 연결됨`으로 바뀌면 성공! 연결 실패 시 아래 ADB 설정 표를 참고하세요.

### 2. 매크로 만들기

1. **매크로 빌더** 탭에서 **새 스크립트** 버튼을 클릭합니다.
2. **스텝 추가** 버튼으로 원하는 동작을 추가합니다:
   - **이미지 클릭**: 화면에서 특정 이미지를 찾아서 클릭
   - **좌표 탭**: 지정한 좌표를 직접 클릭
   - **대기**: 일정 시간 대기
   - **이미지 대기**: 특정 이미지가 나타날 때까지 대기
   - **조건 분기**: 이미지 유무에 따라 다른 동작 실행
3. 스텝을 원하는 순서로 정리한 뒤 **저장** 버튼을 클릭합니다.

### 3. 매크로 실행

- **단일 실행**: 상단 바의 **시작** 버튼 클릭
- **큐 실행**: **매크로 큐** 탭에서 여러 매크로를 추가하고 **큐 실행** 클릭

### 4. 백그라운드 액션 (선택)

매크로 실행과 별개로, 일정 주기마다 반복하는 동작(예: 체력 물약 사용)을 설정할 수 있습니다.

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

## ❓ 자주 묻는 질문

<details>
<summary><b>Q: <code>pip</code>를 실행하면 "'pip'은(는) 내부 또는 외부 명령...이 아닙니다" 라고 나옵니다</b></summary>

Python 설치 시 **"Add python.exe to PATH"**를 체크하지 않은 경우입니다.
- Python을 다시 설치하면서 반드시 체크해주세요.
- 또는 명령 프롬프트에서 `python -m pip install -r requirements.txt`로 실행하세요.
</details>

<details>
<summary><b>Q: ADB 연결이 안됩니다</b></summary>

1. 에뮬레이터에서 ADB 옵션이 활성화되어 있는지 확인하세요 (위 표 참고).
2. 에뮬레이터를 먼저 완전히 실행한 뒤 연결하세요.
3. 다른 프로그램이 같은 포트를 사용 중일 수 있습니다 — 에뮬레이터를 재시작하세요.
4. 방화벽/백신이 ADB 통신을 차단하고 있을 수 있습니다.
</details>

<details>
<summary><b>Q: 매크로가 화면을 인식하지 못합니다</b></summary>

1. 템플릿 이미지의 해상도가 에뮬레이터 해상도와 같은지 확인하세요.
2. `config.yaml`에서 `confidence_threshold` 값을 낮춰보세요 (예: 0.80).
3. **미리보기**를 켜서 현재 화면이 정상적으로 캡처되는지 확인하세요.
</details>

<details>
<summary><b>Q: 실행하면 콘솔(검은 창)이 나타납니다</b></summary>

`MacroForge.bat` 파일로 실행하면 콘솔 없이 실행됩니다.
직접 실행하려면 `python main.py` 대신 `pythonw main.py`를 사용하세요.
</details>

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
│   ├── ui/                  # PySide6 UI (메인 윈도우, 매크로 빌더, 큐, 로그)
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
