#!/usr/bin/env python

import json
import math
import os
import re
import shutil
import sys
from datetime import datetime

import pandas as pd

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.join(_THIS_DIR, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

BATCH_SIZE = int(os.getenv("QA_BATCH_SIZE", "300"))
MAX_RETRIES = int(os.getenv("QA_MAX_RETRIES", "2"))
MIN_SPLIT_SIZE = int(os.getenv("QA_MIN_SPLIT_SIZE", "10"))
SAMPLE_SIZE = int(os.getenv("QA_SAMPLE_SIZE", "0"))

TRANSFORMED_FILE = os.getenv(
    "QA_TRANSFORMED_FILE",
    os.path.join(_THIS_DIR, "output", "transformed_data.csv"),
)
_DEFAULT_RESULT_FILE = os.path.join(_THIS_DIR, "output", "analysis_result.json")
RESULT_FILE = os.getenv(
    "QA_RESULT_FILE",
    _DEFAULT_RESULT_FILE,
)


def load_batches(df: pd.DataFrame, batch_size: int):
    total = len(df)
    n_batches = math.ceil(total / batch_size) if batch_size > 0 else 1
    for index in range(n_batches):
        start = index * batch_size
        end = min(start + batch_size, total)
        yield df.iloc[start:end], start, end


def serialize_batch(batch_df: pd.DataFrame) -> str:
    return batch_df.to_csv(sep="|", index=False)


def _extract_json(raw_text: str):
    if not raw_text:
        return None
    text = raw_text.strip()

    code_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for candidate in reversed(code_blocks):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        first = text.rfind('{"summary"')
        if first == -1:
            first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            candidate = text[first : last + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None
        return None


def _checkpoint_path(result_file: str | None = None) -> str:
    if result_file is None:
        result_file = RESULT_FILE
    base, _ = os.path.splitext(result_file)
    return base + ".progress.json"


def _load_checkpoint(source_file: str, batch_size: int, total_count: int):
    path = _checkpoint_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return None

    if (
        data.get("source_file") != source_file
        or data.get("batch_size") != batch_size
        or data.get("total_count") != total_count
    ):
        return None
    return data


def _save_checkpoint(
    source_file: str,
    batch_size: int,
    total_count: int,
    completed_ranges: list,
    merged_result: dict,
) -> None:
    path = _checkpoint_path()
    data = {
        "source_file": source_file,
        "batch_size": batch_size,
        "total_count": total_count,
        "completed_ranges": completed_ranges,
        "merged_result": merged_result,
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)
    os.replace(tmp_path, path)


def _clear_checkpoint() -> None:
    path = _checkpoint_path()
    if os.path.exists(path):
        os.remove(path)


def _write_result_file(
    total_count: int, processed_count: int, merged_result: dict, is_complete: bool
) -> dict:
    anomaly_count = len(merged_result)
    normal_count = processed_count - anomaly_count
    accuracy_rate = (
        round((normal_count / processed_count * 100), 2) if processed_count > 0 else 0.0
    )

    final_output = {
        "summary": {
            "total_count": total_count,
            "processed_count": processed_count,
            "normal_count": normal_count,
            "anomaly_count": anomaly_count,
            "accuracy_rate": accuracy_rate,
            "is_complete": is_complete,
        },
        "result": merged_result,
    }

    os.makedirs(os.path.dirname(RESULT_FILE) or ".", exist_ok=True)
    tmp_path = RESULT_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as file:
        json.dump(final_output, file, ensure_ascii=False, indent=2)
    os.replace(tmp_path, RESULT_FILE)
    return final_output


def _excel_path(result_file: str | None = None) -> str:
    if result_file is None:
        result_file = RESULT_FILE
    base, _ = os.path.splitext(result_file)
    return base + ".xlsx"


def _write_excel_file(merged_result: dict) -> None:
    df = pd.DataFrame.from_dict(merged_result, orient="index")
    df.index.name = "id"
    df = df.reset_index()

    columns_order = [
        "id",
        "inflo_chnl_id",
        "question",
        "answer",
        "button",
        "intent_id",
        "description",
    ]
    existing_columns = [column for column in columns_order if column in df.columns]
    df = df[existing_columns]

    excel_path = _excel_path()
    os.makedirs(os.path.dirname(excel_path) or ".", exist_ok=True)
    tmp_path = excel_path + ".tmp.xlsx"
    df.to_excel(tmp_path, index=False)
    os.replace(tmp_path, excel_path)


def _process_batch_with_retry(
    crew_cls, batch_df: pd.DataFrame, start: int, end: int, depth: int = 0
) -> dict:
    indent = "  " * (depth + 1)

    for attempt in range(1, MAX_RETRIES + 1):
        batch_text = serialize_batch(batch_df)
        try:
            crew_output = crew_cls().crew().kickoff(inputs={"batch_data": batch_text})
            raw = crew_output.raw if hasattr(crew_output, "raw") else str(crew_output)
        except Exception as error:
            print(
                f"{indent}⚠️ 배치 {start}~{end} 시도 {attempt}/{MAX_RETRIES} 실패: {error}"
            )
            continue

        batch_json = _extract_json(raw)
        if batch_json is None:
            print(
                f"{indent}⚠️ 배치 {start}~{end} 시도 {attempt}/{MAX_RETRIES} JSON 파싱 실패"
            )
            continue

        return batch_json.get("result", {})

    count = len(batch_df)
    if count <= MIN_SPLIT_SIZE:
        print(
            f"{indent}❌ 배치 {start}~{end} ({count}건) 최종 실패, 모든 재시도/분할 소진, 건너뜁니다."
        )
        return {}

    mid = count // 2
    left_df = batch_df.iloc[:mid]
    right_df = batch_df.iloc[mid:]
    left_start, left_end = start, start + mid
    right_start, right_end = start + mid, end
    print(
        f"{indent}🔀 배치 {start}~{end} 반복 실패 -> "
        f"{left_start}~{left_end}, {right_start}~{right_end} 로 분할하여 재시도합니다."
    )

    merged = {}
    merged.update(
        _process_batch_with_retry(crew_cls, left_df, left_start, left_end, depth + 1)
    )
    merged.update(
        _process_batch_with_retry(crew_cls, right_df, right_start, right_end, depth + 1)
    )
    return merged


def run_batches():
    if not os.path.exists(TRANSFORMED_FILE):
        print(
            f"❌ 파일을 찾을 수 없습니다: {TRANSFORMED_FILE}. 먼저 run_transform.py를 실행하세요."
        )
        return

    global RESULT_FILE
    if RESULT_FILE == _DEFAULT_RESULT_FILE:
        run_dir = os.path.join(
            _THIS_DIR, "output", datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        os.makedirs(run_dir, exist_ok=True)
        shutil.copy2(TRANSFORMED_FILE, os.path.join(run_dir, "transformed_data.csv"))
        RESULT_FILE = os.path.join(run_dir, "analysis_result.json")
        print(f"📁 이번 실행 결과 폴더: {run_dir}")

    from faq_annotation.crew import FaqAnnotation

    df = pd.read_csv(TRANSFORMED_FILE, sep="|")

    if SAMPLE_SIZE > 0:
        df = df.head(SAMPLE_SIZE)
        print(f"🧪 테스트 모드: 앞에서부터 {SAMPLE_SIZE}건만 샘플링하여 처리합니다.")

    total_count = len(df)
    print(
        f"🚀 전체 {total_count}건을 배치 크기 {BATCH_SIZE}로 분할하여 분석을 시작합니다."
    )

    force_fresh = os.getenv("QA_FRESH", "").strip() in ("1", "true", "True")
    checkpoint = (
        None
        if force_fresh
        else _load_checkpoint(TRANSFORMED_FILE, BATCH_SIZE, total_count)
    )

    merged_result = {}
    completed_ranges = []
    if checkpoint is not None:
        merged_result = checkpoint.get("merged_result", {})
        completed_ranges = [
            tuple(item) for item in checkpoint.get("completed_ranges", [])
        ]
        if completed_ranges:
            processed_so_far = sum(end - start for start, end in completed_ranges)
            print(
                f"♻️  이전 체크포인트 발견: {len(completed_ranges)}개 배치({processed_so_far}건) 이미 완료됨. 이어서 진행합니다."
            )

    completed_set = set(completed_ranges)
    processed_count = sum(end - start for start, end in completed_ranges)

    for batch_df, start, end in load_batches(df, BATCH_SIZE):
        if (start, end) in completed_set:
            print(f"  ⏭  배치 {start}~{end} 는 이미 처리됨 (체크포인트), 건너뜁니다.")
            continue

        print(f"  ▶ 배치 처리 중: {start}~{end} ({len(batch_df)}건)")
        batch_result = _process_batch_with_retry(FaqAnnotation, batch_df, start, end)

        merged_result.update(batch_result)
        completed_ranges.append((start, end))
        completed_set.add((start, end))
        processed_count += len(batch_df)

        _save_checkpoint(
            TRANSFORMED_FILE, BATCH_SIZE, total_count, completed_ranges, merged_result
        )
        is_complete = processed_count >= total_count
        _write_result_file(total_count, processed_count, merged_result, is_complete)
        _write_excel_file(merged_result)
        print(
            f"  💾 중간 저장 완료 ({processed_count}/{total_count}건 처리됨) -> {RESULT_FILE}, {_excel_path()}"
        )

    is_complete = processed_count >= total_count
    final_output = _write_result_file(
        total_count, processed_count, merged_result, is_complete
    )

    if is_complete:
        _clear_checkpoint()

    anomaly_count = final_output["summary"]["anomaly_count"]
    accuracy_rate = final_output["summary"]["accuracy_rate"]
    status = "완료" if is_complete else "중단(부분 완료)"
    print(
        f"✅ 분석 {status}: {processed_count}/{total_count}건 처리, 이상 {anomaly_count}건 발견 (처리 구간 기준 정확도 {accuracy_rate}%)"
    )
    _write_excel_file(merged_result)
    print(f"결과 저장: {RESULT_FILE}")
    print(f"엑셀 저장: {_excel_path()}")
    return final_output


if __name__ == "__main__":
    run_batches()
