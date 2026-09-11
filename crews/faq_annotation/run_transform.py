import csv
import json
import os
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import psycopg2

POSTGRES_QUERY = """
WITH base AS (
    SELECT
        id,
        inflo_chnl_id,
        type,
        reg_dts,
        value,
        intent_id,
        (value IS JSON OBJECT) AS is_json,
        CASE WHEN value IS JSON OBJECT THEN value::jsonb ELSE NULL END AS value_json
    FROM braindb.cbot_chatbot_log
    WHERE date(reg_dts) = %(target_date)s
),
flagged AS (
    SELECT
        *,
        CASE
            WHEN type = 'REQUEST' AND NOT is_json THEN 1
            ELSE 0
        END AS is_new_question
    FROM base
),
grouped AS (
    SELECT
        *,
        SUM(is_new_question) OVER (
            PARTITION BY inflo_chnl_id ORDER BY reg_dts, id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS q_group
    FROM flagged
),
questions AS (
    SELECT
        inflo_chnl_id,
        q_group,
        id AS q_id,
        reg_dts AS q_reg_dts,
        value AS question_text
    FROM grouped
    WHERE type = 'REQUEST' AND is_new_question = 1
),
bot_responses AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY inflo_chnl_id, q_group ORDER BY reg_dts, id
        ) AS rn
    FROM grouped
    WHERE type = 'RESPONSE'
      AND is_json
      AND (value_json->>'type') = 'BOT'
      AND q_group > 0
),
content_items AS (
    SELECT
        br.inflo_chnl_id,
        br.q_group,
        br.id AS response_id,
        br.intent_id,
        br.rn,
        item
    FROM bot_responses br,
         LATERAL jsonb_array_elements(br.value_json->'content') AS item
),
answer_texts AS (
    SELECT inflo_chnl_id, q_group, response_id, rn, intent_id,
           item->>'value' AS text_val
    FROM content_items
    WHERE item->>'type' = 'text'
),
card_sub_items AS (
    SELECT
        ci.inflo_chnl_id, ci.q_group, ci.response_id, ci.rn, ci.intent_id,
        sub
    FROM content_items ci,
         LATERAL jsonb_array_elements(ci.item->'value') AS sub
    WHERE ci.item->>'type' = 'card'
),
card_texts AS (
    SELECT inflo_chnl_id, q_group, response_id, rn, intent_id,
           sub->>'value' AS text_val
    FROM card_sub_items
    WHERE sub->>'type' = 'text'
),
card_buttons AS (
    SELECT
        cs.inflo_chnl_id, cs.q_group, cs.response_id, cs.rn, cs.intent_id,
        btn->>'action' AS action_val,
        btn->>'label' AS label_val,
        ord.ordinality AS btn_order
    FROM card_sub_items cs,
         LATERAL jsonb_array_elements(cs.sub->'value') WITH ORDINALITY AS ord(btn, ordinality)
    WHERE cs.sub->>'type' = 'buttons'
),
answer_agg AS (
    SELECT inflo_chnl_id, q_group, response_id, rn, intent_id,
           string_agg(text_val, ' ' ORDER BY seq) AS answer
    FROM (
        SELECT inflo_chnl_id, q_group, response_id, rn, intent_id, text_val, 1 AS seq
        FROM answer_texts
        WHERE text_val IS NOT NULL AND text_val <> ''
        UNION ALL
        SELECT inflo_chnl_id, q_group, response_id, rn, intent_id, text_val, 2 AS seq
        FROM card_texts
        WHERE text_val IS NOT NULL AND text_val <> ''
    ) t
    GROUP BY inflo_chnl_id, q_group, response_id, rn, intent_id
),
action_agg AS (
    SELECT inflo_chnl_id, q_group, response_id, rn, intent_id,
           string_agg(DISTINCT action_val, ',') AS actions
    FROM card_buttons
    WHERE action_val IS NOT NULL
    GROUP BY inflo_chnl_id, q_group, response_id, rn, intent_id
),
button_agg AS (
    SELECT inflo_chnl_id, q_group, response_id, rn, intent_id,
           string_agg(label_val, ',' ORDER BY btn_order) AS buttons
    FROM card_buttons
    WHERE label_val IS NOT NULL
    GROUP BY inflo_chnl_id, q_group, response_id, rn, intent_id
),
candidate_responses AS (
    SELECT
        br.inflo_chnl_id, br.q_group, br.id AS response_id, br.rn, br.intent_id,
        COALESCE(aa.answer, '') AS answer,
        ac.actions,
        bt.buttons,
        (COALESCE(aa.answer, '') <> '' OR ac.actions IS NOT NULL OR bt.buttons IS NOT NULL) AS has_content,
        br.reg_dts
    FROM bot_responses br
    LEFT JOIN answer_agg aa ON aa.inflo_chnl_id = br.inflo_chnl_id AND aa.q_group = br.q_group AND aa.rn = br.rn
    LEFT JOIN action_agg ac ON ac.inflo_chnl_id = br.inflo_chnl_id AND ac.q_group = br.q_group AND ac.rn = br.rn
    LEFT JOIN button_agg bt ON bt.inflo_chnl_id = br.inflo_chnl_id AND bt.q_group = br.q_group AND bt.rn = br.rn
),
chosen_response AS (
    SELECT DISTINCT ON (inflo_chnl_id, q_group)
        inflo_chnl_id, q_group, response_id, intent_id, answer, actions, buttons, reg_dts
    FROM candidate_responses
    WHERE has_content
    ORDER BY inflo_chnl_id, q_group, rn
)
SELECT
    q.q_id AS id,
    q.inflo_chnl_id,
    q.q_reg_dts AS reg_dts,
    q.question_text AS "질문",
    cr.answer AS "답변",
    COALESCE(cr.actions, '') AS "액션",
    COALESCE(cr.buttons, '') AS "버튼",
    COALESCE(cr.intent_id, ARRAY[]::integer[]) AS intent_id
FROM questions q
JOIN chosen_response cr
     ON cr.inflo_chnl_id = q.inflo_chnl_id AND cr.q_group = q.q_group
ORDER BY q.inflo_chnl_id, q.q_reg_dts;
"""

_KST = timezone(timedelta(hours=9))


def _parse_intent_id(raw):
    if isinstance(raw, list):
        result = []
        for part in raw:
            try:
                result.append(int(part))
            except (TypeError, ValueError):
                continue
        return result
    if raw is None or (not isinstance(raw, (list, dict)) and pd.isna(raw)):
        return []
    s = str(raw).strip()
    if not s:
        return []
    match = re.match(r"^\{(.*)\}$", s)
    inner = match.group(1) if match else s
    if not inner.strip():
        return []
    result = []
    for part in inner.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            continue
    return result


def _extract_bot_response(parsed):
    answer_parts = []
    actions = []
    buttons = []

    for item in parsed.get("content", []) or []:
        item_type = item.get("type")
        if item_type == "text":
            text_val = item.get("value", "")
            if text_val:
                answer_parts.append(text_val)
        elif item_type == "card":
            for sub in item.get("value", []) or []:
                sub_type = sub.get("type")
                if sub_type == "text":
                    text_val = sub.get("value", "")
                    if text_val:
                        answer_parts.append(text_val)
                elif sub_type == "buttons":
                    for btn in sub.get("value", []) or []:
                        action_val = btn.get("action")
                        label_val = btn.get("label")
                        if action_val is not None:
                            actions.append(action_val)
                        if label_val is not None:
                            buttons.append(label_val)

    return " ".join(answer_parts).strip(), actions, buttons


def _read_source_csv(input_file: str) -> pd.DataFrame:
    with open(input_file, encoding="utf-8-sig") as file:
        first_line = file.readline()

    if "||" in first_line:
        with open(input_file, encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file, delimiter="|")
            rows = list(reader)
        if not rows:
            return pd.DataFrame()
        header = [value for index, value in enumerate(rows[0]) if index % 2 == 0]
        data_rows = []
        for row in rows[1:]:
            values = [value for index, value in enumerate(row) if index % 2 == 0]
            if len(values) < len(header):
                values = values + [""] * (len(header) - len(values))
            elif len(values) > len(header):
                values = values[: len(header)]
            data_rows.append(values)
        return pd.DataFrame(data_rows, columns=header).replace("", pd.NA)

    return pd.read_csv(input_file)


def _get_target_date() -> str:
    return (datetime.now(_KST) - timedelta(days=1)).strftime("%Y-%m-%d")


def _read_source_data(input_file: str | None = None) -> pd.DataFrame:
    database_url = os.getenv("POSTGRES_URL", "").strip()
    if not database_url:
        if not input_file:
            raise ValueError("input_file 또는 POSTGRES_URL 중 하나가 필요합니다.")
        return _read_source_csv(input_file)

    target_date = _get_target_date()
    print(f"PostgreSQL에서 {target_date}(실행일 기준 전일) chatbot log를 조회합니다.")
    with psycopg2.connect(database_url) as connection:
        return pd.read_sql_query(
            POSTGRES_QUERY, connection, params={"target_date": target_date}
        )


def transform_chatbot_data(input_file, output_file):
    df = _read_source_data(input_file)

    if "질문" in df.columns and "답변" in df.columns:
        result_df = df[
            [
                "id",
                "inflo_chnl_id",
                "reg_dts",
                "질문",
                "답변",
                "액션",
                "버튼",
                "intent_id",
            ]
        ].copy()
        result_df["intent_id"] = result_df["intent_id"].apply(_parse_intent_id)
        result_df.to_csv(output_file, sep="|", index=False)
        return len(result_df)

    if "reg_dts" in df.columns:
        df["reg_dts"] = pd.to_datetime(df["reg_dts"])
        df = df.sort_values(by=["inflo_chnl_id", "reg_dts"], ascending=[True, True])

    processed_rows = []
    for _, group in df.groupby("inflo_chnl_id"):
        current_question = None

        for _, row in group.iterrows():
            row_type = row.get("type")
            raw_value = row.get("value")

            if pd.isna(raw_value):
                continue
            value_str = str(raw_value).strip()

            parsed = None
            if value_str.startswith("{"):
                try:
                    parsed = json.loads(value_str)
                except (json.JSONDecodeError, ValueError):
                    continue

            if row_type == "REQUEST":
                if parsed is not None:
                    msg_type = parsed.get("type")
                    if msg_type == "GREET_RESPOND_NORMAL":
                        continue
                    if msg_type == "DIALOG_FLOW_EVENT":
                        current_question = {
                            "id": row.get("id"),
                            "inflo_chnl_id": row.get("inflo_chnl_id"),
                            "reg_dts": row.get("reg_dts"),
                            "text": parsed.get("message", ""),
                        }
                else:
                    current_question = {
                        "id": row.get("id"),
                        "inflo_chnl_id": row.get("inflo_chnl_id"),
                        "reg_dts": row.get("reg_dts"),
                        "text": value_str,
                    }

            elif row_type == "RESPONSE":
                if parsed is None:
                    continue
                if parsed.get("type") == "INTRO_MESG":
                    continue
                if parsed.get("type") == "BOT" and current_question is not None:
                    answer, actions, buttons = _extract_bot_response(parsed)
                    intent_id_list = _parse_intent_id(row.get("intent_id"))
                    if not answer and not actions and not buttons:
                        continue

                    seen_actions = []
                    for action in actions:
                        if action not in seen_actions:
                            seen_actions.append(action)

                    processed_rows.append(
                        {
                            "id": current_question["id"],
                            "inflo_chnl_id": current_question["inflo_chnl_id"],
                            "reg_dts": current_question["reg_dts"],
                            "질문": current_question["text"],
                            "답변": answer,
                            "액션": ",".join(seen_actions),
                            "버튼": ",".join(buttons),
                            "intent_id": intent_id_list,
                        }
                    )
                    current_question = None

    result_df = pd.DataFrame(
        processed_rows,
        columns=[
            "id",
            "inflo_chnl_id",
            "reg_dts",
            "질문",
            "답변",
            "액션",
            "버튼",
            "intent_id",
        ],
    )
    result_df.to_csv(output_file, sep="|", index=False)
    return len(result_df)


if __name__ == "__main__":
    input_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "input")
    input_file = os.path.join("input", "braindb_cbot_chatbot_log_9 (1).csv")
    if os.path.isdir(input_dir):
        candidates = [
            os.path.join(input_dir, file)
            for file in os.listdir(input_dir)
            if file.lower().endswith(".csv")
        ]
        if candidates:
            input_file = max(candidates, key=os.path.getmtime)

    output_file = os.path.join("output", "transformed_data.csv")
    os.makedirs("output", exist_ok=True)

    print(f"입력 파일: {input_file}")
    count = transform_chatbot_data(input_file, output_file)
    print(f"처리된 Q&A 쌍: {count}건 -> {output_file}")
