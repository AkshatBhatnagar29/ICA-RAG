# ICIA dependency graph

```text
FastAPI/Uvicorn
  -> app.main lifespan
     -> Settings / ResourceManager / providers
  -> endpoint dependency
     -> AuthContext + permission
     -> service
        -> SQLAlchemy models/repositories -> PostgreSQL
        -> object storage
        -> RetrievalService
           -> LocalE5EmbeddingProvider -> FastEmbed/ONNX
           -> LocalBM25
           -> reciprocal_rank_fusion (RRF)
           -> LocalCrossEncoderReranker -> FastEmbed/ONNX
        -> context builder
        -> LLMProvider -> Groq HTTP API
        -> Pydantic output -> citation/evidence verifier
```

```text
Upload endpoint
  -> upload_document
  -> DocumentProcessingPipeline
     -> PDF/DOCX parser -> ProcessedDocument
  -> IndexingService
     -> HierarchicalChunker -> ChunkDraft
     -> E5 provider -> Chunk.embedding
     -> PostgreSQL/pgvector READY row
```

```text
AgentService
  -> build_plan/router
  -> AgentExecutor/ToolRegistry
     -> contract_search / contract_analysis / comparison / legal_search
  -> evidence registry
  -> bounded synthesis
  -> contract citation verifier + legal citation verifier
```

The dependency direction is intentionally application-owned: providers satisfy
small protocols, while services decide authorization, ordering, and failure
semantics. There is no LangChain/LlamaIndex orchestration layer.
