import os
import sys

def register(mcp):
    teams_api = None
    
    try:
        from .sample_api import teams_api as api
        teams_api = api
    except ImportError:
        try:
            from sample_api import teams_api as api
            teams_api = api
        except ImportError:
            pass

    if teams_api is None:
        print("Error: Could not import teams_api in teams_service.py", file=sys.stderr)
        return

    @mcp.tool
    def send_teams_message(subject: str, body: str) -> str:
        """
        Sends a message using Teams webhook.
        """
        return teams_api.send_teams_message(subject, body)