FROM python:3.11-slim

# 보안 및 환경 변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONPATH=/app

WORKDIR /app

# 시스템 라이브러리 설치 (CrewAI 도구가 빌드 시 C 라이브러리를 필요로 할 수 있음)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 전체 애플리케이션 복사 (crews/ 폴더와 gateway/ 폴더 모두 포함)
COPY . .

EXPOSE 8000
