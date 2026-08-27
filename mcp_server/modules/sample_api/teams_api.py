import os
import requests
import json


webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")

def send_teams(subject, body):

    total_body = {
        "type": "messageCard",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "msteams": {
                        "width": "Full"
                    },
                    "version": "1.2",
                    "body": body
                }
            }
        ]
    }

    url = webhook_url
    headers = {"Content-Type": "application/json"}
    json_data = json.dumps(total_body)
    response = requests.post(url, data=json_data, headers=headers)
    print(response.text)

    return response.text

