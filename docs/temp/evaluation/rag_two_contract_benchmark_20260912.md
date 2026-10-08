# Two-contract retrieval benchmark — 2026-09-12

The frozen retrieval configuration was evaluated against the canonical
Standard-agreement.pdf and a second real contract/tender artifact from the
official Ministry of External Affairs source. No model, chunk threshold, RRF
parameter, candidate size, LLM, or production retrieval implementation was
changed.

## Contract #2 acquisition and ingestion

The source was downloaded from the official MEA URL:

`https://www.mea.gov.in/Portal/Tender/3768_1/1_PBK_IFMC_Tender_Document-1.pdf`

Acquisition details are in
[`pbk_ifmc_acquisition_report.json`](../../data/evaluation/results/pbk_ifmc_acquisition_report.json).
The artifact is stored at
`data/raw/contracts/pbk_ifmc/1_PBK_IFMC_Tender_Document-1.pdf`, with SHA-256
`7f4a8ccc63ed80739b017884676b5c0c2796734a04969e9334cf5c26696604e7` and size
804,820 bytes.

The PDF was ingested through the existing upload, processing, structure
detection, chunking, embedding, and pgvector path. The parser required a small
compatibility fix for empty PDF block records; no chunking behavior or setting
was changed. The resulting immutable identities are:

- document: `91ae1b03-3ac9-4f07-ab67-59c1dae4d1b1`
- document version: `27077304-3640-46f0-84e5-7c26de4fc368`
- tenant: `49503852-ecd4-511d-97e7-a18db98aee5c`

The version is READY with 51 pages, 669 chunks, 669 embeddings, and 669
verified pgvector rows. Full details are in
[`pbk_ifmc_ingestion_report.json`](../../data/evaluation/results/pbk_ifmc_ingestion_report.json).

## Contract #2 dataset and validation

[`pbk_ifmc_v1.json`](../../data/evaluation/golden/pbk_ifmc_v1.json) contains 36
cases: 33 retrieval-applicable cases and three insufficient-evidence cases.
It covers the supported factual, obligation, payment, termination, renewal,
scope, service-level, penalty, indemnity/liability, confidentiality, dispute,
governing-law, risk, citation, and insufficient-evidence categories. Hard
negative links are recorded for nearby termination, renewal, service-level,
payment, and penalty concepts. One force-majeure case uses `ALL_OF` evidence.

Validation is valid: unique IDs, pinned version and checksum, READY state,
processed artifact, 669 chunks, 669 embeddings, evidence anchors, metadata,
and answer-leakage checks all pass. See
[`pbk_ifmc_golden_validation.json`](../../data/evaluation/results/pbk_ifmc_golden_validation.json).

## Chunk diagnostics

The second artifact has 669 chunks, mean 36.63 tokens, median 20, minimum 1,
maximum 492, 369 chunks below 25 tokens, 497 below 50, 592 below 80, and 622
below 100. Duplicate-text ratio is 0.0419. Evidence containment is 0.9412,
evidence split rate is 0.0294, adjacent retrieval requirement is 0, and
heading/clause cohesion is 0.1765. These are reported diagnostics only; the
base chunker remains frozen. The machine-readable report is
[`chunking_report.json`](../../data/evaluation/results/pbk-ifmc-baseline/chunking_report.json).

## Retrieval metrics

All values are averages over retrieval-applicable cases. Reranker results use
the same pre-rerank candidate pool as their paired hybrid measurement in the
combined runner. Latencies are milliseconds.

| Benchmark | Method | n | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@5 | Candidate R@40 | Mean | P50 | P95 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Standard | Dense | 49 | .551 | .653 | .714 | .776 | .625 | .654 | .857 | 58.0 | 16.7 | 56.8 |
| Standard | BM25 | 49 | .510 | .633 | .694 | .735 | .585 | .620 | .837 | 8.0 | 7.6 | 11.1 |
| Standard | Hybrid | 49 | .510 | .673 | .694 | .796 | .605 | .629 | .857 | 26.7 | 24.2 | 41.0 |
| Standard | Hybrid + reranker | 49 | .571 | .714 | .714 | .755 | .645 | .672 | .857 | 3340.6 | 2787.6 | 5253.5 |
| PBK IFM | Dense | 33 | .333 | .636 | .758 | .758 | .498 | .558 | .909 | 21.3 | 20.9 | 25.6 |
| PBK IFM | BM25 | 33 | .273 | .455 | .485 | .606 | .375 | .385 | .727 | 118.2 | 108.9 | 144.1 |
| PBK IFM | Hybrid | 33 | .303 | .515 | .636 | .727 | .433 | .469 | .848 | 133.6 | 130.7 | 171.0 |
| PBK IFM | Hybrid + reranker | 33 | .394 | .818 | .818 | .818 | .576 | .630 | .848 | 3288.2 | 2995.7 | 5097.3 |
| Combined | Dense | 82 | .463 | .646 | .732 | .768 | .574 | .615 | .878 | 43.2 | 19.2 | 28.5 |
| Combined | BM25 | 82 | .415 | .561 | .610 | .683 | .501 | .526 | .793 | 52.3 | 9.5 | 116.9 |
| Combined | Hybrid | 82 | .427 | .610 | .671 | .768 | .536 | .564 | .854 | 69.7 | 29.6 | 164.6 |
| Combined | Hybrid + reranker | 82 | .500 | .756 | .756 | .780 | .617 | .655 | .854 | 3319.5 | 2992.8 | 5180.9 |

The combined machine-readable benchmark, including every case and per-contract
breakdowns, is [`two-contract-baseline.json`](../../data/evaluation/results/two-contract-baseline.json).
The reproducible combined dataset is
[`two_contracts_dev_v1.json`](../../data/evaluation/golden/two_contracts_dev_v1.json).

## Category results and error taxonomy

The complete category matrix for both contracts and all methods is retained in
the benchmark JSON. For PBK IFM, hybrid / reranked R@1, R@3, R@5, R@10, MRR,
and Candidate R@40 were:

| Category (n) | Hybrid | Reranked |
|---|---|---|
| obligation (4) | .250/.500/.750/.750; .425; 1.000 | .500/1.000/1.000/1.000; .667; 1.000 |
| termination_notice (2) | .000/.500/.500/.500; .167; 1.000 | .000/1.000/1.000/1.000; .417; 1.000 |
| service_level (3) | .333/.333/.333/.333; .333; .667 | .667/.667/.667/.667; .667; .667 |
| penalty_or_deduction (3) | .667/.667/.667/1.000; .722; 1.000 | .667/1.000/1.000/1.000; .778; 1.000 |
| risk_analysis (2) | .000/.500/.500/.500; .250; .500 | .500/.500/.500/.500; .500; .500 |

Values within each cell are R@1/R@3/R@5/R@10; MRR; Candidate R@40.
Categories with fewer than three cases are directional only. The three
insufficient-evidence cases are excluded from retrieval recall by design and
remain safety-answer cases rather than positive retrieval targets.

Observed failures are primarily early-rank misses with the relevant chunk in
the candidate pool, especially risk and scope/service questions; sparse exact
wording is weaker on paraphrased service questions; and the long document's
many short structural chunks reduce heading/clause cohesion. The Standard
artifact remains stronger on factual and dense retrieval, while PBK shows a
larger reranker gain at R@3 and R@5.

## Reranker and generalization analysis

On the combined identical-pool comparison, reranking changes 820 observed
candidate-to-result positions: 510 move upward, 189 downward, and 121 remain
unchanged, with mean movement -6.83 ranks (negative is upward). It improves
combined R@3 from .610 to .756 and MRR from .536 to .617, while mean latency
rises from 69.7 ms to 3,319.5 ms. It remains experimental and is not a
production-readiness conclusion.

The architecture transfers partially: dense retrieval transfers better than
BM25 on the PBK service agreement, hybrid preserves strong candidate recall,
and reranking helps service, obligation, and termination cases at early ranks.
Failures repeat around semantic scope/performance distinctions and risk
questions, but their magnitude is document-specific. The PBK artifact's
long tender structure and 669 small chunks are materially different from the
42-chunk Standard artifact, so aggregate results should not hide that gap.

## Next experiment

Keep the frozen retrieval configuration unchanged. The next useful measurement
is a third independently acquired contract with comparable evidence labeling,
followed by a pre-registered error analysis across document structure and
question difficulty. Only after that should separate, explicitly labeled
experiments test chunking or fusion changes. This benchmark is an evaluation
checkpoint, not a production-ready claim.
