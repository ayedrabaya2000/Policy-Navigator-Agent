from handlers.handler_base import QueryHandler
from aixplain.factories import AgentFactory, IndexFactory

# Handler for EPA queries (Strategy pattern)
class EPAHandler(QueryHandler):
    """
    Handles queries related to EPA regulations using an agent.
    Implements the Strategy pattern for query handling.
    """
    def __init__(self):
        """
        Initializes the EPAHandler by creating an agent with the appropriate index.
        """
        index = self._get_index()
        self.agent = AgentFactory.create(
            name="EPA Agent",
            description="Answers queries about EPA regulations.",
            instructions="You answer questions about EPA regulations.",
            tools=[index] if index else []
        )

    def _get_index(self):
        """
        Finds and returns the EPA index from the available indexes.
        Returns:
            The index object if found, else None.
        """
        for idx in IndexFactory.list():
            if getattr(idx, 'name', None) == "EPA Index":
                return idx
        return None

    def run(self, query: str) -> str:
        """
        Runs the query using the agent.
        Args:
            query (str): The user's query.
        Returns:
            str: The agent's response.
        """
        response = self.agent.run(query)
        return response['data']['output'] 