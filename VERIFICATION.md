# Verification evidence

Executed in the local workspace on 2026-10-27 with Python 3.12.14.

| Check | Observed result |
|---|---|
| Healthy GET /, /healthz and /readyz | Passed |
| Unknown route | 404 |
| Defective release | GET / returned 503; probes remained 200 |
| Failure counter | Reflected the failing request |
| Restore good release | GET / returned 200 with good version |
| SIGTERM | All three server processes exited cleanly |
| Bounded request sample | 100 requests, concurrency 4, zero errors |
| Sample elapsed time / p95 | 0.063 seconds / 4.004 ms |
| Local restart to recovered request | 0.0864 seconds |
| Configuration parse | 10 YAML documents passed PyYAML parsing |
| Static configuration checks | Separate startup/readiness/liveness probes; HPA owns replicas |

The timing results describe one loopback sample on this machine. They are not
production capacity, network latency, Kubernetes recovery time or achieved RTO.
The failure and recovery drill replaces local processes; it does not simulate a
Kubernetes rolling update or restore data.

Not executed: Docker build/container smoke test, GitHub Actions workflow,
image publication/scanning, promtool validation or alert evaluation/delivery,
Kubernetes schema/server-side validation, scheduling, rollout, rollback, HPA,
node failure, load-balanced traffic, ingress/TLS or regional recovery. Docker,
kubectl and promtool are unavailable here; no external cluster was accessed.
Those checks and prerequisites are specified in docs/RUNBOOK.md and CI.

No paid resources were created and no messages or notifications were sent.
