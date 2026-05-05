import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.graphs import Neo4jGraph
from neo4j import GraphDatabase
import time


# ========================= HELPERS =========================

def get_graph(database: str) -> Neo4jGraph:
    """Create a Neo4j graph connection for a specific user database."""
    return Neo4jGraph(
        url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
        database=database.lower(),
    )


def ensure_database_exists(database: str):
    # Force database name to lowercase
    database = database.lower() 
    
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        with driver.session(database="system") as session:
            print(f"🛠 Creating database '{database}'...")

            session.run(f"CREATE DATABASE `{database}` IF NOT EXISTS")

            # 🔥 Wait longer + stronger check
            for i in range(30):
                result = session.run(
                    "SHOW DATABASES YIELD name, currentStatus "
                    "WHERE name = $db RETURN currentStatus",
                    db=database
                ).data()

                if result:
                    status = result[0]["currentStatus"]
                    print(f"⏳ DB status: {status}")

                    if status.lower() == "online":
                        print(f"✅ Database '{database}' is ONLINE.")
                        return

                time.sleep(1)

            raise Exception(f"Database '{database}' not ready after waiting.")

    finally:
        driver.close()


# ========================= EXTRACTION =========================

def extract_all(text: str) -> dict:
    """Extract structured data from PDF text using regex."""
    data = {}

    # Clean bullet characters
    text = text.replace("•", "-")

    # ===== EXECUTIVES =====
    roles = ["CEO", "CTO", "COO", "CFO", "CCO"]
    executives = {}
    for role in roles:
        match = re.search(fr"{role}:\s*([^\n]+)", text)
        if match:
            executives[role] = match.group(1).strip()
    data["executives"] = executives

    # ===== MISSION =====
    mission = re.search(r"Mission Statement\s*(.*?)\s*Vision", text, re.DOTALL | re.IGNORECASE)
    if mission:
        data["mission"] = " ".join(mission.group(1).strip().split())

    # ===== VISION =====
    vision = re.search(r"Vision\s*(.*?)\s*Core Values", text, re.DOTALL | re.IGNORECASE)
    if vision:
        data["vision"] = " ".join(vision.group(1).strip().split())

    # ===== SERVICES & FEATURES =====
    # Try to extract services dynamically from PDF first
    services = extract_services(text)
    if services:
        data["services"] = services

    # ===== FINANCIAL OVERVIEW =====
    financial = {}
    patterns = {
        "Annual Revenue": r"Annual Revenue:\s*([^\n]+)",
        "Profit Margin": r"Profit Margin:\s*([^\n]+)",
        "R&D Investment": r"R&D Investment:\s*([^\n]+)",
        "Market Capitalization": r"Market Capitalization:\s*([^\n]+)",
    }
    for metric, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            financial[metric] = match.group(1).replace('\\', '').strip()
    data["financial"] = financial

    return data


def extract_services(text: str) -> dict:
    """
    Try to dynamically extract services and their bullet-point features.
    Falls back to an empty dict if nothing is found.
    """
    services = {}

    # Look for a "Services" section header and parse until next major section
    services_block = re.search(
        r"(?:Primary\s+)?Services?\s*\n(.*?)(?:\n[A-Z][^\n]{0,40}\n|\Z)",
        text, re.DOTALL | re.IGNORECASE
    )
    if not services_block:
        return services

    block = services_block.group(1)

    # Split by lines that look like service titles (capitalized, not starting with -)
    lines = block.split("\n")
    current_service = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("-") or line.startswith("*"):
            # Feature line
            if current_service:
                feature = line.lstrip("-* ").strip()
                if feature:
                    services[current_service].append(feature)
        else:
            # Potential service title
            if len(line) < 60 and not line[0].isdigit():
                current_service = line
                services[current_service] = []

    # Remove services with no features
    services = {k: v for k, v in services.items() if v}
    return services


# ========================= GRAPH INSERTION =========================

def insert_into_graph(graph: Neo4jGraph, data: dict, company_name: str):
    """Insert extracted data into Neo4j graph. Wipes existing data first."""
    
    # Wipe old data (safe since each user has their own DB or we scope by company)
    graph.query("MATCH (n) DETACH DELETE n")
    print("🗑️  Old graph data cleared.")

    node_count = 0

    # Company node
    graph.query(
        "MERGE (c:Company {name: $name})",
        params={"name": company_name}
    )
    node_count += 1

    # Executives
    for role, name in data.get("executives", {}).items():
        graph.query(f"""
            MATCH (c:Company {{name: $company}})
            MERGE (e:Executive {{name: $name}})
            MERGE (c)-[:HAS_{role}]->(e)
        """, params={"company": company_name, "name": name})
        node_count += 1

    # Mission
    if "mission" in data:
        graph.query("""
            MATCH (c:Company {name: $company})
            MERGE (m:Mission {text: $text})
            MERGE (c)-[:HAS_MISSION]->(m)
        """, params={"company": company_name, "text": data["mission"]})
        node_count += 1

    # Vision
    if "vision" in data:
        graph.query("""
            MATCH (c:Company {name: $company})
            MERGE (v:Vision {text: $text})
            MERGE (c)-[:HAS_VISION]->(v)
        """, params={"company": company_name, "text": data["vision"]})
        node_count += 1

    # Services & Features
    for service_name, features in data.get("services", {}).items():
        graph.query("""
            MATCH (c:Company {name: $company})
            MERGE (s:Service {name: $service_name})
            MERGE (c)-[:PRIMARY_SERVICES]->(s)
        """, params={"company": company_name, "service_name": service_name})
        node_count += 1

        for feature in features:
            graph.query("""
                MATCH (s:Service {name: $service_name})
                MERGE (f:Feature {description: $feature})
                MERGE (s)-[:INCLUDES_FEATURE]->(f)
            """, params={"service_name": service_name, "feature": feature})
            node_count += 1

    # Financial Metrics
    for metric_name, metric_value in data.get("financial", {}).items():
        graph.query("""
            MATCH (c:Company {name: $company})
            MERGE (f:FinancialMetric {name: $metric_name, value: $metric_value})
            MERGE (c)-[:FINANCIAL_OVERVIEW]->(f)
        """, params={
            "company": company_name,
            "metric_name": metric_name,
            "metric_value": metric_value
        })
        node_count += 1

    return node_count


# ========================= MAIN ENTRY POINT =========================

def build_graph_for_user(pdf_path: str, database: str) -> dict:
    """
    Build a Neo4j knowledge graph for a specific user from a PDF file.
    
    Args:
        pdf_path: Path to the uploaded PDF file.
        database: The user's Neo4j database name.
    
    Returns:
        A dict with build summary info.
    
    Raises:
        FileNotFoundError: If the PDF doesn't exist.
        Exception: If graph building fails.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at: {pdf_path}")

    print(f"📄 Loading PDF: {pdf_path}")
    loader = PyPDFLoader(str(pdf_path))
    docs = loader.load()

    if not docs:
        raise ValueError("PDF appears to be empty or unreadable.")

    full_text = "\n".join([doc.page_content for doc in docs])
    print(f"✅ PDF loaded ({len(full_text)} chars across {len(docs)} pages)")

    # Extract company name from text (or default)
    company_match = re.search(r"([A-Z][a-zA-Z]+ (?:Travels|Corp|Inc|Ltd|LLC|Co\.))", full_text)
    company_name = company_match.group(1) if company_match else "Unknown Company"
    print(f"🏢 Detected company: {company_name}")

    # Extract structured data
    data = extract_all(full_text)
    print(f"📊 Extracted: {len(data.get('executives', {}))} executives, "
          f"{len(data.get('services', {}))} services, "
          f"{len(data.get('financial', {}))} financial metrics")

    # Ensure database exists (for Neo4j Enterprise / multi-db setups)
    ensure_database_exists(database)

    time.sleep(2)

    # Connect and insert
    graph = get_graph(database)
    nodes_created = insert_into_graph(graph, data, company_name)
    graph.refresh_schema()

    print(f"✅ Graph built in database '{database}' with ~{nodes_created} nodes.")
    return {
        "company": company_name,
        "nodes_created": nodes_created,
        "database": database,
        "pages": len(docs),
    }


# ========================= STANDALONE RUN =========================

if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else "company_overview.pdf"
    db = sys.argv[2] if len(sys.argv) > 2 else "neo4j_fast"
    result = build_graph_for_user(pdf, db)
    print(f"\n🎉 Done: {result}")