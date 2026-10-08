# ICIA production deployment

This is the initial low-cost single-VM deployment: one FastAPI container, PostgreSQL 16 with pgvector, Redis 7, and an Nginx TLS reverse proxy. Only ports 80/443 are public; PostgreSQL and Redis are private Compose services. Start with one API worker because CPU model inference is memory-sensitive.

## Provision and configure

Use a small Linux VM with Docker Engine and the Compose plugin installed. Clone a pinned release commit or source archive, then create `.env` from `.env.example` (never commit it). Set at minimum `APP_ENV=production`, a random `AUTH_JWT_SECRET` of at least 32 characters, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, and `GROQ_API_KEY`. Do not set `AUTH_BOOTSTRAP_TOKEN` in production.

Place a trusted certificate and key at `docker/nginx/certs/fullchain.pem` and `docker/nginx/certs/privkey.pem`, with the key readable only by the deployment user. Configure DNS to the VM before starting TLS traffic.

## Build, migrate, and start

```sh
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d postgres redis
docker compose -f docker-compose.prod.yml run --rm api uv run --no-dev alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
curl -fsS https://YOUR_HOST/api/v1/health
curl -fsS https://YOUR_HOST/api/v1/ready
docker compose -f docker-compose.prod.yml logs --tail=100 api
```

The first request that uses local models may load them into the persistent `model_cache` volume. For predictable startup, prewarm after deployment with an authenticated search/rerank request and confirm the API log. The selected model and CPU mode are configuration values; model downloads must not be performed on every restart.

Create the first admin through the existing authenticated bootstrap flow, using the deployment-specific bootstrap procedure and then remove the bootstrap token. Verify login, upload, processing, indexing, search, Ask ICIA, citation validation, analysis, legal search, and wrong-tenant rejection before accepting traffic.

## Backup and restore

Back up the database and document volume to storage outside the VM. A minimum daily retention of 7 days is recommended initially:

```sh
mkdir -p /var/backups/icia
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres -d contract_intelligence | gzip > /var/backups/icia/db-$(date +%F).sql.gz
docker run --rm -v icia_document_storage:/data -v /var/backups/icia:/backup alpine tar czf /backup/documents-$(date +%F).tgz -C /data .
```

Test in a non-production Compose project: create an empty database, restore with `gunzip -c db-YYYY-MM-DD.sql.gz | docker exec -i <postgres> psql -U postgres -d contract_intelligence`, restore the document volume archive, run `alembic upgrade head`, and check `/api/v1/ready` plus a known document lookup. Record the date and result; a backup is not accepted until this restore test succeeds.

## Restart and rollback

Tag each built image with the pinned release identifier and retain the previous tag. Restart with `docker compose -f docker-compose.prod.yml up -d`. Roll back by checking out the previous pinned source/image tag, starting the previous API image, and running only migrations compatible with that release. Never downgrade the database schema blindly; restore the database backup if a prior release requires an older schema.

```sh
docker compose -f docker-compose.prod.yml up -d --no-deps api
docker compose -f docker-compose.prod.yml ps
```

## Operational checks

Review request IDs, endpoint/status/latency, and provider error categories in logs. Do not log contract text, tokens, API keys, or complete evidence payloads. Keep `.env`, certificates, dumps, and model cache outside version control. Recheck firewall rules to confirm only 80/443 are reachable.
