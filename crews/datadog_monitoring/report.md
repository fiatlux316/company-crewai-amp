# report.md

```markdown
# 로그 분석 보고서: erody-assist-service

**작성일**: 2026-09-10
**대상 서비스**: `erody-assist-service`
**클러스터**: `erody-prd-comm-eksc` (EKS, `ap-northeast-2a`)
**데이터 출처**: Datadog Logs API (`POST /api/v2/logs/events/search`)

---

## 1. 핵심 요약 (Executive Summary)

본 보고서는 `erody-assist-service`에 대한 최근 24시간(Last 24 hours, 기준일 2026-09-10) 로그 분석 요청을 기반으로 작성되었습니다. 다만, **조회 파라미터 제약(`limit=10`, 페이지네이션 커서 미사용)**으로 인해 실제 확보된 데이터는 24시간 전체가 아닌 **2026-09-10T01:46:39.412Z ~ 01:46:42.413Z (약 3초 구간, 최신 10건)**에 불과합니다. 이는 24시간 대비 약 **0.0035%**의 커버리지로, 본 분석의 신뢰도를 근본적으로 제한하는 **핵심 리스크**입니다.

확보된 표본 내에서는 **심각한 오류(ERROR/CRITICAL)가 0건** 관찰되었으며, `presidio-analyzer` 컴포넌트에서 **PII 마스킹 관련 경고(WARNING) 2건**이 동일 트랜잭션 내 반복 발생한 것이 유일한 이슈입니다. 인프라(EKS 노드, 컨테이너, `/health` 체크) 및 다운스트림 연동(Sendbird, LiteLLM)은 정상 동작 중인 것으로 확인됩니다.

**가장 중요한 결론**: 이 보고서는 "24시간 동안 오류가 없었다"는 것을 증명하지 않습니다. 단지 "가장 최근 3초 스냅샷에 오류가 없었다"는 것만을 확인했을 뿐이며, **전체 기간에 대한 재조회가 최우선 조치로 필요**합니다.

---

## 2. 심각한 오류 (Critical Errors)

| 항목 | 결과 |
|---|---|
| `status=error` 로그 수 | **0건** (조회된 10건 중) |
| `stack_trace` 포함 로그 수 | **0건** (전체 `stack_trace: null`) |
| Exception/Traceback 키워드 매칭 | 없음 |
| 영향받은 서비스 | 없음 (표본 내 미탐지) |
| 발생 타임스탬프 | 해당 없음 |

**분석**: 표본 구간(약 3초) 내에서는 심각 오류나 예외가 탐지되지 않았습니다. 그러나 표본 크기가 극히 작아(24시간 중 0.0035%), 실제 발생했을 수 있는 오류 급증 구간(spike)을 완전히 놓쳤을 가능성이 높습니다.

> ⚠️ **분석 한계 명시**: 본 보고서는 "오류 없음"을 확정할 수 없습니다. `status:error OR status:critical` 필터와 페이지네이션 커서를 활용한 전체 24시간 재조회가 반드시 필요합니다.

---

## 3. 경고 및 이상 징후 (Warnings & Anomalies)

### 3.1 경고 (Warnings)

| 발생 시각 (실제) | 표시 Timestamp | 컴포넌트 | 메시지 | 발생 횟수 |
|---|---|---|---|---|
| 2026-09-10T01:46:41.462Z | 01:46:42.413Z | `presidio-analyzer` | `Entity CARDINAL is not mapped to a Presidio entity, but keeping anyway.` | 1 |
| 2026-09-10T01:46:41.445Z | 01:46:42.413Z | `presidio-analyzer` | `Entity CARDINAL is not mapped to a Presidio entity, but keeping anyway.` | 1 |

- **소계**: 표본 10건 중 2건(20%)이 WARNING 레벨
- **패턴**: 동일 `trace_id`(`5678214569019303924`) 내에서 약 17ms 간격으로 2회 반복
- **원인**: `presidio-analyzer`의 NER 모델이 `CARDINAL`(숫자/수량) 엔티티를 인식했으나, PII 마스킹 대상 엔티티 맵에 매핑되지 않음
- **영향도**: 낮음~중간 — 서비스 중단은 없으나, `CARDINAL`이 실제 개인정보(전화번호, 카드번호 일부 등)를 포함할 경우 마스킹 누락 리스크 존재
- **반복성**: 단일 상담 처리(트랜잭션) 내에서 PII 마스킹 로직이 여러 텍스트 조각에 대해 반복 호출되는 구조로 추정됨 → 상담 건수 증가 시 이 경고도 비례하여 대량 발생 가능

### 3.2 이상 징후 (Anomalies)

| 이상 징후 | 설명 | 심각도 |
|---|---|---|
| **데이터 커버리지 이상** | 24시간 쿼리 요청 대비 반환된 10건이 모두 3초 이내(01:46:39~01:46:42)에 집중됨 | 🔴 High |
| **PII 마스킹 경고 반복** | 단일 트랜잭션 내 동일 경고 2회 발생 | 🟡 Medium |
| **헬스체크 로그 과다 비중** | 10건 중 3건(30%)이 `/health` 체크 응답 → k8s liveness/readiness probe로 추정 | 🟢 Low (정상 운영 패턴) |
| **외부 의존성 응답시간 트렌드 미확인** | LiteLLM(`internal-litellm.emart.com`), Sendbird API 호출은 개별 응답(`elapsed: 0.0241s`) 기준 정상이나, 표본이 1건뿐이라 지연 트렌드 판단 불가 | 🟡 Medium |

---

## 4. 트렌드 (Trends) — Last 24 Hours

> ⚠️ **트렌드 분석 수행 불가**: 확보된 데이터가 24시간 중 단 3초 스냅샷에 불과하여, 다음 항목들에 대한 신뢰 가능한 트렌드 분석이 불가능합니다.

- 시간대별 오류율 변화
- 피크타임 대비 오프피크 트래픽/오류 비교
- WARNING 발생 빈도의 시간대별 분포
- 응답 지연(latency) 추이

### 4.1 표본 내 관찰된 반복 패턴 (참고용, 트렌드 아님)

1. **`GET /health` 요청 반복**: 01:46:39.412Z × 2, 01:46:42.413Z × 1 → k8s probe 주기(약 3초 간격)로 추정, 정상 패턴
2. **`presidio-analyzer` WARNING 반복**: 동일 trace 내 연속 2회 발생 → PII 스캔이 여러 텍스트 조각에 대해 반복 실행되는 구조
3. **순차 처리 체인 확인**: `Sendbird API 호출 → 응답 → classify_service → LiteLLM 호출`이 하나의 `trace_id`(`5678214569019303924`) 내에서 명확히 관찰됨 (정상 워크플로우)

### 4.2 서비스/컴포넌트별 로그 레벨 분포 (표본 기준)

| 서비스/컴포넌트 | 로그 레벨 | 발생 건수 | 비율 |
|---|---|---|---|
| erody-assist-service (전체) | INFO | 8건 | 80% |
| presidio-analyzer (내부 모듈) | WARNING | 2건 | 20% |
| erody-assist-service | ERROR/CRITICAL | 0건 | 0% |

**다운스트림/연동 시스템 상태** (표본 내 정상 확인, 장애 없음):
- Sendbird API (`ticket_id=16163697` 처리) — 정상
- Internal LiteLLM (`internal-litellm.emart.com/v1/chat/completions`) — HTTP 200 OK
- Presidio (PII 마스킹 엔진) — 경고만 존재, 기능 자체는 동작 중

**인프라 컨텍스트**:
- Cluster: `erody-prd-comm-eksc` (EKS, `ap-northeast-2a`)
- Nodegroup: `erody-prd-eksc-comm-ng`
- Container: `erody-assist-service-cntnr`
- AWS Account: `876976907072`

---

## 5. 근본 원인 가설 (Preliminary Root Cause Hypotheses)

| # | 가설 | 근거 | 확신도 |
|---|---|---|---|
| 1 | PII 마스킹 파이프라인의 `CARDINAL` 엔티티 미매핑 반복 경고는 **설정 미완성(config gap)**이 원인 | 로그 메시지가 해결책(`labels_to_ignore` 추가)을 직접 제시 | 높음 |
| 2 | 표본에서 심각 오류가 없는 것은 실제 무결함이 아닌 **쿼리 범위/페이지네이션 한계**로 인한 관측 공백일 가능성 | `limit=10` 및 pagination cursor 미사용 명시 | 높음 |
| 3 | `/health` 체크 응답이 지속적으로 200 반환 → 인프라(EKS 노드, 컨테이너) 자체는 정상 가동 중 | 3건의 연속된 200 응답 | 중간 |
| 4 | 상담 처리 워크플로우(Sendbird → 분류 → LiteLLM)는 정상 체인으로 동작, 병목/장애 신호 없음 | 단일 trace_id 내 순차 처리 완료 확인 | 중간 |

---

## 6. 권장 사항 (Recommendations)

| 우선순위 | 조치 항목 | 상세 내용 |
|---|---|---|
| 🔴 긴급 | **전체 24시간 범위 재조회** | `status:error OR status:critical` 필터와 pagination cursor를 활용하여 표본 부족 문제를 해소하고 신뢰 가능한 오류 분석 수행 |
| 🟡 중 | **PII 마스킹 설정 검토** | `presidio-analyzer`의 `NerModelConfiguration.labels_to_ignore`에 `CARDINAL` 추가 여부를 PII 마스킹 정책팀과 협의 |
| 🟡 중 | **외부 API 응답시간 SLA 확인** | LiteLLM 및 Sendbird API에 대한 응답 시간(latency) 히스토그램을 별도 쿼리하여 SLA 위반 여부 점검 |
| 🟢 하 | **헬스체크 로그 분리** | `/health` 체크 로그를 별도 인덱스/보관 정책으로 분리하여 비즈니스 로그 대비 노이즈 비율 감소 |
| 🟢 하 | **분산 추적(APM) 연계** | trace_id 기반 APM 연계로 상담 처리 파이프라인의 종단 지연(end-to-end latency) 모니터링 대시보드 구축 |

---

## 7. 부록 (Appendix) — 원본 로그 샘플

### 7.1 WARNING 샘플 (presidio-analyzer)

```json
{
  "timestam