import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from regulation_vectorstore.vector_index import VectorIndex
from regulation_tools.federal_register_api_tools import query_federal_register_api
from regulation_tools.courtlistener_api_tools import query_caselaw_api
from regulation_tools.aixplain_embedding_tools import aixplain_embed, aixplain_summarize
from dotenv import load_dotenv
load_dotenv()
 
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
 
class PolicyNavigatorAgent:
    SYSTEM_PROMPT = """You are Policy Navigator Agent, an AI assistant specialized in answering questions related to government policies, regulations, compliance, and public health guidelines. When you receive a question, follow these steps:
 
1. Carefully analyze the question to understand the user's intent and specific context.
2. Select the most relevant data source: use CSVs for structured data, vector search for policy documents, and APIs for real-time information.
3. Retrieve accurate, relevant information using RAG methods.
4. Generate a clear, concise, and informative answer.
5. If the query is unclear, ask the user for clarification.
6. Always provide citations or references to data sources.
7. If no relevant data is found, explain that politely.
8. Avoid guessing or providing unsupported answers.
9. Maintain a professional, helpful, and neutral tone."""
 
    def __init__(self, vehicle_code_file: str = "data/vehicle_code.json"):
        self.index = VectorIndex()
        self.sections = []
        self.data_sources = {
            "federal_register": "Federal Register API",
            "caselaw": "CourtListener API",
            "vehicle_code": "Vehicle Code Database",
            "vector_search": "Policy Document Vector Database"
        }
        if vehicle_code_file and os.path.exists(vehicle_code_file):
            self.load_vehicle_code_json(vehicle_code_file)
        slack_token = os.environ.get("SLACK_TOKEN")
        slack_channel = os.environ.get("SLACK_CHANNEL")
        self.notifier = None
        if SlackNotifier and slack_token and slack_channel:
            self.notifier = SlackNotifier(slack_token, slack_channel)
 
    def embed(self, text: str) -> List[float]:
        vec = aixplain_embed(text)
        if vec:
            return vec
        return [float(ord(c)) for c in text[:384]] + [0.0]*(384-len(text))
 
    def load_vehicle_code_json(self, filepath: str) -> None:
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
            print(f"Error loading vehicle code JSON: {e}")
 
    def analyze_query_intent(self, query: str) -> Dict[str, any]:
        q = query.lower()
        intent = {
            "query_type": None,
            "data_source": None,
            "keywords": [],
            "entities": {},
            "requires_clarification": False,
            "context": {}
        }
        keywords = re.findall(r'\b\w+\b', q)
        intent["keywords"] = [kw for kw in keywords if len(kw) > 3]
        if any(x in q for x in ["executive order", "federal register", "regulation", "notices",
                               "clean air act", "public comments", "department of transportation",
                               "scheduled to take effect", "amendment"]):
            intent["query_type"] = "federal_regulation"
            intent["data_source"] = "federal_register"
        elif any(x in q for x in ["court", "case", "sued", "precedent", "litigation",
                                 "supreme court", "outcome", "v.", "section 230",
                                 "patriot act", "fair use", "fourth amendment"]):
            intent["query_type"] = "caselaw"
            intent["data_source"] = "caselaw"
        elif any(x in q for x in ["vehicle", "driving", "license", "traffic", "road",
                                 "section", "penalty", "fine", "violation"]):
            intent["query_type"] = "vehicle_code"
            intent["data_source"] = "vehicle_code"
        else:
            intent["query_type"] = "general_policy"
            intent["data_source"] = "vector_search"
        if len(query.strip().split()) <= 3:
            intent["requires_clarification"] = True
        return intent
 
    def search_vehicle_code(self, query: str) -> Optional[Dict]:
        match = re.search(r'section\s*(\d+[\w\.]*)', query, re.IGNORECASE)
        if match:
            sec = match.group(1)
            for entry in self.sections:
                if entry['section'] == sec:
                    return entry
        keywords = [
            "driving without a license", "unlicensed driver", "license required",
            "penalty", "penalties", "fine", "fines", "suspended license",
            "revoked license", "operating without a license", "valid license",
            "violation", "infraction"
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
 
    def format_response(self, content: str, data_source: str, query: str,
                       additional_info: Optional[Dict] = None) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response = f"""**Policy Navigator Agent Response**
 
{content}
 
**Data Source:** {self.data_sources.get(data_source, data_source)}
**Query Processed:** {query}
**Response Generated:** {timestamp}"""
        if additional_info:
            if "section" in additional_info:
                response += f"\n**Reference:** Section {additional_info['section']}"
            if "title" in additional_info:
                response += f"\n**Document Title:** {additional_info['title']}"
        return response
 
    def handle_query(self, query: str) -> str:
        try:
            intent = self.analyze_query_intent(query)
            if intent["requires_clarification"]:
                clarification_response = f"""I'd be happy to help you with your policy-related question. However, I need a bit more detail to provide you with the most accurate and relevant information.
 
Could you please provide more specific details about: '{query.strip()}'?
 
For example:
- What type of policy or regulation are you asking about?
- Are you looking for current requirements, recent changes, or historical information?
- What specific aspect or context are you interested in?
 
This will help me search the most appropriate data sources and provide you with a comprehensive answer."""
                if self.notifier:
                    self.notifier.send_message(f"Query: {query}\nResponse: [Clarification Request]")
                return clarification_response
            result = None
            data_source = intent["data_source"]
            additional_info = {}
            if data_source == "federal_register":
                result, additional_info = self._query_federal_register(query, intent)
            elif data_source == "caselaw":
                result, additional_info = self._query_caselaw(query, intent)
            elif data_source == "vehicle_code":
                result, additional_info = self._query_vehicle_code(query, intent)
            else:
                result, additional_info = self._query_vector_search(query, intent)
            if result:
                formatted_response = self.format_response(result, data_source, query, additional_info)
            else:
                formatted_response = f"""I've searched through our available policy and regulation databases, but I couldn't find specific information related to your query: "{query}"
 
**What I searched:**
- {', '.join([self.data_sources[ds] for ds in self.data_sources.keys()])}
 
**Suggestions:**
- Try rephrasing your question with more specific terms
- Check if you're looking for information from a specific time period
- Consider if the topic might be covered under different terminology
 
I'm here to help, so please feel free to ask your question in a different way or provide additional context."""
            if self.notifier:
                self.notifier.send_message(f"Query: {query}\nResponse: {formatted_response[:200]}...")
            return formatted_response
        except Exception as e:
            error_response = f"""I encountered an error while processing your query: "{query}"
 
**Error Details:** {str(e)}
 
**What you can do:**
- Try rephrasing your question
- Check if your query contains any special characters that might cause issues
- Contact support if the problem persists
 
I apologize for the inconvenience and am here to help once the issue is resolved."""
            if self.notifier:
                self.notifier.send_message(f"Query: {query}\nResponse: [Error] {str(e)}")
            return error_response
 
    def _query_federal_register(self, query: str, intent: Dict) -> Tuple[Optional[str], Dict]:
        q = query.lower()
        from_date, to_date, agency, doc_type = None, None, None, None
        if "last 30 days" in q:
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
        elif "next month" in q:
            from_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            to_date = (datetime.now() + timedelta(days=31)).strftime('%Y-%m-%d')
        elif "may 2025" in q:
            from_date = "2025-05-01"
            to_date = "2025-05-31"
        if "department of transportation" in q:
            agency = "Department of Transportation"
        elif "epa" in q or "environmental protection" in q:
            agency = "Environmental Protection Agency"
        if "public comments" in q:
            doc_type = "public_comment"
        elif "executive order" in q:
            doc_type = "executive_order"
        resp = query_federal_register_api(query, from_date, to_date, agency, doc_type, per_page=3)
        if resp:
            summary = aixplain_summarize(resp) or resp
            additional_info = {
                "source": "Federal Register",
                "date_range": f"{from_date} to {to_date}" if from_date and to_date else "Recent",
                "agency": agency or "Multiple"
            }
            return summary.strip(), additional_info
        return None, {}
 
    def _query_caselaw(self, query: str, intent: Dict) -> Tuple[Optional[str], Dict]:
        q = query.lower()
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
        resp = query_caselaw_api(query, statute=statute, party=party, keyword=keyword, per_page=3)
        if resp:
            summary = aixplain_summarize(resp) or resp
            additional_info = {
                "source": "CourtListener",
                "statute": statute,
                "party": party,
                "keyword": keyword
            }
            return summary.strip(), additional_info
        return None, {}
 
    def _query_vehicle_code(self, query: str, intent: Dict) -> Tuple[Optional[str], Dict]:
        entry = self.search_vehicle_code(query)
        if entry:
            summary = aixplain_summarize(entry['text']) or entry['text'][:500]
            additional_info = {
                "section": entry['section'],
                "title": entry['title'],
                "source": "Vehicle Code Database"
            }
            return summary.strip(), additional_info
        return None, {}
 
    def _query_vector_search(self, query: str, intent: Dict) -> Tuple[Optional[str], Dict]:
        embedding = self.embed(query)
        retrieved = self.index.query(query, embedding, top_k=3)
        if retrieved:
            context = "\n\n".join(retrieved)
            summary = aixplain_summarize(context) or context[:500]
            additional_info = {
                "source": "Policy Document Vector Database",
                "documents_retrieved": len(retrieved)
            }
            return summary.strip(), additional_info
        return None, {}
 
RAGAgent = PolicyNavigatorAgent
