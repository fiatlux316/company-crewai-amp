def register(mcp):
    @mcp.tool
    def create_confluence_page(space_key: str, title: str, body_content: str, parent_page_id: str = None) -> str:
        """
        Creates a new wiki page in Confluence.
        
        Args:
            space_key: Space key of Confluence (e.g. 'DEVOPS')
            title: Title of the page
            body_content: Content of the page
            parent_page_id: Optional ID of the parent page
        """
        return f"[Confluence Skeleton] Created page '{title}' in space '{space_key}' with body size {len(body_content)} bytes."

    @mcp.tool
    def search_confluence(query: str) -> str:
        """
        Searches Confluence content.
        
        Args:
            query: Confluence search query string
        """
        return f"[Confluence Skeleton] Search results for '{query}': ['Deployment Guide 2026', 'Monitoring Runbooks', 'Incident Report Template']"
