# 2026-04-11 — Memory leak triage and docker memory cap

## Context

Around 04:52 UTC today, the `infra` VM ran out of memory and started OOM-killing
unrelated services (cadvisor restarted six times, Grafana / Loki / Uptime Kuma
degraded). SRE-agent traced the cause to this service: `documentation-server`
had grown from ~175 MB at startup to 750 MB over several hours, and the same
pattern had repeated at least eight times in the previous 2.5 days — peaks of
1.26 GB, 1.59 GB, and 1.25 GB across 8 Apr / 9 Apr / 10 Apr respectively. The
VM has 1.95 GB total RAM, so one run-away container is enough to starve
everything else.

## Diagnosis

1. **`mem_limit: 1536m` was catastrophic on a 1.95 GB host.** Docker would
   let this container reach 78% of host RAM before killing it — by that
   point the kernel had already started evicting other containers. The
   container limit was, in effect, "no limit".
2. **The underlying growth pattern was glibc malloc hoarding**, not a
   Python-level leak. The scheduler runs every 5 minutes and each cycle
   allocates: the output of `git log --diff-filter=A --name-only` (can be
   MB per repo × 14 repos), GitPython `Repo` objects with reference cycles,
   numpy arrays from ONNX inference when content changes, and SQLite / ChromaDB
   query results. Python frees these objects, but glibc retains the freed
   pages in its arenas and does not hand them back to the kernel. Over
   hours, RSS drifts upward until the container is OOM-killed.
3. **Secondary leak: per-request `anthropic.Anthropic` client** in
   `server.py`. Each call to `/api/chat` allocated a fresh client with its
   own internal `httpx.Client` connection pool. This isn't the scheduler-
   driven leak the SRE observed, but it is a real leak and trivial to fix.

## Fixes

1. **`docker-compose.yml`** — `mem_limit` lowered from 1536 MB to 512 MB,
   added `mem_reservation: 200m`. Steady-state is ~150 MB, so 512 MB gives
   ~3× headroom for transient ingestion spikes; anything above that is a
   regression and gets OOM-killed cleanly instead of taking the host down.
2. **`ingestion.py`** — added `reclaim_memory()` helper that runs
   `gc.collect()` and (on glibc Linux) `ctypes.CDLL(libc).malloc_trim(0)`
   to return freed pages back to the kernel. `_run_once_safe` calls it in
   a `finally` block after every cycle, so it runs even if the cycle
   raises. Every call logs before/after RSS under the `memory_reclaim`
   event so the fix is visible in production logs.
3. **`server.py`** — introduced `_get_anthropic_client()` module-level
   singleton. The cache keys on the class identity of `anthropic.Anthropic`
   so test patches that swap in mocks still rebuild the client on demand.

## Tests

Added `TestMemoryReclaim` in `tests/test_ingestion.py`:

- `test_reclaim_memory_returns_expected_keys` — shape / type check on the
  returned dict.
- `test_reclaim_memory_runs_gc_collect` — confirms `gc.collect` is called
  unconditionally (not gated on `_MALLOC_TRIM` availability).
- `test_run_once_safe_calls_reclaim_on_success` — happy path.
- `test_run_once_safe_calls_reclaim_on_exception` — the `finally` block
  must run the cleanup even if the underlying cycle raises.

Added `_reset_anthropic_client_cache` autouse fixture in
`tests/test_chat_endpoint.py` to clear the singleton between tests so
mock patches take effect on every test. The singleton also detects
class-identity changes so in-test re-patching works without manual resets.

Full suite: **333 passed** at 88% coverage. Lint clean.

## Platform notes

`malloc_trim(0)` is glibc-only. On macOS dev machines and Alpine/musl
builds the helper returns `None` and the reclaim step degrades to a plain
`gc.collect()`. The production image is Debian slim (glibc), which is
where the mitigation matters.

## Follow-ups to consider

- If the leak recurs after deploying this fix, the next investigation
  should target **GitPython specifically** — its `Repo` objects are known
  to hold subprocess handles and pack-file references past `close()`.
  Replacing `Repo.remotes.origin.fetch()` with a plain `subprocess.run(["git", "fetch"])`
  would remove that variable entirely and is likely worth doing regardless.
- The `infra` VM at 1.95 GB for ~14 services is genuinely tight. Even a
  healthy documentation-server at 150 MB leaves little headroom. Bumping
  the VM to 4 GB is worth considering independent of this fix.
- The `memory_reclaim` log event should get a Grafana panel so the
  before/after-reclaim RSS is visible at a glance.
