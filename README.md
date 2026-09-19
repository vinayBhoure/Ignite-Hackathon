# ignite-hackathon starter

Starter scaffold wired up for the four Ignite-with-Delhi sponsors: **Tavily**,
**Neo4j**, **Cognee**, and **Render**. Goal is to have accounts/keys/connections
sorted *before* the clock starts, so none of the 8 hours goes to plumbing.

## 1. Get accounts + keys (do this first, takes ~10 min)

- **Tavily** - sign up free at https://app.tavily.com, copy your API key
- **Neo4j** - create a free instance at https://console.neo4j.io (Aura Free).
  It gives you a URI, username (`neo4j`), and password - save the password,
  it's only shown once
- **Cognee** - no separate account, but it needs an LLM key to build its
  memory graph (OpenAI by default) - use whatever LLM key you already have
- **Render** - sign up free at https://render.com, connect your GitHub -
  nothing to configure locally until you're ready to deploy

## 2. Local setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

copy .env.example .env       # then open .env and paste in your keys
```

## 3. Sanity-check everything's connected

```bash
python test_connections.py
```

Anything you haven't filled in yet just prints SKIPPED, not an error -
fill in keys as you get them and re-run.

## 4. Start building

`app.py` is a minimal FastAPI app with one example route per sponsor
(`/search` -> Tavily, `/graph/ping` -> Neo4j, `/memory/add` + `/memory/search`
-> Cognee). Run it locally with:

```bash
uvicorn app:app --reload
```

Then open http://127.0.0.1:8000/docs to poke at the routes in the browser.
Replace the placeholder logic in each route with your actual idea rather than
starting the file from scratch.

## 5. Deploying (when you have something to demo)

Push this folder to a GitHub repo, then in Render: **New -> Blueprint**,
point it at the repo. `render.yaml` already describes the service - Render
will prompt you to paste in the same env vars from your `.env`.

## Files

| File | What it's for |
|---|---|
| `.env.example` | Copy to `.env` and fill in real keys - `.env` is gitignored |
| `requirements.txt` | `pip install -r requirements.txt` |
| `test_connections.py` | Run after filling in `.env` to check each service works |
| `app.py` | Minimal FastAPI app with one example route per sponsor |
| `render.yaml` | Deployment blueprint for Render |
