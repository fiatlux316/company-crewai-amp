import os

def register(mcp):
    @mcp.tool
    def create_jira_issue(project_key: str, summary: str, description: str, issue_type: str = "Task") -> str:
        """
        Creates a new issue in Jira.
        
        Args:
            project_key: Key of the Jira project (e.g., 'PROJ')
            summary: Short summary or title of the issue
            description: Detailed description of the issue
            issue_type: Type of issue (e.g., 'Bug', 'Task', 'Story')
        """
        jira_url = os.environ.get("JIRA_URL", "https://jira.example.com")
        return f"[Jira Skeleton] Successfully created {issue_type} in project '{project_key}' at {jira_url}. Summary: {summary}"

    @mcp.tool
    def get_jira_issue(issue_key: str) -> str:
        """
        Retrieves details of a Jira issue by its key.
        
        Args:
            issue_key: The issue key (e.g., 'PROJ-123')
        """
        return f"[Jira Skeleton] Retrieved issue {issue_key}: Summary = 'Sample Issue', Status = 'In Progress'"
