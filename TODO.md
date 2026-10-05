# TODO

Roadmap for calorie-balance. Decisions and background live in `CLAUDE.md`.

## 0. Project setup ✅

- [x] Decide burned-calories source (Strava REST API now, COROS MCP later)
- [x] Public GitHub repo with `.gitignore`, `.env.example`, MIT license, noreply commit email
- [x] Secret scanning + push protection enabled (GitHub, free for public repos)
- [ ] Optional: install gitleaks and add a pre-commit hook

## 1. Thin end-to-end slice

Goal: photo → macros → save → today's balance, with a hard-coded burned value.

### Backend (FastAPI)

- [ ] Project skeleton (`backend/`), settings loaded from `.env`
- [ ] `POST /meals/estimate` — photo in, Claude vision → strict JSON out
      (items, grams, kcal, protein/carbs/fat, confidence)
- [ ] Try it on a few of my own meal photos via FastAPI's `/docs` page (sanity check, not an
      accuracy study)
- [ ] `GET /balance/today` — burned (hard-coded `BurnProvider`) vs. ingested
- [ ] Simple shared-secret auth between app and backend (the backend holds paid API keys)
- [ ] Decide where the backend runs for the phone to reach it:
      local network / Tailscale vs. a small cloud host (Fly.io, Railway, …)

### Android app

- [ ] Project skeleton (`android/`): Kotlin, Jetpack Compose, Material 3
- [ ] CameraX capture screen
- [ ] Send photo to backend, show estimate on a basic review screen (editable numbers)
- [ ] Save meal to Room
- [ ] Basic "today's balance" screen (ingested from Room, burned from backend)

## 2. Real burned calories (Strava)

- [ ] Register a Strava app; add client ID/secret to `.env`
- [ ] One-time OAuth flow (`/auth/strava/callback` or script); store refresh token locally
- [ ] Token refresh (access tokens expire after ~6 h)
- [ ] `StravaBurnProvider`: list today's activities → fetch details → sum `calories`
- [ ] BMR estimate (Mifflin–St Jeor × activity factor) from `.env` body data
- [ ] Handle activities with 0/missing calories
- [ ] Tests with synthetic Strava responses (no real data in the repo)

## 3. UI polish

- [ ] Design pass (Material 3): camera, review/edit estimate, today's balance, history
- [ ] History screen: past days with balance per day
- [ ] Edit/delete logged meals
- [ ] Manual meal entry (no photo) as a fallback
- [ ] If estimates feel off: look up nutrition per 100 g in USDA FoodData Central /
      Open Food Facts instead of letting the model guess; barcode scanning for packaged food

## 4. Later: COROS (if I buy a COROS watch)

- [ ] Connect COROS MCP in Claude Code and inspect raw `queryDailyHealthData` output
- [ ] Resolve: active or total (incl. BMR) calories?
- [ ] `CorosBurnProvider` via MCP client (OAuth, follow regional redirects, defensive parsing)
- [ ] Switch provider in config; keep Strava as fallback
