# calorie-balance

Personal Android app: photograph food → AI estimates calories + macros → compare against
calories burned → show daily caloric balance (burned vs. ingested).
Single user (me). Not distributed.

## Architecture (decided)

```
Android app (Kotlin + Jetpack Compose, CameraX, Room for local meal log)
   │  photo / "today's balance"
   ▼
Small backend (FastAPI)
   ├─ BurnProvider → burned calories (Strava REST API now; COROS MCP later)
   └─ Claude vision API → calories + macros as strict JSON
```

The backend exists to hold the OAuth tokens and the AI API key (keep keys out of the APK).

## Public repo — rules

This repo is public on GitHub.

- Secrets only in `.env` (gitignored); document new variables in `.env.example` with empty values.
- Never commit personal data: meal photos, spike results, body data, real Strava/COROS responses,
  local databases. Use synthetic fixtures in tests.
- Commits use the GitHub noreply email (set in this repo's local git config).
- Check `git status` / the staged diff for secrets and personal data before every commit.

## Burned-calories source (decided)

- **Now: Strava REST API + BMR estimate.** I don't own a COROS watch yet; the goal is to get the
  app working end to end, not perfect numbers.
- **Later (optional): switch to COROS MCP** if I buy a COROS watch — it has all-day data (steps,
  daily calories), which Strava lacks.
- Keep the source swappable behind one interface; the Android app only calls the backend
  (`GET /balance/today`) and never knows which provider is used:

  ```python
  @dataclass
  class DailyBurn:
      date: date
      total_kcal: int         # what the balance screen shows
      active_kcal: int | None
      source: str             # "strava+bmr", "coros", ...

  class BurnProvider(Protocol):
      async def get_daily_burn(self, day: date) -> DailyBurn: ...
  ```

## Strava data access (current)

- Docs: `https://developers.strava.com/docs/` (API reference: `https://developers.strava.com/docs/reference/`)
- Register an app at `https://www.strava.com/settings/api`; OAuth 2.0 with scope `activity:read_all`.
  Access tokens expire after ~6 h — the backend stores the refresh token and refreshes. One-time
  authorization via a backend callback endpoint (or a one-off script); no login screen in the app.
- Daily burn = BMR estimate (Mifflin–St Jeor × activity factor) + sum of today's activity calories:
  - `GET /athlete/activities?after=<midnight>&before=<now>` — summary objects have **no** calories.
  - `GET /activities/{id}` — detailed activity has `calories` (kcal).
- Caveats: Strava only knows recorded activities (no everyday movement / steps); `calories` can be
  0/missing without HR or body weight (set weight in the Strava profile); activity calories are
  usually gross, so adding them on top of full-day BMR slightly overcounts. Fine for now.
- Activities without a watch: record with the Strava phone app.
- Not the Strava MCP connector — it requires a paid subscription and appears limited to Claude clients.

## COROS data access (later)

- COROS MCP server: `https://mcp.coros.com/mcp` — standard OAuth 2.0, no partner approval needed
  for custom apps. The backend acts as a plain MCP client (`tools/call`), no LLM involved.
- Reference links:
  - COROS MCP overview (data exposed, supported AI clients): `https://coros.com/stories/coros-metrics/c/mcp-testing`
  - Build on COROS MCP (custom apps, OAuth, limitations): `https://support.coros.com/hc/en-us/articles/53181619102996-Build-on-COROS-MCP`
    (blocks plain fetches with 403; read it via the Zendesk API:
    `https://support.coros.com/api/v2/help_center/en-us/articles/53181619102996.json`)
  - Docs + tool list: `https://github.com/coroslab/COROS-MCP`
- Tool for burned calories: `queryDailyHealthData` (steps, calories, stress, sleep, HR summary).
  Output format is undocumented — parse defensively.
- Single-user scope, no webhooks (poll), endpoint redirects to a regional server — the client
  must follow redirects.
- **Open question:** does `queryDailyHealthData` return active or total (incl. BMR) calories?
  Verify by connecting in Claude Code (`claude mcp add --transport http coros https://mcp.coros.com/mcp`,
  then `/mcp` to authenticate) and inspecting the raw tool output. Decides whether the COROS
  provider still needs the BMR estimate.

## Plan / order

Detailed checklist: `TODO.md` — keep it updated as items are done.

Food estimates only need to be good enough to be useful — no formal accuracy study; the
review/edit screen handles corrections.

1. Thin end-to-end slice: photo → macros → save → today's balance (hard-coded burned value).
2. Wire in real burned calories: `StravaBurnProvider` (Strava REST API + BMR estimate) behind
   the `BurnProvider` interface.
3. UI polish (design pass only after the slice works). Screens: camera, review/edit estimate,
   today's balance, history. Material 3.
4. Later, if I get a COROS watch: add `CorosBurnProvider` (COROS MCP) and switch to it; resolve
   the active-vs-total question first.
