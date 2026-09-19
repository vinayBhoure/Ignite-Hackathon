"""
Minimal starter app wiring up the hackathon sponsors. Build on top of this
instead of starting from scratch - swap out the placeholder logic in each
route for your actual idea.

Run locally:    uvicorn app:app --reload
Deploy:         push to GitHub, then Render -> New -> Blueprint (uses render.yaml)
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

app = FastAPI(title="Ignite Hackathon Starter")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
def search(q: str):
    """Example: web search via Tavily, grounded in real-time results."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return client.search(q, max_results=5)


# --- Neo4j: open one driver and reuse it, don't reconnect per request ---
_neo4j_driver = None


def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        from neo4j import GraphDatabase

        _neo4j_driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
        )
    return _neo4j_driver


@app.get("/graph/ping")
def graph_ping():
    """Example: confirm the graph DB is reachable."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        session.run("RETURN 1")
    return {"neo4j": "connected"}


# --- Cognee: build/query an agent's long-term memory ---
@app.post("/memory/add")
async def memory_add(text: str):
    """Example: add a piece of text to the agent's persistent memory."""
    import cognee

    await cognee.add(text)
    await cognee.cognify()
    return {"status": "added"}


@app.get("/memory/search")
async def memory_search(q: str):
    """Example: query the agent's memory graph."""
    import cognee

    results = await cognee.search(q)
    return {"results": results}
