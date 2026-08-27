def register(mcp):
    @mcp.tool
    def execute_rds_query(db_identifier: str, query: str) -> str:
        """
        Executes a read-only SQL query on the specified RDS database instance.
        
        Args:
            db_identifier: The RDS DB Instance identifier or connection name
            query: The SQL query to execute (must be SELECT/read-only)
        """
        # Safety check to prevent write queries in this tool
        cleaned_query = query.strip().upper()
        if not cleaned_query.startswith("SELECT"):
            return "Error: Only read-only SELECT queries are allowed for security reasons."
            
        return f"[RDS Skeleton] Successfully connected to RDS database '{db_identifier}' and executed: '{query}'\nResult: 5 rows found."
