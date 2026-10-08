# Evidence and citation validation

Contract evidence uses `E1`, `E2`, ...; legal retrieval uses `L1`, `L2`, ...;
comparison can preserve `S-` and `T-` prefixes. IDs are application-assigned,
not model-invented. An ID's shape is never sufficient proof.

```text
authorized evidence -> registry -> selected generation context -> LLM IDs
                    -> Pydantic shape -> selected-ID/provenance verifier
                    -> accepted authoritative metadata or fail closed
```

`verify_citations()` rejects unknown-to-selected, duplicate IDs. It returns
metadata from the `EvidenceItem`, not model-supplied metadata. Legal validation
also checks source type, optional source citation, optional quote containment,
and evidence-gate requirements. Tenant/document/version scope was checked before
the evidence entered this path.

The recent bug matters here: a registry may contain E447 for diagnostics, but if
E447 was not in the prompt, accepting it would allow unsupported citation claims.
The selected-only registry prevents that attack while retaining full registry
bookkeeping.
