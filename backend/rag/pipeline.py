from .router import route
from .search import DBLPSearch


class RAGPipeline:
    def __init__(self):
        self.searcher = DBLPSearch()

    def retrieve(self, question: str, top_k: int = 8):
        decision = route(question)
        # For this first milestone, every non-analytical search uses BM25.
        # Dense retrieval and RRF will be added after lexical retrieval is verified.
        results = self.searcher.search(question, top_k=top_k)
        return decision["intent"], results
