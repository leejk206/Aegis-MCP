# Aegis-MCP (지능형 보안 AI 오케스트레이터)

Aegis-MCP는 Slack 기반 업무 질의 환경에서 **보안 정책(MAC)**, **데이터 보호(DP Filter)**, **LLM 오케스트레이션**을 결합해 안전한 AI 응답 파이프라인을 제공하는 백엔드 프로젝트입니다.

## 핵심 아키텍처

- **FastAPI**: Slack Events API 수신 및 서비스 엔드포인트 제공
- **SQLAlchemy ORM**: 사용자/문서 보안 메타데이터의 데이터 계층 추상화
- **SQLite**: 경량 로컬 DB(`aegis_mock.db`) 기반 실행 및 테스트
- **LLM 연동 구조**:
  - Intent Classification (의도 분류)
  - Query/Entity Extraction (검색 키워드 추출)
  - Grounded RAG Answering (허용 문서 기반 응답 생성)
  - 최종 Output Guardrail(PII/기밀 마스킹)

## 주요 기능

### 1) MAC (강제 접근 제어)
- 사용자 등급(Clearance)에 따라 문서 접근 범위를 통제합니다.
- `required_clearance <= user_clearance` 조건으로 조회 가능한 문서만 검색/요약 대상으로 허용합니다.

### 2) 데이터 보호 (DP Filter)
- 정규식 기반 PII 마스킹:
  - 휴대전화 번호 등 민감 정보 탐지 및 `[MASKED_PII]` 치환
- 기밀 키워드 필터링:
  - 민감 키워드를 `[MASKED_CONFIDENTIAL]`로 치환

### 3) AI 오케스트레이션
- LLM 기반 Intent Classification:
  - `GENERAL_CONVERSATION`, `DATA_RETRIEVAL`, `SECURITY_QUERY` 분기
- 안전한 RAG 파이프라인:
  - 접근 허용 문서만 Context로 합성
  - "문서 밖 내용 추측 금지" 프롬프트로 환각 최소화
- 모든 응답은 최종적으로 마스킹 단계를 거쳐 Slack으로 전송

## 프로젝트 구조

```text
app/
  api/
  core/
    config.py
    database.py
  db/
    init_db.py
  models/
    user.py
    document.py
  services/
    orchestrator.py
    mac_service.py
    intent_classifier.py
    dp_filter.py
tests/
  test_orchestrator.py
.github/workflows/ci.yml
```

## 로컬 실행 가이드

### 1) 의존성 설치

```bash
pip install -r requirements.txt
```

### 2) 환경변수 설정 (`.env`)

프로젝트 루트에 `.env` 파일을 만들고 아래 예시를 참고해 설정합니다.

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
APP_PORT=8000
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

### 3) 서버 실행

```bash
uvicorn app.main:app --reload
```

## 테스트 실행 방법

### 단위 테스트

```bash
pytest tests/ -v
```

- `tests/test_orchestrator.py`는 인메모리 SQLite(`sqlite:///:memory:`)를 사용하여
  실제 운영 DB 파일 오염 없이 MAC 허용/차단 시나리오를 검증합니다.

## CI 파이프라인

- 경로: `.github/workflows/ci.yml`
- 트리거:
  - `main` 브랜치 `push`
  - `main` 대상 `pull_request`
- 실행 내용:
  - Python 3.10 / 3.11 환경 구성
  - `pip install -r requirements.txt`
  - `pytest tests/ -v`

> PR 머지 차단은 GitHub 저장소의 Branch Protection Rules에서 해당 CI 체크를 Required Status Check로 지정해야 적용됩니다.
