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
├── run_webapp.py            # 웹앱 실행 스크립트
├── requirements.txt
└── README.md