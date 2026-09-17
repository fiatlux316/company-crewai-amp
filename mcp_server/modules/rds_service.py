import os
import sys

def register(mcp):
    rds_api = None
    
    try:
        from .sample_api import rds_api as api
        rds_api = api
    except ImportError:
        try:
            from sample_api import rds_api as api
            rds_api = api
        except ImportError:
            pass

    if rds_api is None:
        print("Error: Could not import rds_api in rds_service.py", file=sys.stderr)
        return

    @mcp.tool
    def execute_rds_query(db_identifier: str, query: str) -> str:
        """
        Executes a read-only SQL query on the specified RDS database instance.
        """
        return rds_api.execute_rds_query(db_identifier, query)