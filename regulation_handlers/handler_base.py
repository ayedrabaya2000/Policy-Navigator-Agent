from abc import ABC, abstractmethod

# Abstract base class for all query handlers (Strategy pattern)
class QueryHandler(ABC):
    """
    Abstract base class for all query handlers.
    Implements the Strategy pattern for query handling.
    """
    @abstractmethod
    def run(self, query: str) -> str:
        """
        Abstract method to run a query.
        Args:
            query (str): The user's query.
        Returns:
            str: The handler's response.
        """
        pass 