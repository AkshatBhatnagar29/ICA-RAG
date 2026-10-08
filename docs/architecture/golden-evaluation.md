# Golden RAG evaluation

The production golden evaluator exercises the existing Ask ICIA `AgentService`
directly. It does not replace retrieval, reranking, generation, legal
retrieval, or citation validation with test doubles. Contract and legal
evidence remain separate and all application tenant scoping is preserved.

Start the development services, ensure the standard agreement has been
processed and indexed, and configure the existing provider in `.env`:

```text
docker compose up -d
uv run python scripts/run_golden_eval.py
```

The upload smoke test uses the checked-in source PDF automatically:

```text
$env:ICIA_SMOKE_EMAIL="..."
$env:ICIA_SMOKE_PASSWORD="..."
uv run python scripts/smoke_mvp.py
```

Its default file is
`data/raw/contracts/icat-version1/PDFs/PDFs/Standard-agreement.pdf`; set
`ICIA_SMOKE_FILE` to upload a different document.

The runner discovers a READY version whose filename matches
`Standard-agreement.pdf`. If discovery is ambiguous, pass
`--document-version-id` and `--tenant-id`. Legal cases use the newest legal
corpus version unless `--corpus-version-id` is supplied.

Useful options:

```text
uv run python scripts/run_golden_eval.py --case SA-001
uv run python scripts/run_golden_eval.py --limit 5
uv run python scripts/run_golden_eval.py --dataset data/evaluation/golden/standard_agreement_v1.json
uv run python scripts/run_golden_eval.py --no-llm --case SA-001
```

Each run writes timestamped JSON, Markdown, and CSV reports and refreshes
`data/evaluation/results/latest.json`. `--no-llm` intentionally exercises the
real retrieval path while recording generation as unavailable; it must not be
interpreted as a successful end-to-end generation result. Provider failures
are recorded per case as `ERROR`.
