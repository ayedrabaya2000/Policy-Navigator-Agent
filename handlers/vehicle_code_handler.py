from handlers.handler_base import QueryHandler
from aixplain.factories import AgentFactory, IndexFactory

# Handler for Vehicle Code queries (Strategy pattern)
class VehicleCodeHandler(QueryHandler):
    """
    Handles queries related to the Vehicle Code dataset using an agent.
    Implements the Strategy pattern for query handling.
    """
    def __init__(self):
        """
        Initializes the VehicleCodeHandler by creating an agent with the appropriate index.
        """
        index = self._get_index()
        self.agent = AgentFactory.create(
            name="Vehicle Code Agent",
            description="Answers queries about the Vehicle Code dataset.",
            instructions="You answer questions about the Vehicle Code.",
            tools=[index] if index else []
        )

    def _get_index(self):
        """
        Finds and returns the Vehicle Code index from the available indexes.
        Returns:
            The index object if found, else None.
        """
        for idx in IndexFactory.list():
            if getattr(idx, 'name', None) == "Vehicle Code Index":
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