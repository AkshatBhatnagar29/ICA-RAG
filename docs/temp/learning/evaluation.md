# Evaluation

Evaluation code lives in `app/services/evaluation`, `tests/evaluation`, scripts,
and dated reports. Retrieval goldens map query/contract scope to expected
evidence. Recall@k asks whether relevant evidence appears in the first k;
MRR rewards the first relevant rank; nDCG rewards graded ordering. Candidate
Recall@40 measures whether reranking had the needed evidence before early-rank
selection. Latency p50/p95/p99 expose typical and tail cost.

The progression in repository reports is: baseline 20-case benchmark -> expanded
dataset audit -> two-contract benchmark -> three-contract benchmark -> frozen
reranker comparison. Lessons: hybrid retrieval improves lexical/semantic
coverage; Candidate R@40 remains strong but early-rank confusion remains; Jina
is retained for production while MiniLM needs matched repeated latency/resource
evidence. Reports freeze embedding, BM25, RRF k=60, chunking, scope, labels,
and candidate sets so reranker comparisons are interpretable.

Generation evaluation also checks citation precision/recall, unsupported claims,
legal scope, and controlled insufficient-evidence behavior. A benchmark score
does not establish legal correctness or production SLA; it identifies failure
modes and tradeoffs.
