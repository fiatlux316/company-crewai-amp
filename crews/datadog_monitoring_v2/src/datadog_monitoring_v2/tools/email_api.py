import os
import smtplib
from email.mime.text import MIMEText
import markdown  # 👈 설치한 마크다운 라이브러리 임포트

def _markdown_to_html(markdown_content):
    content = markdown_content.strip()
    lines = content.splitlines()
    if lines and lines[0].strip().lower() in ("```", "```markdown") and lines[-1].strip() == "```":
        content = "\n".join(lines[1:-1])

    return markdown.markdown(
        content,
        extensions=["tables", "fenced_code"],
    )


def send_outlook_email(subject, markdown_content, to_email):

    sender_email = os.environ.get("OUTLOOK_EMAIL")
    sender_password = os.environ.get("OUTLOOK_PASSWORD")

    print("sender_email", sender_email)
    print("sender_password", sender_password)

    # 1. 마크다운 내용을 HTML 코드로 변환
    raw_html = _markdown_to_html(markdown_content)
    
    # 2. 이메일에서 예쁘게 보이도록 디자인(CSS) 입히기 (옵션)
    styled_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333333; }}
            h1 {{ color: #1f4e78; border-bottom: 2px solid #1f4e78; padding-bottom: 5px; }}
            h2 {{ color: #2e75b6; border-bottom: 1px solid #d9d9d9; padding-bottom: 5px; }}
            h3 {{ color: #595959; }}
            p {{ margin: 10px 0; }}
            strong {{ color: #c00000; }}
            ul, ol {{ padding-left: 20px; }}
            li {{ margin-bottom: 5px; }}
            code {{ background-color: #f2f2f2; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
            pre {{ background-color: #f2f2f2; padding: 10px; border-radius: 5px; overflow-x: auto; }}
            table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
            th, td {{ border: 1px solid #d9d9d9; padding: 8px 10px; text-align: left; vertical-align: top; }}
            th {{ background-color: #1f4e78; color: #ffffff; font-weight: bold; }}
            tr:nth-child(even) {{ background-color: #f7f9fb; }}
        </style>
    </head>
    <body>
        {raw_html}
    </body>
    </html>
    """

    # 1. 아웃룩(Office 365) 공식 SMTP 설정
    smtp_server = "email.shinsegae.com"
    port = 25
    
    # ⚠️ 중요: 세 번째 인자를 "plain" 대신 "html"로 작성합니다.
    msg = MIMEText(styled_html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        # 2. 아웃룩 서버는 반드시 STARTTLS 연결이 필요합니다.
        server = smtplib.SMTP(smtp_server, port)
        server.ehlo()
        server.starttls()  # TLS 보안 연결 활성화
        server.ehlo()
        
        # 3. 로그인 및 발송
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.close()
        print("아웃룩 메일 발송 성공!")
        return "아웃룩 메일 발송 성공!"
    except Exception as e:
        print(f"아웃룩 메일 발송 실패: {e}")
        return f"아웃룩 메일 발송 실패: {e}"


def send_google_email(subject, markdown_content, to_email):

    google_sender_email = os.environ.get("GOOGLE_EMAIL")
    google_sender_password = os.environ.get("GOOGLE_PASSWORD")

    print("google_sender_email", google_sender_email)
    print("google_sender_password", google_sender_password)
    print("to_email", to_email)

    # 1. 마크다운 내용을 HTML 코드로 변환
    raw_html = _markdown_to_html(markdown_content)
    
    # 2. 이메일에서 예쁘게 보이도록 디자인(CSS) 입히기 (옵션)
    styled_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333333; }}
            h1 {{ color: #1f4e78; border-bottom: 2px solid #1f4e78; padding-bottom: 5px; }}
            h2 {{ color: #2e75b6; border-bottom: 1px solid #d9d9d9; padding-bottom: 5px; }}
            h3 {{ color: #595959; }}
            p {{ margin: 10px 0; }}
            strong {{ color: #c00000; }}
            ul, ol {{ padding-left: 20px; }}
            li {{ margin-bottom: 5px; }}
            code {{ background-color: #f2f2f2; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
            pre {{ background-color: #f2f2f2; padding: 10px; border-radius: 5px; overflow-x: auto; }}
            table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
            th, td {{ border: 1px solid #d9d9d9; padding: 8px 10px; text-align: left; vertical-align: top; }}
            th {{ background-color: #1f4e78; color: #ffffff; font-weight: bold; }}
            tr:nth-child(even) {{ background-color: #f7f9fb; }}
        </style>
    </head>
    <body>
        {raw_html}
    </body>
    </html>
    """

    # SMTP 설정 (예: Gmail 기준)
    smtp_server = "smtp.gmail.com"
    port = 587

    # ⚠️ 중요: 세 번째 인자를 "plain" 대신 "html"로 작성합니다.
    msg = MIMEText(styled_html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = google_sender_email
    msg["To"] = to_email
    try:
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()  # 보안 연결 시작
            server.login(google_sender_email, google_sender_password)
            server.sendmail(google_sender_email, to_email, msg.as_string())
        print("이메일 발송 성공!")
        return "이메일 발송 성공!"
    except Exception as e:
        print(f"이메일 발송 실패: {e}")
        return f"이메일 발송 실패: {e}"