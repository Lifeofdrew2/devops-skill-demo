# Deployment, incidents and recovery

Scope: isolated `devops-demo` namespace, existing cluster, no data store. Operator
and escalation contact must be assigned by the team. Commands below have NOT run
against a cluster. Do not apply to production as a tutorial exercise.

## Before deployment

- Have Docker, kubectl, metrics-server, an existing Prometheus and two schedulable
  nodes. Confirm cluster version supports APIs in k8s/app.yaml and available headroom
  for five replicas plus one surge (600m CPU requests, 384Mi memory requests).
  These are workload requests only, not total cluster requirements.
- Inspect `kubectl config current-context` and explicitly choose your lab context.
  Use `kubectl --context "$LAB_CONTEXT"` on EVERY command; never infer a production
  context. Set LAB_CONTEXT to an actual context you inspected.
- Use a public lab image or provision private-registry pull access separately.
  Build once for the intended cluster architecture, scan it using the team's
  scanner, resolve its registry digest, and retain the last known-good digest.
  CI publishes a release after checks; it does not automatically deploy.
- Replace REPLACE_IMAGE_BY_DIGEST in a COPY of k8s/app.yaml with an actual
  `registry/repository@sha256:...` reference. Call the copy `release.yaml`.
  Never apply unresolved placeholders. Create the namespace first for dry-run:

```sh
kubectl --context "$LAB_CONTEXT" create namespace devops-demo --dry-run=client -o yaml > namespace.yaml
kubectl --context "$LAB_CONTEXT" apply -f namespace.yaml
kubectl --context "$LAB_CONTEXT" apply --dry-run=server -f release.yaml
kubectl --context "$LAB_CONTEXT" diff -f release.yaml
# diff exits 1 for differences; review those changes before continuing.
kubectl --context "$LAB_CONTEXT" apply -f release.yaml
kubectl --context "$LAB_CONTEXT" -n devops-demo rollout status deployment/demo-api --timeout=180s
kubectl --context "$LAB_CONTEXT" -n devops-demo get pods,hpa,pdb
kubectl --context "$LAB_CONTEXT" -n devops-demo port-forward service/demo-api 8080:80
# In another terminal:
curl --fail http://127.0.0.1:8080/
```

The response must identify the expected version and status 200. Set APP_VERSION
in the release manifest to the release commit. Inspect all replicas, endpoints,
logs and actual ingress journey if integrating ingress. A port-forward tests a
single connection path, not load balancing, TLS or external availability.

## Monitoring integration

Merge monitoring/prometheus.yaml scrape job and rule_files entry into your existing
Prometheus configuration. Mount alerts.yaml at the stated path. Replace the RBAC
account placeholders, review and apply monitoring/rbac.yaml. Check config and
rules with the same Prometheus release used by your team:

```sh
promtool check config /path/to/merged-prometheus.yaml
promtool check rules monitoring/alerts.yaml
```

Retain existing Alertmanager routing; select an actual owner and notification
receiver before production use. No notifications are sent by this lab. Confirm
per-pod targets are up; do not scrape only the load-balanced Service, which would
mix counters across replicas. Test delivery in an authorized sandbox channel.
A missing job or all down targets fires after 2m; low/no traffic suppresses the
error-ratio alert. Scrape success alone does not prove the business route works.
Dashboard queries: throughput `sum(rate(demo_requests_total[5m]))`; error ratio
`sum(rate(demo_requests_total{status="503"}[5m])) / clamp_min(sum(rate(demo_requests_total[5m])), 0.001)`;
scrape health `up{job="demo-api"}`. Use existing cluster telemetry for CPU,
memory, restarts and pending pods. Add latency instrumentation before adopting
a latency SLO; this lab does not expose latency histograms.

## Incident: failing requests following a release

Impact: the GET / journey returns 503 while process health can remain green.
Capture UTC onset, release digest, affected users and incident owner.

```sh
kubectl --context "$LAB_CONTEXT" -n devops-demo rollout history deployment/demo-api
kubectl --context "$LAB_CONTEXT" -n devops-demo get pods -o wide
kubectl --context "$LAB_CONTEXT" -n devops-demo logs deployment/demo-api --since=10m --tail=100
kubectl --context "$LAB_CONTEXT" -n devops-demo get events --sort-by=.lastTimestamp
kubectl --context "$LAB_CONTEXT" -n devops-demo top pods
```

Decision: failures aligned with a new release suggest regression; unchanged
release plus high CPU/pending pods suggests capacity; missing scrape targets
suggest discovery/network/process issues. These are hypotheses until verified.
For a confirmed release regression restore the recorded previous digest:

```sh
# PREVIOUS_IMAGE must be the actual retained known-good digest.
kubectl --context "$LAB_CONTEXT" -n devops-demo set image deployment/demo-api api="$PREVIOUS_IMAGE"
kubectl --context "$LAB_CONTEXT" -n devops-demo rollout status deployment/demo-api --timeout=180s
```

Smoke-test GET /, then monitor errors, target health and restarts for at least
10 minutes under representative lab traffic. Match version metadata to the
restored release. Escalate to the assigned owner if rollback fails, pods remain
pending, targets disappear or customer errors persist. Record trigger,
observations, action, recovery time and follow-up; do not label a hypothesis as
root cause. `rollout undo` is an alternative only after inspecting its target
revision. A readiness probe cannot identify every business logic defect.

## Scale and reliability drill (lab only)

Start with two replicas and steady representative traffic. Ramp gradually for
at most five minutes; stop at sustained >5% failures or rising latency outside
the team's agreed limit. Watch HPA, CPU and pending pods. Expected HPA range:
2-5, CPU target 60% of the 100m request, 300s scale-down stabilization. Metrics
server and node headroom are prerequisites; HPA does not provision nodes.
Measure achieved throughput, tail latency, errors, saturation and replica count
before changing targets. No capacity claim is established by this configuration.

Proposed availability SLO: 99.9% successful GET / requests over 30 days, using
200 / (200 + 503), excluding probes and metrics. This is a proposal, not measured
uptime. Budget: 0.1% of eligible requests; zero traffic is undefined. Scrape gaps
and unreachable-process failures make application counters incomplete; add an
independent synthetic journey before adopting this as a production SLI.

Two nodes and spread constraints reduce node concentration. PDB only constrains
voluntary evictions; it does not guarantee survival of node failures or protect
against bad releases. One cluster/region and telemetry remain dependencies.
There is no durable application state: preserve source/configuration and image
digests for recovery. Proposed RTO is 15 minutes; RPO is not applicable to this
stateless lab. Regional rebuild and backup restoration are untested.

## Cleanup

Local tests shut down their own processes. To remove cluster lab resources,
first confirm the namespace contains only this demo and retain anything needed:

```sh
kubectl --context "$LAB_CONTEXT" -n devops-demo get all
# Destructive to this namespace; run only for your disposable lab.
kubectl --context "$LAB_CONTEXT" delete namespace devops-demo
```

Remove merged Prometheus scrape/rules entries and reload using your established
process. Keep shared monitoring infrastructure and unrelated resources.
