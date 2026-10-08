# Redis reality check

`app/db/session.py:ResourceManager` constructs an async Redis client from
`REDIS_URL` and closes it with the SQLAlchemy engine. Compose starts Redis and
health-checks `redis-cli ping`. That is the complete current application use:

```text
startup -> construct client
shutdown -> close client
```

There are no application Redis keys, TTLs, reads, writes, queues, locks, or
cache lookups. Redis is therefore **currently used for infrastructure
availability/lifecycle only**, not durable state, retrieval, sessions, or model
results. The production Compose file adds password protection, persistence, and
no-eviction configuration, but that does not create application semantics.

Possible future uses are bounded request throttling, short-lived job/status
state, or carefully invalidated cache entries. Durable document, evidence,
analysis, and authorization state must remain PostgreSQL/object-storage data.
