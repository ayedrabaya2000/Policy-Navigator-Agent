from handlers.handler_base import QueryHandler
from handlers.document_upload_handler import UploadIndexSingleton
from tools.aixplain_embedding_tools import aixplain_embed, aixplain_summarize
from typing import Optional

# Handler for querying uploaded documents (Strategy pattern)
class UploadedDocumentQueryHandler(QueryHandler):
    """
    Handles queries against uploaded documents using a vector index.
    Implements the Strategy pattern for query handling.
    """
    def __init__(self, upload_index: Optional[object] = None):
        """
        Args:
            upload_index (Optional[object]): Injected vector index for uploaded documents. Defaults to singleton.
        """
        self.upload_index = upload_index or UploadIndexSingleton.get_instance()

    def run(self, query: str) -> str:
        """
        Searches uploaded documents for relevant information and summarizes the results.
        Args:
            query (str): The user's query (may start with 'upload:' or 'uploaded:').
        Returns:
            str: Summarized relevant information or a not found message.
        """
        # Remove the 'upload:' or 'uploaded:' prefix if present
        q = query
        if q.lower().startswith('upload:'):
            q = q[len('upload:'):].strip()
        elif q.lower().startswith('uploaded:'):
            q = q[len('uploaded:'):].strip()
        embedding = aixplain_embed(q)
        retrieved = self.upload_index.query(q, embedding, top_k=2)
        if not retrieved:
            return "No relevant information found in uploaded documents."
        # Summarize the most relevant chunk(s) and include source reference
        answers = []
        for chunk in retrieved:
            summary = aixplain_summarize(chunk) or chunk[:300]
            answers.append(summary)
        return '\n\n'.join(answers) 