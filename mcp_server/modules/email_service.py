import os
import sys

def register(mcp):
    email_api = None
    
    try:
        from .sample_api import email_api as api
        email_api = api
    except ImportError:
        try:
            from sample_api import email_api as api
            email_api = api
        except ImportError:
            pass

    if email_api is None:
        print("Error: Could not import email_api in email_service.py", file=sys.stderr)
        return

    @mcp.tool
    def send_outlook_email(subject: str, markdown_content: str, to_email: str = None) -> str:
        """
        Sends an email using Outlook SMTP server.
        Converts markdown content to formatted HTML with styling before sending.
        If to_email is not provided, it defaults to the configured RECIPIENT_EMAIL environment variable.
        """
        recipient = to_email or os.environ.get("RECIPIENT_EMAIL", "").strip()
        if not recipient:
            return "Fail: RECIPIENT_EMAIL environment variable is not set and to_email was not provided."
        return email_api.send_outlook_email(subject, markdown_content, recipient)

    @mcp.tool
    def send_google_email(subject: str, markdown_content: str, to_email: str = None) -> str:
        """
        Sends an email using Google SMTP server (Gmail).
        Converts markdown content to formatted HTML with styling before sending.
        If to_email is not provided, it defaults to the configured RECIPIENT_EMAIL environment variable.
        """
        recipient = to_email or os.environ.get("RECIPIENT_EMAIL", "").strip()
        if not recipient:
            return "Fail: RECIPIENT_EMAIL environment variable is not set and to_email was not provided."
        return email_api.send_google_email(subject, markdown_content, recipient)
