from handlers.handler_base import QueryHandler
from tools.courtlistener_api_tools import query_caselaw_api

class CourtListenerHandler(QueryHandler):
    """
    Handles queries to the CourtListener API for case law search and summarization.
    Implements the Strategy pattern for query handling.
    """
    def run(self, query: str) -> str:
        """
        Query the CourtListener API for relevant case law.
        Args:
            query (str): The user's query.
        Returns:
            str: Summaries of relevant court opinions or error message.
        """
        return query_caselaw_api(query) 