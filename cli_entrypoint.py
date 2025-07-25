"""
Main CLI entry point for the Multi-Agent RAG System for Government Regulation Search.
Handles user interaction, agent setup, Slack integration, and command routing.
"""
from aixplain.factories import AgentFactory, TeamAgentFactory, IndexFactory
from rich.console import Console
import requests
from dotenv import load_dotenv
load_dotenv()

import os
from regulation_query_facade import PolicyNavigatorFacade

# --- Slack Integration ---
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    class SlackNotifier:
        """
        Sends messages to a Slack channel using a bot token.
        """
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

# --- Tool Functions ---
def federal_register_tool(query):
    """
    Query the Federal Register API for the latest document matching the query.
    Returns a summary string or error message.
    """
    url = "https://www.federalregister.gov/api/v1/documents.json"
    params = {"per_page": 1, "order": "newest", "conditions[term]": query}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        results = data.get("results", [])
        if results:
            doc = results[0]
            title = doc.get("title", "")
            summary = doc.get("abstract", "No summary available.")
            pub_date = doc.get("publication_date", "?")
            return f"{title} (Published: {pub_date}): {summary}"
        else:
            return "No relevant federal register documents found."
    except Exception as e:
        return f"Federal Register: Error fetching data: {e}"

def courtlistener_tool(query):
    """
    (Deprecated) Query the CourtListener API for a relevant opinion. Kept for reference.
    """
    import time
    url = "https://www.courtlistener.com/api/rest/v3/opinions/"
    params = {"search": query, "page_size": 1}
    headers = {'Authorization': 'Token b84fd8d15e3969573f5f1de7ced3f88288e70c95'}
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            data = resp.json()
            results = data.get('results', [])
            if results:
                opinion = results[0]
                case_name = (
                    opinion.get('caseName') or
                    opinion.get('case_name') or
                    opinion.get('name_abbreviation') or
                    "Unknown Case"
                )
                cite = (
                    opinion.get('cite') or
                    (opinion.get('citations') and opinion.get('citations')[0].get('cite')) or
                    "No citation"
                )
                summary = opinion.get('summary') or opinion.get('headnotes')
                if summary:
                    summary = summary.strip().replace('\n', ' ')
                else:
                    plain_text = opinion.get('plain_text', '').strip()
                    if plain_text:
                        paragraphs = [p.strip() for p in plain_text.split('\n') if p.strip()]
                        summary = None
                        for p in paragraphs:
                            if len(p) > 40 and not p.lower().startswith((
                                'filed', 'court', 'state of', 'appeal', 'supreme', 'district', 'county', 'judge',
                                'panel', 'date', 'before', 'argued', 'decided', 'counsel', 'attorney', 'prosecutor',
                                'defendant', 'plaintiff', 'appellant', 'appellee', 'respondent', 'petitioner', 'brief',
                                'syllabus', 'headnote')):
                                summary = p
                                break
                        if not summary:
                            summary = paragraphs[0] if paragraphs else '[No summary available]'
                    else:
                        summary = '[No summary available]'
                return f"{case_name} ({cite}): {summary}"
            else:
                return "No relevant court opinions found."
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                return "CourtListener: Error fetching data: Request timed out after multiple attempts. Please try again later."
        except Exception as e:
            return f"CourtListener: Error fetching data: {e}"

# --- Index and Agent Setup ---
def get_index_by_name(index_name, retries=5, delay=2):
    """
    Utility to find an index by name, with retries.
    """
    from time import sleep
    for attempt in range(retries):
        indexes = IndexFactory.list()
        for idx in indexes:
            if getattr(idx, 'name', None) == index_name:
                return idx
        if attempt < retries - 1:
            print(f"[INFO] Index '{index_name}' not found, retrying in {delay} seconds...")
            sleep(delay)
    print(f"[ERROR] Index '{index_name}' not found after {retries} retries.")
    return None

# Create agents for each regulation domain
vehicle_code_index = get_index_by_name("Vehicle Code Index")
epa_index = get_index_by_name("EPA Index")

vehicle_code_agent = AgentFactory.create(
    name="Vehicle Code Agent",
    description="Answers queries about the Vehicle Code dataset.",
    instructions="You answer questions about the Vehicle Code.",
    tools=[vehicle_code_index] if vehicle_code_index else []
)
epa_agent = AgentFactory.create(
    name="EPA Agent",
    description="Answers queries about EPA regulations.",
    instructions="You answer questions about EPA regulations.",
    tools=[epa_index] if epa_index else []
)
team_agent = TeamAgentFactory.create(
    name="Policy Navigator Agent",
    description="Agentic RAG System for Government Regulation Search",
    instructions="Extract insights from regulations, policies, and public health guidelines.",
    agents=[vehicle_code_agent, epa_agent]
)

# --- Command Pattern Implementation ---
class QueryCommand:
    """
    Abstract base class for all query commands.
    """
    def execute(self, query, console):
        raise NotImplementedError

class VehicleCodeCommand(QueryCommand):
    """
    Command for querying the Vehicle Code agent.
    """
    def __init__(self, agent):
        self.agent = agent
    def execute(self, query, console):
        response = self.agent.run(query)
        console.print(f"[green]Vehicle Code Agent response:[/green]\n{response['data']['output']}")
        return response['data']['output']

class EPACommand(QueryCommand):
    """
    Command for querying the EPA agent.
    """
    def __init__(self, agent):
        self.agent = agent
    def execute(self, query, console):
        response = self.agent.run(query)
        console.print(f"[green]EPA Agent response:[/green]\n{response['data']['output']}")
        return response['data']['output']

class FederalRegisterCommand(QueryCommand):
    """
    Command for querying the Federal Register tool.
    """
    def execute(self, query, console):
        result = federal_register_tool(query)
        console.print(f"[green]Federal Register Tool response:[/green]\n{result}")
        return result

class CourtListenerCommand(QueryCommand):
    """
    Command for querying the CourtListener handler via the facade.
    """
    def __init__(self, facade):
        self.facade = facade
    def execute(self, query, console):
        result = self.facade.handle_query("courtlistener: " + query)
        console.print(f"[green]CourtListener Tool response:[/green]\n{result}")
        return result

# --- Main Application ---
def main():
    """
    Main CLI loop for user interaction, command routing, and Slack notification.
    """
    print("Slack token:", os.environ.get("SLACK_TOKEN"))
    print("Slack channel:", os.environ.get("SLACK_CHANNEL"))
    console = Console()
    facade = PolicyNavigatorFacade()  # Facade provides a unified interface to all agents/tools
    console.print("[bold green]Welcome to the Agentic RAG System![/bold green]")

    # Initialize SlackNotifier if configured
    slack_notifier = None
    slack_token = os.environ.get("SLACK_TOKEN")
    slack_channel = os.environ.get("SLACK_CHANNEL")
    if SlackNotifier and slack_token and slack_channel:
        slack_notifier = SlackNotifier(slack_token, slack_channel)

    # Command registry for menu options
    commands = {
        "1": VehicleCodeCommand(vehicle_code_agent),
        "2": EPACommand(epa_agent),
        "3": FederalRegisterCommand(),
        "4": CourtListenerCommand(facade),
    }

    while True:
        # Show menu and get user choice
        console.print("\n[bold yellow]Select query type:[/bold yellow]\n1. Vehicle Code\n2. EPA\n3. Federal Register\n4. CourtListener\n5. Exit")
        choice = console.input("[bold blue]Enter choice (1-5): [/bold blue]")
        if choice == "5" or choice.lower() == "exit":
            break
        if choice not in commands:
            console.print("[red]Invalid choice. Please select 1-5.[/red]")
            continue
        query = console.input("[bold blue]Enter your query: [/bold blue]")
        try:
            response = commands[choice].execute(query, console)
            # Post to Slack if configured
            if slack_notifier:
                try:
                    slack_notifier.send_message(f"Query: {query}\nResponse: {response}")
                except Exception as e:
                    console.print(f"[yellow]Warning: Failed to post to Slack: {e}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    main() 