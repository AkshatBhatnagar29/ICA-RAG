from __future__ import annotations

import re
import unicodedata

from app.services.retrieval.models import RetrievalScope


class InvalidRetrievalQuery(ValueError):
    pass


class QueryProcessor:
    def __init__(self, max_length: int = 4000) -> None:
        self.max_length = max_length

    def normalize(self, query: str) -> str:
        if not isinstance(query, str):
            raise InvalidRetrievalQuery("query must be text")
        normalized = unicodedata.normalize("NFC", query)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            raise InvalidRetrievalQuery("query must not be empty")
        if len(normalized) > self.max_length:
            raise InvalidRetrievalQuery(f"query exceeds {self.max_length} characters")
        return normalized

    @staticmethod
    def validate_scope(scope: RetrievalScope) -> RetrievalScope:
        if scope.tenant_id is None:
            raise PermissionError("tenant scope is required for retrieval")
        return scope

