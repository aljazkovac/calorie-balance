# TODO

Roadmap for calorie-balance. Decisions and background live in `CLAUDE.md`.

## 0. Project setup ✅

- [x] Decide burned-calories source (Strava REST API now, COROS MCP later)
- [x] Public GitHub repo with `.gitignore`, `.env.example`, MIT license, noreply commit email
- [x] Secret scanning + push protection enabled (GitHub, free for public repos)
- [x] Decide where data lives (backend, not phone) and hosting (DigitalOcean Droplet)
- [ ] Optional: install gitleaks and add a pre-commit hook

## 1. Thin end-to-end slice

Goal: photo → macros → save → today's balance, with a hard-coded burned value, running on
the Droplet and used from the phone.

### Backend (FastAPI)

- [x] Project skeleton (`backend/`), settings loaded from `.env`
- [x] `POST /meals/estimate` — photo in, Claude vision → strict JSON out
      (items, grams, kcal, protein/carbs/fat, confidence)
- [ ] Try it on a few of my own meal photos via FastAPI's `/docs` page (sanity check, not an
      accuracy study)
- [ ] SQLite storage in `DATA_DIR` (meals + items), reduced photos as files next to it
- [ ] Meal endpoints: save (estimate as edited + reduced photo), list by day, get, edit, delete
- [ ] `GET /meals/{id}/photo`
- [ ] `GET /balance/today` (or `?date=`) — burned (hard-coded `BurnProvider`) vs. eaten
- [ ] App token auth on every endpoint (`Authorization: Bearer <APP_TOKEN>`)
- [ ] Tests with synthetic data (no real photos/meals in the repo)

### Deploy (DigitalOcean)

- [ ] `Dockerfile` for the backend + `docker-compose.yml` (backend + Caddy), data dir as a volume
- [ ] Domain/subdomain for the backend (needed for HTTPS)
- [ ] Create Droplet: Basic 1 GB, EU region (Amsterdam/Frankfurt), Ubuntu LTS, SSH key,
      daily backups
- [ ] Harden: SSH keys only, Cloud Firewall (22/80/443), unattended security upgrades
- [ ] Install Docker, copy `.env` to the server (never via git), `docker compose up -d`
- [ ] Deploy script (later: GitHub Actions deploy on push to `main`)
- [ ] Smoke test from the phone's browser: `https://<domain>/docs`

### Android app

- [ ] Project skeleton (`android/`): Kotlin, Jetpack Compose, Material 3
- [ ] Backend URL + app token config (not committed)
- [ ] CameraX capture screen; also pick an existing photo from the gallery
- [ ] Send photo to backend, show estimate on a basic review screen (editable numbers)
- [ ] Save meal via backend
- [ ] Basic "today's balance" screen (from `GET /balance/today`)

## 2. Real burned calories (Strava)

- [ ] Register a Strava app; add client ID/secret to `.env` (local + server)
- [ ] One-time OAuth flow (`/auth/strava/callback` or script); store refresh token in `DATA_DIR`
- [ ] Token refresh (access tokens expire after ~6 h)
- [ ] `StravaBurnProvider`: list today's activities → fetch details → sum `calories`
- [ ] BMR estimate (Mifflin–St Jeor × activity factor) from `.env` body data
- [ ] Handle activities with 0/missing calories
- [ ] Tests with synthetic Strava responses (no real data in the repo)

## 3. UI polish

- [ ] Design pass (Material 3): camera, review/edit estimate, today's balance, history
- [ ] History screen: past days with balance per day, meal thumbnails
- [ ] Edit/delete logged meals
- [ ] Manual meal entry (no photo) as a fallback
- [ ] Optional setting: also save the full-size original photo to the gallery (Google Photos)
- [ ] If estimates feel off: look up nutrition per 100 g in USDA FoodData Central /
      Open Food Facts instead of letting the model guess; barcode scanning for packaged food

## 4. Operations

- [ ] Off-site backup of DB + photos (e.g. daily copy to DigitalOcean Spaces)
- [ ] Uptime check / alert if the backend is down
- [ ] Optional: Room as an offline cache in the app

## 5. Later: COROS (if I buy a COROS watch)

- [ ] Connect COROS MCP in Claude Code and inspect raw `queryDailyHealthData` output
- [ ] Resolve: active or total (incl. BMR) calories?
- [ ] `CorosBurnProvider` via MCP client (OAuth, follow regional redirects, defensive parsing)
- [ ] Switch provider in config; keep Strava as fallback
