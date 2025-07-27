from abc import ABC, abstractmethod

class QueryHandler(ABC):
    @abstractmethod
    def run(self, query: str) -> str:
        pass 