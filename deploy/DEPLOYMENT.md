# Deployment — matchmaking.hamqadam.com

## Live layout

| Piece | Value |
|---|---|
| Public URL | https://matchmaking.hamqadam.com |
| Server | 187.127.190.176 (AlmaLinux 9.8, CyberPanel/OLS 2.5.0) |
| App dir | `/home/hamqadam.com/matchmaking-model` |
| Python | `/usr/bin/python3.11` → venv at `.venv/` |
| Process | systemd `matchmaking-model.service`, uvicorn on `127.0.0.1:8011`, **1 worker** |
| Web layer | OLS vhost proxies `context /` → `127.0.0.1:8011` |
| TLS | Let's Encrypt (already issued); HTTP 301s to HTTPS |

## Endpoints

- `GET  /`          service banner
- `GET  /health`    health check (never requires the API key)
- `POST /users`     backend pushes the full user pool
- `GET  /match/{user_id}?top_n=&min_score=`
- `GET  /docs`      Swagger UI

## Operations

```bash
ssh hamqadam-vps
systemctl status  matchmaking-model
systemctl restart matchmaking-model
journalctl -u matchmaking-model -f     # application logs
```

## Redeploy after a code change

```bash
rsync -az --delete --exclude '.venv/' --exclude '.git/' --exclude '__pycache__/' \
      --exclude '*.pyc' --exclude '.DS_Store' --exclude '.env' \
      ./ hamqadam-vps:/home/hamqadam.com/matchmaking-model/
ssh hamqadam-vps 'chown -R hamqa5023:hamqa5023 /home/hamqadam.com/matchmaking-model \
                  && systemctl restart matchmaking-model'
```

## Important: the user pool is in-memory

`POST /users` stores the pool in the process. It is wiped by any restart, deploy or
crash, and that is why the service runs with `--workers 1` (a second worker would
serve `GET /match` from a pool that never received the upload).

The backend must therefore call `POST /users` before relying on `GET /match`.
`GET /health` reports `users_loaded`, so the backend can re-push when it hits 0.
Moving the pool to Redis or a database is the fix if that is not acceptable.

## Optional API key (currently OFF)

The API is public: anyone can overwrite the pool or read anyone's matches. To lock
it down, put the key in `/home/hamqadam.com/matchmaking-model/.env`:

```
MATCHMAKING_API_KEY=<long-random-string>
MATCHMAKING_ALLOWED_ORIGINS=https://hamqadam.com
```

then `systemctl restart matchmaking-model`. Clients then send `X-API-Key: <key>`.
Leaving `MATCHMAKING_API_KEY` unset keeps the API open (current behaviour).

## Backups of what was replaced

- code: `/root/matchmaking-model.bak.<timestamp>`
- vhost: `/usr/local/lsws/conf/vhosts/matchmaking.hamqadam.com/vhost.conf.bak.<timestamp>`

---

# CI/CD pipeline

`.github/workflows/deploy.yml` — every push to `master`:

1. **test** — Python 3.11, `pytest` (121 tests), route check, a real end-to-end
   smoke test against a uvicorn started in the runner, and a check that the API
   key guard rejects unauthenticated calls.
2. **deploy** — SSH to the server and run `deploy <sha>`.
3. **verify** — runs `deploy/smoke_test.py` against https://matchmaking.hamqadam.com,
   so the pipeline is only green if live matchmaking actually worked.

Pull requests run **test** only. Deploys are serialised by a concurrency group.

## Server side

`/usr/local/bin/deploy-matchmaking.sh <sha>` does the real work:
fetch → reset to that exact commit → `pip install -r requirements.txt` →
run the test suite **on the server** → restart → health check.
**If the tests or the health check fail it automatically rolls back** to the
commit that was previously running and restarts it. Log: `/var/log/matchmaking-deploy.log`.

The CI key is locked down in root's `authorized_keys` with
`command="/usr/local/bin/gha-deploy-wrapper.sh"` plus `no-pty`, `no-port-forwarding`,
`no-agent-forwarding`, `no-X11-forwarding`. The wrapper only accepts
`deploy` or `deploy <40-hex-sha>` — the key cannot open a shell or run
anything else on the server.

## Required GitHub secrets

| Secret | Value |
|---|---|
| `DEPLOY_SSH_KEY` | private key `~/.matchmaking-ci/gha_deploy` |
| `DEPLOY_HOST` | `187.127.190.176` |
| `DEPLOY_KNOWN_HOSTS` | `187.127.190.176 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKbddYBxMfLkJxOoQbJwOhTe8CpsJ8u1AkRSRHhpP6op` |
| `MATCHMAKING_API_KEY` | optional — only if the API key guard is switched on |

## Manual deploy / rollback

```bash
ssh hamqadam-vps '/usr/local/bin/deploy-matchmaking.sh'              # deploy master HEAD
ssh hamqadam-vps '/usr/local/bin/deploy-matchmaking.sh <old-sha>'    # roll back
tail -f /var/log/matchmaking-deploy.log
```
