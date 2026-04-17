# LectoMLV LLM

강의자료 기반 **Grounded RAG** 질의응답 서버입니다.

업로드된 STT 세그먼트와 슬라이드 텍스트를 FAISS 벡터 인덱스로 관리하고,
사용자 질문에 대해 **출처 인용이 포함된 답변**을 생성합니다.
모든 문장에 `[S#]` 인라인 인용을 강제하며, Faithfulness 검증까지 수행합니다.

## 주요 기능

- **Grounded RAG** — 출처 기반 답변 생성, 모든 문장에 `[S#]` 인용 강제
- **Faithfulness 검증** — LLM이 생성한 답변을 다시 검증하여 근거 없는 문장 탐지
- **구간 검색 / 요약 / 추천** — 3가지 쿼리 유형 지원
- **외부 JSON 자동 변환** — PPTX 슬라이드·영상 자막 등 다양한 형식 자동 감지 및 임포트
- **비동기 처리** — Celery Worker가 LLM 추론과 벡터 인덱싱을 백그라운드 수행
- **데모 대시보드** — 브라우저에서 바로 쿼리·업로드·결과 확인 가능
- **모델 확장 가능** — Ollama 지원 모델을 설정만으로 추가 가능

## 아키텍처

```
Client (Browser / curl / Python)
    │
    ▼
┌────────┐     ┌─────────────────┐
│ Nginx  │────▶│ Django (DRF)    │  API + Demo UI
│ :8777  │     │ Gunicorn :8000  │
└────────┘     └────────┬────────┘
                        │
                  ┌─────┴─────┐
                  │   Redis   │  Celery Broker
                  └─────┬─────┘
                        │
               ┌────────┴────────┐
               │  Celery Worker  │  LLM 추론 + FAISS 인덱싱
               └────────┬────────┘
                        │
            ┌───────────┼───────────┐
            │           │           │
     ┌──────┴──────┐ ┌──┴───┐ ┌────┴─────┐
     │   Ollama    │ │FAISS │ │PostgreSQL│
     │ (LLM, GPU) │ │(벡터)│ │ (메인 DB)│
     └─────────────┘ └──────┘ └──────────┘
```

## 빠른 시작

```bash
# 1. 클론
git clone https://github.com/SCH-AICS/lectomlv-llm.git
cd lectomlv-llm

# 2. 환경변수
cp docker/.env.example docker/.env
# docker/.env에서 DJANGO_SECRET_KEY 등 수정

# 3. 빌드 & 실행
docker compose up -d --build

# 4. DB 마이그레이션
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# 5. Ollama 모델 다운로드 확인 (최초 실행 시 자동, 수동도 가능)
docker compose exec ollama ollama pull qwen2.5:14b

# 6. 접속
open http://localhost:8777/          # 데모 대시보드
open http://localhost:8777/api/      # API Root (Browsable UI)
```

> 최초 실행 시 Ollama가 모델을 자동 다운로드합니다 (10분+ 소요).
> 진행 확인: `docker compose logs -f ollama_init`

## 기본 워크플로우

```
1. 강의 데이터 임포트   POST /api/lectures/bulk-import/   → 벡터 인덱싱 자동 시작
2. 인덱싱 완료 확인     GET  /api/llm/tasks/{task_id}/
3. LLM 쿼리 전송       POST /api/llm/query/              → 비동기 처리 시작
4. 결과 조회            GET  /api/llm/query/{id}/          → Grounded 답변 + 출처
```

## LLM 모델 사양

Ollama를 통해 양자화된(Q4) 모델을 사용합니다.
권장 GPU: **NVIDIA RTX 3090 (24GB VRAM)** 이상

| 모델 | 키 | 파라미터 | 양자화 | VRAM 사용량 | 컨텍스트 길이 | 용도 |
|------|-----|---------|--------|------------|-------------|------|
| Qwen 2.5 14B | `qwen` | 14.7B | Q4_K_M | ~15 GB | 32K tokens | 기본 모델, 한국어 성능 우수 |
| MiniLM-L12 (임베딩) | — | 118M | FP32 | ~0.5 GB (CPU) | 512 tokens | 벡터 임베딩 |

> Ollama는 요청 시 모델을 GPU에 로드하고, 유휴 시 자동 언로드합니다.
> `docker/.env`의 `OLLAMA_QWEN_MODEL`을 변경하면 다른 Ollama 모델로 교체할 수 있습니다.

## API 엔드포인트

### 강의 데이터 관리

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/lectures/` | 강의 목록 |
| POST | `/api/lectures/` | 강의 생성 |
| GET | `/api/lectures/{id}/` | 강의 상세 (세그먼트 포함) |
| PUT | `/api/lectures/{id}/` | 강의 수정 |
| DELETE | `/api/lectures/{id}/` | 강의 삭제 |
| GET | `/api/lectures/{id}/segments/` | 구간 목록 |
| POST | `/api/lectures/bulk-import/` | STT 데이터 일괄 임포트 |

### LLM 쿼리

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/llm/query/` | LLM 쿼리 생성 (비동기) |
| GET | `/api/llm/query/{id}/` | 쿼리 결과 조회 |
| GET | `/api/llm/queries/` | 쿼리 이력 |
| GET | `/api/llm/tasks/{task_id}/` | 태스크 상태 확인 |
| GET | `/api/llm/models/` | 사용 가능 모델 목록 |

## 외부에서 배치 업로드

서버가 아닌 다른 컴퓨터에서 강의 데이터를 한꺼번에 업로드할 수 있습니다.

### curl로 업로드

```bash
SERVER="http://서버IP:8777"

# 내부 형식 (직접 지정)
curl -s -X POST "$SERVER/api/lectures/bulk-import/" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "인공지능과 기계학습 1강",
    "source_file": "p1_AI_ML_intro.pdf",
    "segments": [
      {"start_time": "00:01", "end_time": "01:36", "transcript": "오늘 수업은..."},
      {"start_time": "01:37", "end_time": "04:22", "transcript": "인공지능이라는 거는..."}
    ]
  }' | python3 -m json.tool

# 외부 형식 (자동 변환 — PPTX 슬라이드 + 영상 자막 혼합 JSON)
curl -s -X POST "$SERVER/api/lectures/bulk-import/" \
  -H "Content-Type: application/json" \
  -d @CAD기초.json | python3 -m json.tool
```

### Python 스크립트로 업로드

```python
import requests, time
from pathlib import Path

SERVER = "http://서버IP:8777"

# JSON 파일 일괄 업로드
for f in sorted(Path("./data").glob("*.json")):
    print(f"Uploading: {f.name}")
    data = f.read_text(encoding="utf-8")
    resp = requests.post(
        f"{SERVER}/api/lectures/bulk-import/",
        headers={"Content-Type": "application/json"},
        data=data,
    )
    result = resp.json()
    if resp.ok:
        count = result.get("success", result.get("segments_count", "?"))
        print(f"  OK — {count}")
    else:
        print(f"  FAIL — {result}")

# 쿼리 + 폴링
resp = requests.post(f"{SERVER}/api/llm/query/", json={
    "query_text": "인공지능과 머신러닝의 차이가 뭐야?",
    "query_type": "search",
    "model_name": "qwen",
})
query_id = resp.json()["query_id"]

while True:
    r = requests.get(f"{SERVER}/api/llm/query/{query_id}/").json()
    print(f"  status: {r['status']}")
    if r["status"] in ("completed", "failed"):
        break
    time.sleep(3)

print(r["result_text"])
```

> 외부 JSON(PPTX slides + video segments, course 래퍼 등)은 서버에서 자동 감지·변환합니다.

## 기술 스택

| 영역 | 기술 |
|------|------|
| API 서버 | Django 5 + Django REST Framework |
| 비동기 작업 | Celery + Redis |
| LLM 서빙 | Ollama (NVIDIA GPU) |
| 벡터 검색 | FAISS (CPU) + sentence-transformers |
| 데이터베이스 | PostgreSQL 16 |
| 리버스 프록시 | Nginx |
| 컨테이너 | Docker Compose (NVIDIA runtime) |

## 프로젝트 구조

```
lectomlv-llm/
├── apps/
│   ├── lectures/                   # 강의 데이터 관리
│   │   ├── models.py               # Lecture, LectureSegment
│   │   ├── serializers.py
│   │   ├── views.py                # CRUD + BulkImport
│   │   ├── converter.py            # 외부 JSON → 내부 형식 변환
│   │   ├── tasks.py                # FAISS 인덱싱 Celery 태스크
│   │   └── urls.py
│   ├── llm/                        # LLM 서비스
│   │   ├── models.py               # LLMQuery
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── tasks.py                # LLM 추론 Celery 태스크
│   │   ├── urls.py
│   │   └── services/
│   │       ├── ollama_client.py    # Ollama REST API 클라이언트
│   │       ├── embedding_service.py # FAISS 벡터 임베딩 (싱글턴)
│   │       └── rag_service.py      # Grounded RAG 파이프라인
│   └── demo/                       # 데모 대시보드
│       ├── views.py
│       ├── urls.py
│       ├── templates/demo/index.html
│       └── management/commands/
│           ├── seed_lectures.py    # 더미 데이터 생성
│           └── index_lectures.py   # FAISS 인덱싱 실행
├── config/                         # Django / Celery 설정
│   ├── settings.py
│   ├── celery.py
│   ├── urls.py
│   └── wsgi.py
├── docker/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── nginx.conf
│   ├── requirements.txt
│   └── .env.example
├── docker-compose.yml
├── manage.py
└── README.md
```

## 트러블슈팅

### Ollama 모델이 아직 준비 안 됨

```bash
docker compose logs ollama_init
docker compose exec ollama ollama pull qwen2.5:14b
docker compose exec ollama ollama list
```

### 쿼리가 계속 pending 상태

```bash
docker compose logs -f celery_worker
docker compose restart celery_worker
```

### GPU 관련 오류

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
# GPU 없이 실행하려면 docker-compose.yml에서 ollama의 deploy 섹션 제거
```

### DB 마이그레이션 문제

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py showmigrations
```

### 전체 초기화 후 재시작

```bash
docker compose down -v
docker compose up -d --build
```

## 라이선스

이 저장소의 **SCH-AICS가 작성한 코드**는 [LICENSE](LICENSE)에 따릅니다.

- **허용된 기업·기관(Authorized Licensee)**: SCH-AICS가 서면(계약·공식 이메일 등)으로 지정한 경우, 약정된 범위에서 **별도 사용료 없이** 사용할 수 있습니다.
- **그 외**: 상업적·기관 이용을 포함해 사용하려면 **별도의 유료·사용 계약**이 필요합니다.

**라이선스·제휴 문의**: 순천향대학교 AICS(AI Convergence Software) 연구실 이메일 또는 담당자 연락처로 문의하시기 바랍니다.

**서드파티 패키지**(예: Ollama, FAISS, sentence-transformers, PyPI 의존성)는 각각 **원저작자의 라이선스**가 적용됩니다. 본 `LICENSE`는 그들의 권리를 대체하지 않습니다.
