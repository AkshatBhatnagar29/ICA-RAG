# Production and Docker

`Dockerfile` builds Python 3.12 slim, installs Tesseract and LibreOffice, syncs
locked dependencies, and runs Uvicorn. `docker-compose.yml` runs API,
PostgreSQL/pgvector, and Redis with health checks, model/document/Postgres
volumes, and internal service names. `docker-compose.prod.yml` adds restart
policies, secrets from `.env`, Redis auth/persistence, and an Nginx TLS reverse
proxy exposing only 80/443.

Local development uses default Compose credentials and published database/Redis
ports; these are not production credentials. Production requires overriding
passwords and JWT/API secrets, private DB/Redis networking, backups, TLS
certificates, and operational monitoring.

The current deployment is a low-cost single VM, one API worker, because local
CPU embedding/reranker inference is memory-sensitive. It has not measured SLA,
load, autoscaling, or multi-worker model duplication. Future scale work would
separate ingestion/index workers, model capacity, storage, and database read
capacity only after measurements; Celery/Kafka/Kubernetes are not current
architecture.
