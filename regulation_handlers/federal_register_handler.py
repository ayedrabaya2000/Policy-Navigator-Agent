from handlers.handler_base import QueryHandler
from tools.federal_register_api_tools import query_federal_register_api

# Adapter for the Federal Register API (Adapter pattern)
class FederalRegisterHandler(QueryHandler):
    """
    Handles queries to the Federal Register API.
    Implements the Adapter pattern to unify the interface for query handling.
    """
    def run(self, query: str) -> str:
        """
        Query the Federal Register API and return the result.
        Args:
            query (str): The user's query.
        Returns:
            str: The API response.
        """
        resp = query_federal_register_api(query)
        return resp 