import os
import re
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests


def _parse_time_range(time_range: str) -> tuple[str, str]:
    """Parse a human-readable time range into ISO 8601 from/to timestamps."""

    # timezone : Asia/Seoul
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    time_range_lower = time_range.lower().strip()

    # Parse patterns like "last 1 hour", "last 30 minutes", "last 7 days"
    match = re.match(
        r"last\s+(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks)",
        time_range_lower,
    )

    if match:
        amount = int(match.group(1))
        unit = match.group(2).rstrip("s")  # normalize to singular

        if unit == "minute":
            delta = timedelta(minutes=amount)
        elif unit == "hour":
            delta = timedelta(hours=amount)
        elif unit == "day":
            delta = timedelta(days=amount)
        elif unit == "week":
            delta = timedelta(weeks=amount)
        else:
            delta = timedelta(hours=1)

        from_time = (now - delta).isoformat()
        to_time = now.isoformat()
    else:
        # Default: last 1 hour
        from_time = (now - timedelta(hours=1)).isoformat()
        to_time = now.isoformat()

    return from_time, to_time


def _datadog_http_error_message(response: requests.Response) -> str:
    if response is not None and response.status_code == 401:
        return (
            "ERROR: Datadog API returned HTTP 401 Unauthorized. "
            "This usually means DD_API_KEY or DD_APP_KEY is invalid, expired, or does not have permission. "
            "Also verify DD_SITE matches your Datadog region (for example datadoghq.com or datadoghq.eu). "
            f"Response: {response.text[:500]}"
        )

    return (
        f"ERROR: Datadog API returned HTTP {response.status_code}. "
        f"Response: {response.text[:500]}"
    )



def datadog_logs_search(query: str, time_range: str, limit: int = 10) -> str:
    # Read credentials from environment
    api_key = os.environ.get("DD_API_KEY")
    app_key = os.environ.get("DD_APP_KEY")
    dd_site = os.environ.get("DD_SITE", "datadoghq.com")
    print(f"DEBUG: Using DD_SITE={dd_site}")
    print(f"DEBUG: Using DD_API_KEY={api_key}")
    print(f"DEBUG: Using DD_APP_KEY={app_key}")

    if not api_key or not app_key:
        return (
            "ERROR: DD_API_KEY and DD_APP_KEY environment variables must be set. "
            "Please configure them in your .env file."
        )

    # Parse the human-readable time range into ISO 8601 timestamps
    from_time, to_time = _parse_time_range(time_range)
    print(f"DEBUG: Parsed time range: from_time={from_time}, to_time={to_time}")

    # Build the API request
    url = f"https://api.{dd_site}/api/v2/logs/events/search"
    headers = {
        "Content-Type": "application/json",
        "DD-API-KEY": api_key,
        "DD-APPLICATION-KEY": app_key,
    }
    body = {
        "filter": {
            "query": query,
            "from": from_time,
            "to": to_time,
        },
        "sort": "-timestamp",
        "options": {
            "timezone": "Asia/Seoul"
        },
        "page": {
            "limit": min(limit, 1000),
        },
    }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        return _datadog_http_error_message(e.response)
    except requests.exceptions.RequestException as e:
        return f"ERROR: Failed to connect to Datadog API: {str(e)}"

    data = response.json()
    logs = data.get("data", [])
    print(f"DEBUG: API Response Logs length: {len(logs)}")
    print(f"DEBUG: API Response Logs: {logs}")

    if not isinstance(logs, list):
        return (
            "ERROR: Unexpected Datadog response format. "
            f"Expected a list under 'data', got {type(logs).__name__}. "
            f"Response: {json.dumps(data)[:500]}"
        )

    if not logs:
        return (
            f"No logs found for query '{query}' in the time range '{time_range}' "
            f"({from_time} to {to_time})."
        )

    # Format the results
    results = []
    results.append(f"=== Datadog Logs Search Results ===")
    results.append(f"Query: {query}")
    results.append(f"Time Range: {from_time} to {to_time}")
    results.append(f"Total Logs Retrieved: {len(logs)}")
    results.append(f"{'=' * 50}\n")

    for i, log_entry in enumerate(logs, 1):
        if not isinstance(log_entry, dict):
            continue
        attrs = log_entry.get("attributes") or {}
        log_attrs = (attrs.get("attributes") or {}) if isinstance(attrs, dict) else {}
        http_info = log_attrs.get("http", {})
        error_info = log_attrs.get("error", {})

        results.append(f"--- Log Entry #{i} ---")
        results.append(f"  Timestamp: {attrs.get('timestamp', 'N/A')}")
        results.append(f"  Status:    {attrs.get('status', 'N/A')}")
        results.append(f"  Service:   {attrs.get('service', 'N/A')}")
        results.append(f"  Host:      {attrs.get('host', 'N/A')}")

        # Message
        message = attrs.get("message", "")
        if message:
            # Truncate very long messages
            if len(message) > 1000:
                message = message[:1000] + "... [truncated]"
            results.append(f"  Message:   {message}")

        # HTTP info
        if http_info:
            results.append(f"  HTTP Method:      {http_info.get('method', 'N/A')}")
            results.append(f"  HTTP URL:         {http_info.get('url', 'N/A')}")
            results.append(f"  HTTP Status Code: {http_info.get('status_code', 'N/A')}")

        # Error info
        if error_info:
            results.append(f"  Error Type:    {error_info.get('kind', error_info.get('type', 'N/A'))}")
            results.append(f"  Error Message: {error_info.get('message', 'N/A')}")
            stack = error_info.get("stack", "")
            if stack:
                if len(stack) > 2000:
                    stack = stack[:2000] + "\n  ... [stack trace truncated]"
                results.append(f"  Stack Trace:\n{stack}")

        # Tags
        tags = attrs.get("tags", [])
        if tags:
            results.append(f"  Tags: {', '.join(tags[:20])}")

        results.append("")

    # Pagination info
    page_after = data.get("meta", {}).get("page", {}).get("after")
    if page_after:
        results.append(
            f"NOTE: More logs are available. "
            f"Use pagination cursor to fetch the next page."
        )

    return "\n".join(results)

def datadog_apm_search(query: str, time_range: str, limit: int = 10) -> str:
    # Read credentials from environment
    api_key = os.environ.get("DD_API_KEY")
    app_key = os.environ.get("DD_APP_KEY")
    dd_site = os.environ.get("DD_SITE", "datadoghq.com")
    print(f"DEBUG: Using DD_SITE={dd_site}")
    print(f"DEBUG: Using DD_API_KEY={api_key}")
    print(f"DEBUG: Using DD_APP_KEY={app_key}")

    if not api_key or not app_key:
        return (
            "ERROR: DD_API_KEY and DD_APP_KEY environment variables must be set. "
            "Please configure them in your .env file."
        )

    # Parse the human-readable time range into ISO 8601 timestamps
    print(f"DEBUG: Parsing time range: {time_range}")
    print(f"DEBUG: query: {query}")
    print(f"DEBUG: limit: {limit}")

    from_time, to_time = _parse_time_range(time_range)
    print(f"DEBUG: Parsed time range: from_time={from_time}, to_time={to_time}")

    # Build the API request
    url = f"https://api.{dd_site}/api/v2/spans/events/search"
    headers = {
        "Content-Type": "application/json",
        "DD-API-KEY": api_key,
        "DD-APPLICATION-KEY": app_key,
    }
    body = {
        "data": {
            "type": "search_request",
            "attributes": {
                "filter": {
                    "query": query,
                    "from": from_time,
                    "to": to_time,
                },
                "sort": "-timestamp",
                "options": {
                    "timezone": "Asia/Seoul"
                },
                "page": {
                    "limit": min(limit, 1000),
                },
            },
        },
    }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=30)
        #print(f"DEBUG: API Response: {response.text}")
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        return _datadog_http_error_message(e.response)
    except requests.exceptions.RequestException as e:
        return f"ERROR: Failed to connect to Datadog API: {str(e)}"

    data = response.json()
    #print(f"DEBUG: API Response Data: {data}")
    logs = data.get("data", [])
    print(f"DEBUG: API Response Logs length: {len(logs)}")
    print(f"DEBUG: API Response Logs sample: {logs[0] if logs else 'No logs returned'}")


    if not isinstance(logs, list):
        return (
            "ERROR: Unexpected Datadog APM response format. "
            f"Expected a list under 'data', got {type(logs).__name__}. "
            f"Response: {json.dumps(data)[:500]}"
        )

    if not logs:
        return (
            f"No APM trace found for query '{query}' in the time range '{time_range}' "
            f"({from_time} to {to_time})."
        )

    # Format the results
    results = []
    results.append(f"=== Datadog APM Search Results ===")
    results.append(f"Query: {query}")
    results.append(f"Time Range: {from_time} to {to_time}")
    results.append(f"Total Logs Retrieved: {len(logs)}")
    results.append(f"{'=' * 50}\n")

    for i, log_entry in enumerate(logs, 1):
        if not isinstance(log_entry, dict):
            continue
        attrs = log_entry.get("attributes") or {}
        log_attrs = (attrs.get("attributes") or {}) if isinstance(attrs, dict) else {}
        http_info = log_attrs.get("http", {})
        error_info = log_attrs.get("error", {})

        results.append(f"--- Log Entry #{i} ---")
        results.append(f"  Timestamp: {attrs.get('timestamp', 'N/A')}")
        results.append(f"  Status:    {attrs.get('status', 'N/A')}")
        results.append(f"  Service:   {attrs.get('service', 'N/A')}")
        results.append(f"  Host:      {attrs.get('host', 'N/A')}")

        # Message
        message = attrs.get("message", "")
        if message:
            # Truncate very long messages
            if len(message) > 1000:
                message = message[:1000] + "... [truncated]"
            results.append(f"  Message:   {message}")

        # HTTP info
        if http_info:
            results.append(f"  HTTP Method:      {http_info.get('method', 'N/A')}")
            results.append(f"  HTTP URL:         {http_info.get('url', 'N/A')}")
            results.append(f"  HTTP Status Code: {http_info.get('status_code', 'N/A')}")

        # Error info
        if error_info:
            results.append(f"  Error Type:    {error_info.get('kind', error_info.get('type', 'N/A'))}")
            results.append(f"  Error Message: {error_info.get('message', 'N/A')}")
            stack = error_info.get("stack", "")
            if stack:
                if len(stack) > 2000:
                    stack = stack[:2000] + "\n  ... [stack trace truncated]"
                results.append(f"  Stack Trace:\n{stack}")

        # Tags
        tags = attrs.get("tags", [])
        if tags:
            results.append(f"  Tags: {', '.join(tags[:20])}")

        results.append("")

    # Pagination info
    page_after = data.get("meta", {}).get("page", {}).get("after")
    if page_after:
        results.append(
            f"NOTE: More logs are available. "
            f"Use pagination cursor to fetch the next page."
        )

    return "\n".join(results)
