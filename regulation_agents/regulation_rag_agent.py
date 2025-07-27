import os
import json
import re
from datetime import datetime, timedelta
from vectorstore.vector_index import VectorIndex
from tools.federal_register_api import query_federal_register_api
from tools.caselaw_api import query_caselaw_api
from tools.aixplain_tools import aixplain_embed, aixplain_summarize
from dotenv import load_dotenv
load_dotenv()

# --- Slack Integration ---
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    class SlackNotifier:
        def __init__(self, token: str, channel: str):
            self.client = WebClient(token=token)
            self.channel = channel
        def send_message(self, text: str):
            try:
                self.client.chat_postMessage(channel=self.channel, text=text)
            except SlackApiError as e:
                print(f"Slack API error: {e.response['error']}")
except ImportError:
    SlackNotifier = None

class RAGAgent:
    def __init__(self, vehicle_code_file: str = "data/vehicle_code.json"):
        self.index = VectorIndex()
        self.sections = []
        if vehicle_code_file and os.path.exists(vehicle_code_file):
            self.load_vehicle_code_json(vehicle_code_file)
        # Slack integration
        slack_token = os.environ.get("SLACK_TOKEN")
        slack_channel = os.environ.get("SLACK_CHANNEL")
        self.notifier = None
        if SlackNotifier and slack_token and slack_channel:
            self.notifier = SlackNotifier(slack_token, slack_channel)
    def embed(self, text):
        vec = aixplain_embed(text)
        if vec:
            return vec
        return [float(ord(c)) for c in text[:384]] + [0.0]*(384-len(text))
    def load_vehicle_code_json(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for entry in data:
                section = entry.get('section', '')
                title = entry.get('title', '')
                text = entry.get('text', '')
                doc = f"Section {section}: {title}\n{text}"
                embedding = self.embed(doc)
                self.index.add_document(doc, embedding)
                self.sections.append({"section": section, "title": title, "text": text})
        except Exception as e:
            print(f"Error loading commercial code JSON: {e}")
    def search_vehicle_code(self, query):
        match = re.search(r'section\s*(\d+[\w\.]*)', query, re.IGNORECASE)
        if match:
            sec = match.group(1)
            for entry in self.sections:
                if entry['section'] == sec:
                    return entry
        keywords = [
            "driving without a license", "unlicensed driver", "license required", "penalty", "penalties", "fine", "fines", "suspended license", "revoked license", "operating without a license", "valid license", "violation", "infraction"
        ]
        ql = query.lower()
        for entry in self.sections:
            text = entry['text'].lower()
            if any(kw in text for kw in keywords) or any(kw in ql for kw in text.split()):
                return entry
        for entry in self.sections:
            if query.lower() in entry['text'].lower() or query.lower() in entry['title'].lower():
                return entry
        return None
    def handle_query(self, query: str) -> str:
        try:
            result = None
            q = query.lower()
            if any(x in q for x in ["executive order", "federal register", "regulation", "notices", "clean air act", "public comments", "department of transportation", "scheduled to take effect", "amendment"]):
                from_date, to_date, agency, doc_type = None, None, None, None
                if "last 30 days" in q:
                    from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                    to_date = datetime.now().strftime('%Y-%m-%d')
                if "next month" in q:
                    from_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                    to_date = (datetime.now() + timedelta(days=31)).strftime('%Y-%m-%d')
                if "may 2025" in q:
                    from_date = "2025-05-01"
                    to_date = "2025-05-31"
                if "department of transportation" in q:
                    agency = "Department of Transportation"
                if "public comments" in q:
                    doc_type = "public_comment"
                resp = query_federal_register_api(query, from_date, to_date, agency, doc_type, per_page=1)
                summary = aixplain_summarize(resp) or resp
                result = summary.strip()
                if self.notifier:
                    self.notifier.send_message(f"Query: {query}\nResponse: {result}")
                return result
            if any(x in q for x in ["court", "case", "sued", "precedent", "litigation", "supreme court", "outcome", "v.", "amendment", "section 230", "patriot act", "fair use", "roommates.com", "fourth amendment"]):
                party = None
                statute = None
                keyword = None
                match = re.search(r'section\s*(\d+[\w\.]*)', query, re.IGNORECASE)
                if match:
                    statute = match.group(1)
                match = re.search(r'v\.\s*([\w\.]+)', query, re.IGNORECASE)
                if match:
                    party = match.group(1)
                if "uber" in q:
                    party = "Uber"
                if "fair use" in q:
                    keyword = "fair use"
                if "patriot act" in q:
                    statute = "Patriot Act"
                if "climate change" in q:
                    keyword = "climate change"
                resp = query_caselaw_api(query, statute=statute, party=party, keyword=keyword, per_page=1)
                summary = aixplain_summarize(resp) or resp
                result = summary.strip()
                if self.notifier:
                    self.notifier.send_message(f"Query: {query}\nResponse: {result}")
                return result
            entry = self.search_vehicle_code(query)
            if entry:
                summary = aixplain_summarize(entry['text']) or entry['text'][:300]
                result = summary.strip()
                if self.notifier:
                    self.notifier.send_message(f"Query: {query}\nResponse: {result}")
                return result
            embedding = self.embed(query)
            retrieved = self.index.query(query, embedding, top_k=1)
            if retrieved:
                context = retrieved[0]
                summary = aixplain_summarize(context) or context
                result = summary.strip()
                if self.notifier:
                    self.notifier.send_message(f"Query: {query}\nResponse: {result}")
                return result
            # Dynamic conversational fallback
            if len(query.strip().split()) <= 3:
                result = f"Could you please provide more details about '{query.strip()}'? I'm here to help!"
            elif '?' in query:
                result = f"That's a great question! I couldn't find a direct answer, but let's explore it together: '{query.strip()}'"
            else:
                result = f"I couldn't find relevant information for: '{query.strip()}'. Could you clarify or ask in a different way?"
            if self.notifier:
                self.notifier.send_message(f"Query: {query}\nResponse: {result}")
            return result
        except Exception as e:
            result = f"[Error] {e}"
            if self.notifier:
                self.notifier.send_message(f"Query: {query}\nResponse: {result}")
            return result 