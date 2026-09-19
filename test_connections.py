"""
Run this after filling in .env to sanity-check that each sponsor's
service is reachable, before you start building on top of them.

    python test_connections.py
"""

import os
from dotenv import load_dotenv

load_dotenv()


def test_tavily():
    from tavily import TavilyClient

    key = os.getenv("TAVILY_API_KEY")
    if not key:
        print("[Tavily] SKIPPED - no TAVILY_API_KEY in .env")
        return

    client = TavilyClient(api_key=key)
    result = client.search("Ignite Room hackathon Delhi", max_results=1)
    print(f"[Tavily] OK - got {len(result.get('results', []))} result(s)")


def test_neo4j():
    from neo4j import GraphDatabase

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not password:
        print("[Neo4j] SKIPPED - no NEO4J_URI/PASSWORD in .env")
        return

    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.run("RETURN 1")
    driver.close()
    print("[Neo4j] OK - connected and ran a test query")


def test_cognee():
    key = os.getenv("LLM_API_KEY")
    if not key:
        print("[Cognee] SKIPPED - no LLM_API_KEY in .env")
        return

    # Cognee reads its LLM key from the environment itself (LLM_API_KEY),
    # so as long as it's set, this just confirms the package imports fine.
    import cognee  # noqa: F401

    print("[Cognee] OK - package imports fine and LLM_API_KEY is set")
    print("         (cognee.add(...) / cognee.cognify() need an event loop -")
    print("          try those directly inside your actual app)")


if __name__ == "__main__":
    print("Checking sponsor connections...\n")
    for name, fn in [
        ("Tavily", test_tavily),
        ("Neo4j", test_neo4j),
        ("Cognee", test_cognee),
    ]:
        try:
            fn()
        except Exception as e:
            print(f"[{name}] FAILED - {e}")
    print("\nDone. Render has no local test - you check that by deploying.")
