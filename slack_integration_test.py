import os
from slack_sdk import WebClient
from dotenv import load_dotenv
load_dotenv()

token = os.environ.get("SLACK_TOKEN")
channel = os.environ.get("SLACK_CHANNEL")

if not token or not channel:
    print("SLACK_TOKEN or SLACK_CHANNEL not set.")
else:
    client = WebClient(token=token)
    try:
        response = client.chat_postMessage(channel=channel, text="Test message from script")
        print("Message sent! Response:", response)
    except Exception as e:
        print("Slack API error:", e) 