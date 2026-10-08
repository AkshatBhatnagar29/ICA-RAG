# Context builder and the E1...E447 bug

## The distinction

- Candidate pool: recall-oriented dense/BM25/RRF/reranker inputs.
- Evidence registry: all authorized, deduplicated evidence retained for
  diagnostics and provenance bookkeeping.
- Generation evidence: selected registry entries authorized for this provider
  call.
- LLM context: rendered text/metadata for generation evidence only.

The fixed path is:

```text
candidate results -> EvidencePacket registry -> deterministic top 10
                  -> deduplicate -> 6000-token text budget -> LLM
```

`app/services/generation/context.py` assigns IDs to registry items, stores the
full registry in `registry_items`, and stores only selected items in `items` and
`context`. `selected_registry` is the citation authorization set.

Before the fix, `AgentService.run()` chose a contract-analysis packet and
`agents/synthesis.py` formatted every `contract_packet.items` item. Thus a
contract analysis yielding E1-E447 could put all 447 blocks in the provider
prompt; the ordinary path only enforced a token budget and had no independent
top-K. The fix applies `generation_top_k=10` immediately before context
construction, including multi-tool synthesis, preserves `E*`/`L*` namespaces,
and makes citation verification selected-only.

An oversized/insufficient selection returns a controlled result or bounded
failure; it never falls back to serializing the full registry. Safe diagnostics
include counts, estimated tokens, request byte size, and IDs sent, never full
contract/legal text or secrets.
