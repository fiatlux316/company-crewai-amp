import sys

def register(mcp):
    datadog_api = None
    
    try:
        from .sample_api import datadog_api as api
        datadog_api = api
    except ImportError:
        try:
            from sample_api import datadog_api as api
            datadog_api = api
        except ImportError:
            pass

    if datadog_api is None:
        print("Error: Could not import datadog_api in datadog_service.py", file=sys.stderr)
        return

    @mcp.tool
    def search_datadog_logs(query: str, time_range: str, limit: int = 10) -> str:
        """
        Search and retrieve Datadog Logs.
        
        Args:
            query: The search query (e.g. 'status:error service:web-api')
            time_range: Human-readable time range (e.g. 'last 1 hour', 'last 24 hours')
            limit: Maximum number of log entries to retrieve (default 10)
        """
        return datadog_api.datadog_logs_search(query, time_range, limit)

    @mcp.tool
    def search_datadog_apm(query: str, time_range: str, limit: int = 10) -> str:
        """
        Search and retrieve Datadog APM trace spans.
        
        Args:
            query: The trace search query (e.g. 'service:payment-gateway')
            time_range: Human-readable time range (e.g. 'last 1 hour', 'last 6 hours')
            limit: Maximum number of traces/spans to retrieve (default 10)
        """
        return datadog_api.datadog_apm_search(query, time_range, limit)
