# Concept map

```text
HTTP -> FastAPI -> dependency injection -> AuthContext -> tenant scope
     -> service -> SQLAlchemy session/transaction -> response model

tokenization -> BM25 -> lexical rank
text -> E5 tokenizer/model -> 384D vector -> cosine distance -> dense rank
dense rank + BM25 rank -> RRF(k=60) -> candidate pool
candidate (query, chunk) -> cross-encoder score -> reranked evidence
evidence registry -> selected generation evidence -> bounded prompt -> LLM
LLM JSON -> Pydantic -> selected-ID citation validation -> response

processed pages -> structural units -> clause/subclause chunks
             -> hashes/provenance -> embedding/index row

typed request -> planner -> typed steps -> bounded tools -> evidence
             -> mixed synthesis -> namespace-specific validators
```

Prerequisite traps: cosine similarity is not BM25; RRF combines ranks rather
than raw scores; reranking reorders existing candidates; an evidence registry
is not the same thing as generation context; LLM citations are claims to be
checked, not proof.
