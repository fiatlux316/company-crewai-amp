def register(mcp):
    @mcp.tool
    def list_bitbucket_repositories(project_key: str) -> str:
        """
        Lists repositories in a specific Bitbucket project.
        
        Args:
            project_key: Key of the Bitbucket project (e.g. 'PROJ')
        """
        return f"[Bitbucket Skeleton] Repositories under project '{project_key}': ['auth-service', 'payment-gateway', 'monitoring-infra']"

    @mcp.tool
    def create_bitbucket_pull_request(repo_slug: str, title: str, source_branch: str, destination_branch: str) -> str:
        """
        Creates a new Pull Request in Bitbucket.
        
        Args:
            repo_slug: Repository identifier slug (e.g. 'auth-service')
            title: Title of the PR
            source_branch: Source branch name (e.g. 'feature/monitoring')
            destination_branch: Target branch name (e.g. 'main')
        """
        return f"[Bitbucket Skeleton] PR '{title}' created successfully: {source_branch} -> {destination_branch} in repo '{repo_slug}'."
