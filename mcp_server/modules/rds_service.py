import os
import sys
import pandas as pd
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
    def execute_rds_query(query: str,db_identifier: str = None) -> str:
        """
        Executes a read-only SQL query on the specified RDS database instance.
        """
        if not db_identifier:
            db_identifier = os.environ.get("DB_IDENTIFIER")
        
        result = rds_api.execute_rds_query(db_identifier, query)

        if isinstance(result, str):
            return result
        if isinstance(result, pd.DataFrame):
            if result.empty:
                return "쿼리 결과가 없습니다."
            return result.to_string(index=False)
        if result is None:
            return "쿼리 결과가 없습니다."
        return str(result)