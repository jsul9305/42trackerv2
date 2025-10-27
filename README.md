# 42Tracker: 마라톤 라이브 기록 추적기

**42Tracker**는 국내 여러 마라톤 기록 측정 사이트의 데이터를 크롤링하여, 지정된 참가자들의 스플릿(구간 기록)을 실시간으로 추적하고 예상 기록을 예측해주는 웹 애플리ケーション입니다.

## ✨ 주요 기능

- **실시간 기록 추적**: 여러 참가자의 기록을 하나의 화면에서 주기적으로 자동 갱신하며 모니터링합니다.
- **다중 플랫폼 지원**: `smartchip.co.kr`, `spct.co.kr`, `myresult.co.kr` 등 여러 기록 측정 사이트를 지원합니다.
- **기록 예측**: 현재 페이스를 기반으로 다음 구간 및 최종 완주 예상 시각(ETA), 예상 넷타임(Net Time)을 계산합니다.
- **간편한 관리**: 웹 기반 관리자 페이지에서 대회 정보를 등록/수정하고, 추적할 참가자를 쉽게 추가/삭제할 수 있습니다.
- **반응형 웹 UI**: 데스크톱과 모바일 환경 모두에 최적화된 화면을 제공하여 어디서든 편리하게 사용할 수 있습니다.
- **개인 기록 아카이브**: 완료된 대회의 기록을 모아보고, 기록증 이미지를 확인할 수 있는 별도 페이지를 제공합니다.

## ⚙️ 기술 스택

- **Backend**: Python, Flask
- **Crawling**: Playwright (동적 페이지), BeautifulSoup (정적 페이지)
- **Database**: SQLite
- **Frontend**: Vanilla JavaScript, HTML, CSS

## 🚀 시작하기

### 1. 설치

```bash
# 1. 저장소 클론
git clone https://your-repository-url/42tracker.git
cd 42tracker

# 2. 가상환경 생성 및 활성화
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. (선택) Playwright 브라우저 설치
# MyResult.co.kr과 같이 동적 크롤링이 필요한 사이트를 지원하려면 필요합니다.
playwright install
```

### 2. 실행

**1. 웹 애플리케이션 실행**

```bash
python run_webapp.py
```

- 웹 앱이 실행되면 `http://127.0.0.1:5000` (기본값) 주소로 접속할 수 있습니다.
- **사용자 화면**: `http://127.0.0.1:5000`
- **관리자 화면**: `http://127.0.0.1:5000/admin`

**2. 백그라운드 크롤러 실행 (옵션)**

`run_crawler.py`는 등록된 모든 활성 참가자의 기록을 주기적으로 크롤링하여 데이터베이스를 업데이트하는 독립적인 스크립트입니다. 웹 앱과 별도로 실행할 수 있습니다.

```bash
python run_crawler.py
```

## 📝 사용 방법

1.  **대회 등록**:
    - 관리자 페이지 (`/admin`)에 접속합니다.
    - '새 대회 추가' 폼에 대회 정보(대회명, 총거리, 크롤링 URL 템플릿 등)를 입력하고 추가합니다.
    - **URL 템플릿 예시**:
      - **Smartchip**: `https://smartchip.co.kr/return_data_livephoto.asp?nameorbibno={nameorbibno}&usedata={usedata}`
      - **SPCT**: `http://time.spct.co.kr/m2.php?{usedata}&BIB_NO={nameorbibno}`
      - **MyResult**: `https://myresult.co.kr/{usedata}/{nameorbibno}`

2.  **참가자 등록**:
    - 사용자 화면 (`/race/<대회ID>`) 또는 관리자 페이지에서 추적할 참가자를 추가합니다.
    - '성명(표시용)'과 '배번 또는 이름'을 입력하여 등록합니다.
    - 관리자 페이지에서는 엑셀 파일로 참가자를 일괄 업로드할 수도 있습니다.

3.  **기록 확인**:
    - 사용자 화면에서 등록된 참가자들의 실시간 기록, 현재 위치, 예상 기록 등을 확인할 수 있습니다.
    - 페이지는 설정된 주기에 따라 자동으로 새로고침됩니다.

4.  **전체 기록 보기**:
    - `/records` 페이지에서 모든 참가자의 최종 기록을 모아볼 수 있습니다.

## 📂 프로젝트 구조

```
smartchip_live/
├── config/
│   ├── __init__.py
│   ├── settings.py          # 설정 (DB 경로, 포트, 환경변수 등)
│   └── constants.py         # 상수 (거리, 정규식 등)
│
├── core/
│   ├── __init__.py
│   ├── database.py          # DB 연결, 스키마, 마이그레이션
│   ├── models.py            # 데이터 모델 (Marathon, Participant, Split 등)
│   └── exceptions.py        # 커스텀 예외
│
├── parsers/
│   ├── __init__.py
│   ├── base.py              # 파서 베이스 클래스
│   ├── smartchip.py         # 스마트칩 전용 파서
│   ├── spct.py              # SPCT 전용 파서
│   ├── myresult.py          # MyResult 전용 파서
│   └── utils.py             # 파싱 유틸 (시간 변환, 거리 추출 등)
│
├── crawler/
│   ├── __init__.py
│   ├── engine.py            # 크롤링 엔진 (메인 루프)
│   ├── fetcher.py           # HTTP/브라우저 요청 처리
│   ├── worker.py            # MyResult 워커 등 특수 워커
│   └── scheduler.py         # 스케줄링 로직
│
├── webapp/
│   ├── __init__.py
│   ├── app.py               # Flask 앱 생성
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── api.py           # REST API 엔드포인트
│   │   ├── pages.py         # 페이지 라우트
│   │   └── static_routes.py # 정적 파일 서빙
│   └── services/
│       ├── __init__.py
│       ├── marathon.py      # 마라톤 비즈니스 로직
│       ├── participant.py   # 참가자 비즈니스 로직
│       └── prediction.py    # 예측/분석 로직
│
├── utils/
│   ├── __init__.py
│   ├── time_utils.py        # 시간 관련 유틸
│   ├── distance_utils.py    # 거리 계산 유틸
│   ├── file_utils.py        # 파일 저장 유틸
│   └── validation.py        # 검증 유틸
│
├── config/                  # 설정 (DB 경로, 상수 등)
├── core/                    # DB, 데이터 모델, 공통 예외
├── parsers/                 # 각 기록 사이트별 HTML/JSON 파서
├── crawler/                 # 크롤링 엔진 및 워커
├── webapp/                  # Flask 웹 애플리ケーション (라우트, 서비스 로직)
│   ├── routes/              # API 및 페이지 라우트
│   └── services/            # 비즈니스 로직
├── utils/                   # 시간, 거리, 파일 등 각종 유틸리티
├── templates/               # HTML 템플릿
│   ├── index.html
│   ├── admin.html
│   └── records.html
│
├── static/                  # 정적 파일
│   └── certs/
│
├── tests/                   # 테스트
│   ├── __init__.py
│   ├── test_parsers.py
│   ├── test_crawler.py
│   └── test_api.py
│
├── run_crawler.py           # 크롤러 실행 스크립트
├── static/                  # 정적 파일 (CSS, JS, 이미지)
├── tests/                   # 테스트 코드
├── run_crawler.py           # 크롤러 실행 스크...
├── run_webapp.py            # 웹앱 실행 스크립트
├── requirements.txt
└── README.md
```