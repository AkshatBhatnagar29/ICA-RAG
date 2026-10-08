class ApplicationError(Exception):
    """Base class for expected application failures."""

    status_code = 500
    code = "application_error"


class DependencyUnavailableError(ApplicationError):
    status_code = 503
    code = "dependency_unavailable"

    def __init__(self, dependency: str) -> None:
        self.dependency = dependency
        super().__init__(f"{dependency} is unavailable")


class DocumentValidationError(ApplicationError):
    status_code = 400
    code = "invalid_document"


class DuplicateDocumentError(ApplicationError):
    status_code = 409
    code = "duplicate_document_version"


class StorageError(ApplicationError):
    status_code = 500
    code = "storage_error"


class DocumentProcessingError(ApplicationError):
    status_code = 422
    code = "document_processing_failed"


class UnsupportedDocumentType(DocumentProcessingError):
    code = "unsupported_document_type"


class DocumentParseError(DocumentProcessingError):
    code = "document_parse_failed"


class OCRProcessingError(DocumentProcessingError):
    code = "ocr_processing_failed"


class GenerationError(ApplicationError):
    status_code = 502
    code = "generation_failed"


class GenerationConfigurationError(GenerationError):
    status_code = 503
    code = "generation_not_configured"


class GenerationRateLimitError(GenerationError):
    status_code = 429
    code = "generation_rate_limited"


class GenerationTimeoutError(GenerationError):
    status_code = 504
    code = "generation_timeout"


class GenerationCitationError(GenerationError):
    code = "invalid_citations"


class GenerationOutputValidationError(GenerationError):
    code = "invalid_generation_output"
