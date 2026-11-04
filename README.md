# Eat and Burn

Personal nutrition and training tracker, built as a **learning project**. The app itself is deliberately simple; the real goal is hands-on depth in deployment and testing.

## Why this project exists

I want to learn, end to end and properly, the stack I work with at a high pace at work:

1. **Kubernetes, Helm, GitOps with Argo CD** (most important; for my platform engineering work)
2. **Testing strategy**: unit, integration, contract, and E2E (most important; I lead a team that includes QA engineers)
3. Observability, multiple environments, feature flags, progressive delivery
4. AI features (photo-based nutrition estimates, chat assistant) and how to test non-deterministic output

Not a goal: learning Android/iOS or native mobile development.

## How to work with me (learning mode)

- Explain _why_ before _what_. When there are real alternatives, lay out the trade-offs briefly and let me make the call.
- Prefer small, reviewable steps over large generated chunks. Don't scaffold whole subsystems in one go.
- When introducing a new tool or concept (Helm, ApplicationSets, Testcontainers, etc.), give a short explanation of what it does and how it fits.
- Occasionally ask me to explain something back or to write a piece myself, then review it.
- Record significant decisions as short ADRs in `docs/adr/` (context, decision, alternatives, consequences).
- Point out when I'm drifting into scope that doesn't serve the learning goals above.

## Product (what the app does)

A **PWA** (progressive web app), hosted in Kubernetes and opened on my phone via the browser / home-screen icon. No native app.

Screens, in build order:

1. **Capture**: take a photo of a meal, get an AI estimate (foods, portions, calories, macros), confirm or correct it. Corrections are important: they fix accuracy and become labeled data for AI evals.
2. **Today**: calories in vs. calories out, running deficit, macros, today's training.
3. **History**: past meals and days, editable.
4. Later: **Trends dashboard** (weekly deficit trend, intake vs. training load).
5. Later: **Chat assistant** (slide-up panel with access to my meal and activity data).

Both sides of the deficit are estimates; show trends over weeks rather than precise daily numbers.

## Architecture

- **Frontend**: PWA (React or Vue, so it can be wrapped with Capacitor later if ever needed for app stores).
- **Backend API**: FastAPI, in `backend/` (run locally with `.venv/bin/uvicorn app.main:app --reload`, port 8000).
- **Worker**: processes photo-analysis jobs from a queue (NATS or Redis), calls an LLM.
- **Postgres**: in the cluster (e.g. CloudNativePG), with backups that get test-restored.
- **Sync CronJobs**: pull activity data from external providers nightly and store it in Postgres.

### Activity data: provider-agnostic adapters

One internal interface, e.g. `ActivitySource` with `get_daily_summary` and `get_workouts`, with adapters behind it:

1. **Fake adapter** (build first): generates realistic synthetic data. Used by integration and E2E tests, and lets the whole platform be built before real data matters.
2. **Polar adapter** (current real source): via Polar AccessLink (REST + OAuth2).
3. **COROS adapter** (later, if I buy a COROS watch): via the official COROS MCP (OAuth, self-service for individual developers, read access to daily health, activities, assessments; write access for workout plans).

Decided against: **Samsung Health** (on-device SDK only, would need a native Android sync app, and the SDK doesn't run on emulators, so it can't be tested in CI). **Strava** (API terms prohibit using its data for AI).

### Calories out model (with current hardware)

I have a Polar chest strap and record workouts with the Polar Beat app; sessions sync to Polar Flow. There is no all-day activity tracking. So:

- Resting energy: formula (e.g. Mifflin-St Jeor) from height, weight, age, sex
- Workout calories: from the chest strap via AccessLink (heart-rate based, most accurate part)
- Everyday movement: simple activity multiplier for now

The dashboards should show which parts are measured vs. estimated.

## Polar AccessLink setup

- Admin site: https://admin.polaraccesslink.com (log in with Polar Flow account, create an API client)
- Register as a personal, non-commercial, single-user project
- Redirect URL: implement the callback in the FastAPI backend, e.g. `http://localhost:8000/auth/polar/callback`; add the production domain later (multiple redirect URLs are allowed; must match exactly, including port)
- Authorize via `https://flow.polar.com/oauth2/authorization?response_type=code&client_id=<CLIENT_ID>`, exchange code for token, then register the user (409 Conflict = already registered, fine)
- Reference: github.com/polarofficial/accesslink-example-python
- To verify early: whether historical data is available or only data recorded after linking. Record a test workout after linking and confirm the sync can fetch it.
- Client secret is never committed; later managed as a Kubernetes secret (External Secrets or Sealed Secrets)

## Local environment notes

- macOS with OrbStack (has a built-in single-node Kubernetes cluster, usable instead of kind/k3d)
- Port 5000 is taken by macOS AirPlay Receiver (ControlCenter); don't use it
- Port 8000: backend API. Keep a fixed port per service and document it in `.env.example`

## Testing strategy

- **Unit**: business logic, adapter data mapping, deficit calculation
- **Integration**: Testcontainers with real Postgres and queue; sync jobs against a mock provider server
- **Contract**: each adapter against the provider's response format (catch upstream changes early)
- **E2E**: Playwright (including mobile viewport emulation) against a per-PR preview environment, fed by the fake adapter with known data
- **AI evals**: a small set of meal photos with known calories, run in CI to track estimate accuracy over time
- **Live checks**: occasional scheduled runs against the real Polar API, not on every commit
- Deliberately handle flaky tests rather than retrying them away

## Platform, GitOps, and operations

- **Repos**: app repo(s) with code, tests, Dockerfiles, Helm charts; a separate **GitOps repo** with desired state per environment and all cluster add-ons. CI builds and pushes images but never touches the cluster; Argo CD deploys.
- **Environments**: dev / staging / prod as folders or values files; promotion is a PR that bumps an image tag (rollback = `git revert`)
- **App of apps / ApplicationSets** to generate Argo CD Applications
- **Preview environments**: ApplicationSet PR generator, one namespace per PR, E2E tests run against it
- **Cluster add-ons via GitOps**: ingress, cert-manager, Prometheus/Grafana, OpenTelemetry, External Secrets, Postgres operator
- **Self-heal**: enable auto-sync; deliberately cause drift to see it reverted
- **Feature flags**: OpenFeature with flagd or Unleash; ship features dark, enable for myself, then make permanent
- **Progressive delivery**: Argo Rollouts canaries gated on Prometheus metrics
- **IaC**: Terraform/OpenTofu for the cluster itself; goal is to rebuild everything from Git
- **Hosting candidates**: OrbStack Kubernetes locally; k3s on cheap Hetzner VMs for the real cluster
- **Failure practice**: kill nodes, break deployments, run a mini incident with a postmortem

## Roadmap

1. **Walking skeleton**: one trivial endpoint + DB through the full path (repo → CI → image → Helm → Argo CD → cluster → ingress/TLS → one E2E test)
2. **GitOps foundations**: add-ons in Git, multiple environments, PR-based promotion
3. **Observability**: metrics, logs, traces, first SLOs
4. **Testing strategy**: full test pyramid, preview environments per PR
5. **Real data**: Polar adapter + sync CronJob
6. **App features**: capture → today → history
7. **Feature flags + Argo Rollouts**
8. **AI features**: photo analysis worker with evals, then trends dashboard, then chat assistant
9. Later, optional: COROS adapter

## Conventions

- Every table has a `user_id` from day one, even while I'm the only user
- Keep a clean API boundary between frontend and backend
- No secrets in Git, ever
