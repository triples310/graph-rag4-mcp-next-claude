import os
from dotenv import load_dotenv

load_dotenv()

from langchain_ollama import ChatOllama
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate


# ========================= LLM =========================

def get_llm():
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct"),
        temperature=0,
        num_ctx=4096,
        num_predict=1024,
    )


# ========================= GRAPH =========================

def get_graph(database: str) -> Neo4jGraph:
    return Neo4jGraph(
        url=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
        database=database.lower(),
    )


# ========================= GRAPH HEALTH CHECK =========================

def is_graph_populated(graph: Neo4jGraph) -> bool:
    """Check if the graph has any data."""
    try:
        result = graph.query("MATCH (n) RETURN count(n) AS count LIMIT 1")
        return result[0]["count"] > 0 if result else False
    except Exception:
        return False


def get_schema_info(graph: Neo4jGraph) -> dict:
    """
    Dynamically get node labels and relationship types from the user's graph.
    This lets the prompt adapt to whatever PDF was uploaded.
    """
    try:
        labels_result = graph.query("CALL db.labels() YIELD label RETURN collect(label) AS labels")
        rels_result = graph.query(
            "CALL db.relationshipTypes() YIELD relationshipType "
            "RETURN collect(relationshipType) AS rels"
        )
        labels = labels_result[0]["labels"] if labels_result else []
        rels = rels_result[0]["rels"] if rels_result else []

        # Get company name if exists
        company_result = graph.query(
            "MATCH (c:Company) RETURN c.name AS name LIMIT 1"
        )
        company_name = company_result[0]["name"] if company_result else "the company"

        return {"labels": labels, "relationships": rels, "company_name": company_name}
    except Exception:
        return {"labels": [], "relationships": [], "company_name": "the company"}


# ========================= DYNAMIC CYPHER PROMPT =========================

def build_cypher_prompt(company_name: str, labels: list, relationships: list) -> PromptTemplate:
    """
    Build a Cypher prompt that adapts to the user's actual graph schema.
    """
    # Format schema lines
    schema_lines = "\n".join([f"- (:{label})" for label in labels]) if labels else "- No labels found"
    rel_lines = "\n".join([f"- [:{rel}]" for rel in relationships]) if relationships else "- No relationships found"

    # Build executive relationship examples dynamically
    exec_rels = [r for r in relationships if r.startswith("HAS_")]
    exec_examples = ""
    if exec_rels:
        sample = exec_rels[0]
        role = sample.replace("HAS_", "")
        # FIX: Use quadruple braces {{{{ }}}} for Cypher properties inside f-strings
        exec_examples = f"""
Question: who is the {role}?
Cypher:
MATCH (c:Company {{{{name: "{company_name}"}}}})-[:{sample}]->(e:Executive)
RETURN e.name AS name
"""

    # FIX: Use quadruple braces {{{{ }}}} for ALL node properties
    # Leave {{question}} as double braces so Langchain receives it as {question}
    template = f"""You are an expert Neo4j Cypher query writer.

Graph Schema:
Node Labels:
{schema_lines}

Relationship Types:
{rel_lines}

Company in graph: "{company_name}"

Rules:
- ALWAYS start with MATCH (c:Company {{{{name: "{company_name}"}}}})
- Use ONLY the relationships listed in the schema above. NEVER invent new ones.
- Return ONLY the Cypher query. No explanation, no markdown, no ```cypher.
- For financial questions, use FINANCIAL_OVERVIEW relationship.
- For services, use PRIMARY_SERVICES and INCLUDES_FEATURE.
- If asked about a general topic with no obvious relationship, return general Company info.

Examples:

Question: what are the primary services?
Cypher:
MATCH (c:Company {{{{name: "{company_name}"}}}})-[:PRIMARY_SERVICES]->(s:Service)
RETURN s.name AS service

Question: what is the mission?
Cypher:
MATCH (c:Company {{{{name: "{company_name}"}}}})-[:HAS_MISSION]->(m:Mission)
RETURN m.text AS mission

Question: tell me about the financial overview
Cypher:
MATCH (c:Company {{{{name: "{company_name}"}}}})-[:FINANCIAL_OVERVIEW]->(f:FinancialMetric)
RETURN f.name AS metric, f.value AS value
{exec_examples}
Now answer this question:

Question: {{question}}
Cypher:
"""
    return PromptTemplate(template=template, input_variables=["question"])


# ========================= CHAIN FACTORY =========================

def build_chain(database: str) -> GraphCypherQAChain:
    """Build a fresh chain for a user's database."""
    graph = get_graph(database)
    graph.refresh_schema()
    schema_info = get_schema_info(graph)

    cypher_prompt = build_cypher_prompt(
        company_name=schema_info["company_name"],
        labels=schema_info["labels"],
        relationships=schema_info["relationships"],
    )

    return GraphCypherQAChain.from_llm(
        llm=get_llm(),
        graph=graph,
        cypher_prompt=cypher_prompt,
        verbose=True,
        allow_dangerous_requests=True,
        return_intermediate_steps=True,
        top_k=5,
    ), graph


# ========================= SAFE RESPONSE =========================

def get_chatbot_response(question: str, database: str) -> str:
    """
    Get a chatbot response for a user's question using their graph.

    Safety guarantees:
    - If the database is empty or unreachable, returns a friendly message.
    - If the LLM generates a bad Cypher query, catches the error gracefully.
    - Never crashes the API.
    """
    if not question.strip():
        return "Please ask a question."

    # Step 1: connect and health-check
    try:
        graph = get_graph(database)
        graph.refresh_schema()
    except Exception as e:
        return (
            f"I couldn't connect to your knowledge graph. "
            f"Please try re-uploading your PDF. (Error: {e})"
        )

    if not is_graph_populated(graph):
        return (
            "Your knowledge graph is empty. "
            "Please upload a PDF first so I can answer questions about it."
        )

    # Step 2: build and run the chain
    try:
        chain, _ = build_chain(database)
        result = chain.invoke({"query": question})
        answer = result.get("result", "").strip()

        if not answer or answer.lower() in ["i don't know", "i don't know.", ""]:
            return (
                "I couldn't find a clear answer in your knowledge graph. "
                "Try rephrasing your question or ask about services, executives, "
                "financials, or the company mission."
            )

        return answer

    except Exception as e:
        error_msg = str(e)
        # Common Neo4j / Cypher errors
        if "SyntaxError" in error_msg or "Invalid" in error_msg:
            return (
                "I had trouble forming a query for that question. "
                "Try asking about: executives, services, financials, or the company mission."
            )
        if "database" in error_msg.lower() and "not exist" in error_msg.lower():
            return (
                "Your knowledge graph database doesn't exist yet. "
                "Please upload a PDF to create it."
            )
        return f"Something went wrong while answering your question: {error_msg}"


# ========================= STANDALONE CLI =========================

if __name__ == "__main__":
    import sys
    database = sys.argv[1] if len(sys.argv) > 1 else os.getenv("NEO4J_DATABASE", "neo4j")

    print(f"🤖 Chatbot connected to database: {database}")
    print("Type 'exit' to quit.\n")

    graph = get_graph(database)
    if not is_graph_populated(graph):
        print("⚠️  Graph is empty. Please build it first with build_graph.py\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in ["exit", "quit", "bye"]:
            print("Goodbye!")
            break
        if not question:
            continue
        print("Thinking...")
        answer = get_chatbot_response(question, database)
        print(f"\nBot: {answer}\n")