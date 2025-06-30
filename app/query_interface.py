"""Natural language query interface utilities.

Will be implemented in Phase 4.
"""

from typing import Any, Dict, List

import json
import os
import re
from dotenv import load_dotenv

# Carregar variáveis de ambiente do diretório pai
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from openai import OpenAI
from neo4j import GraphDatabase, Driver

# Back to working OpenAI SDK with proper configuration
import asyncio
from openai import OpenAI

# ---------------------------------------------------------------------------
# Graph schema & examples
# ---------------------------------------------------------------------------

GRAPH_SCHEMA = (
    """
Graph schema (labels and relationships):
(:Building) -[:HAS_FLOOR]-> (:Floor)
(:Building) -[:HAS_METADATA]-> (:Metadata)
(:Floor) -[:HAS_SPACE]-> (:Space)
(:Floor) -[:HAS_WALL]-> (:WallSegment)
(:Floor) -[:HAS_FEATURE]-> (:Feature)
(:Floor) -[:HAS_ANNOTATION]-> (:Annotation)
Each node has a unique `uid` property. Additional common properties:
Building: name
Floor: name, level
Space: raw_points (list of points), point_count, layer
WallSegment: start_x, start_y, start_z, end_x, end_y, end_z, layer
Feature: type (CIRCLE/ARC), center_x, center_y, center_z, radius, layer
Annotation: text, insert_x, insert_y, insert_z, height, layer
Metadata: type, dimscale, ltscale, cmlscale, celtscale
    """
).strip()

FEW_SHOT_EXAMPLES: List[Dict[str, str]] = [
    {
        "q": "How many spaces are on floor 1?",
        "c": (
            "MATCH (:Floor {level: 1})-[:HAS_SPACE]->(s:Space)\n"
            "RETURN count(s) AS space_count"
        ),
    },
    {
        "q": "List the names of all floors in the building",
        "c": "MATCH (:Building)-[:HAS_FLOOR]->(f:Floor) RETURN f.name ORDER BY f.level",
    },
    {
        "q": "What annotations are in the drawing?",
        "c": "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) RETURN a.text, a.layer ORDER BY a.text",
    },
    {
        "q": "Show me all wall segments",
        "c": "MATCH (:Floor)-[:HAS_WALL]->(w:WallSegment) RETURN w.uid, w.start_x, w.start_y, w.end_x, w.end_y, w.layer",
    },
    {
        "q": "What is the scale of the project?",
        "c": "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) WHERE toLower(a.text) CONTAINS 'escala' OR a.text CONTAINS '1:' OR toLower(a.text_value) CONTAINS 'escala' OR a.text_value CONTAINS '1:' RETURN COALESCE(a.text, a.text_value) AS scale_info",
    },
    {
        "q": "Qual a escala do projeto?",
        "c": "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) WHERE toLower(a.text) CONTAINS 'escala' OR a.text CONTAINS '1:' OR toLower(a.text_value) CONTAINS 'escala' OR a.text_value CONTAINS '1:' RETURN COALESCE(a.text, a.text_value) AS scale_info",
    },
    {
        "q": "Do que se trata este projeto?",
        "c": "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) WHERE toLower(a.text) CONTAINS 'aeroporto' OR toLower(a.text) CONTAINS 'sbbi' OR toLower(a.text) CONTAINS 'projeto' RETURN a.text LIMIT 10",
    },
    {
        "q": "What is this project about?",
        "c": "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) WHERE toLower(a.text) CONTAINS 'aeroporto' OR toLower(a.text) CONTAINS 'airport' OR toLower(a.text) CONTAINS 'sbbi' RETURN a.text LIMIT 10",
    },
    {
        "q": "Qual o tipo de projeto?",
        "c": "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) WHERE toLower(a.text) CONTAINS 'aeroporto' OR toLower(a.text) CONTAINS 'adequação' OR a.text = 'TIPO' RETURN a.text LIMIT 10",
    },
    {
        "q": "Quais as legendas do projeto?",
        "c": "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) WHERE toLower(a.text) CONTAINS 'faixa' OR toLower(a.text) CONTAINS 'área' OR toLower(a.text) CONTAINS 'legenda' RETURN DISTINCT a.text ORDER BY a.text LIMIT 15",
    },
    {
        "q": "What are the project legends?",
        "c": "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) WHERE toLower(a.text) CONTAINS 'faixa' OR toLower(a.text) CONTAINS 'área' OR toLower(a.text) CONTAINS 'legenda' RETURN DISTINCT a.text ORDER BY a.text LIMIT 15",
    },
]

SYSTEM_PROMPT = (
    "You are an intelligent CAD/DWG project analysis assistant with deep understanding of architectural and engineering drawings. "
    "You can perform two types of analysis: "
    "\n1. INTELLIGENT ANALYSIS: For questions about 'what is this project', 'do que se trata', 'análise completa', use the intelligent_project_analyzer module to provide comprehensive insights about project type, purpose, scale, complexity, and key elements."
    "\n2. SPECIFIC QUERIES: For specific questions, translate to Cypher queries for Neo4j containing CAD data."
    "\nWhen users ask about scale ('escala'), look in both a.text and a.text_value properties of Annotation nodes for textual scale information like 'ESCALA H 1:1500'. Use COALESCE(a.text, a.text_value) to access text content."
    "\nFor specific queries, always output a JSON object with a single key `cypher` containing ONLY the query. "
    "For intelligent analysis, return the direct analysis result with rich formatting and insights."
    "\nDo not include explanations or formatting code fences. Do not use UNION queries."
)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_prompt(user_question: str) -> List[Dict[str, str]]:  # noqa: D401
    """Construct the messages array for the OpenAI ChatCompletion API."""

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Schema:\n{GRAPH_SCHEMA}"},
    ]

    for ex in FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": ex["q"]})
        messages.append({"role": "assistant", "content": json.dumps({"cypher": ex["c"]})})

    # Actual question
    messages.append({"role": "user", "content": user_question})
    return messages


# ---------------------------------------------------------------------------
# Cypher generation
# ---------------------------------------------------------------------------


def _extract_cypher_from_response(content: str) -> str:
    """Extract the Cypher string from the model response."""

    # Attempt JSON parse directly
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "cypher" in data:
            return data["cypher"].strip()
    except json.JSONDecodeError:
        pass

    # Strip code fences if present
    code_match = re.search(r"```(?:json)?(.*?)```", content, re.S)
    if code_match:
        inner = code_match.group(1).strip()
        try:
            data = json.loads(inner)
            if "cypher" in data:
                return data["cypher"].strip()
        except json.JSONDecodeError:
            return inner.strip()

    # Fallback: return whole content
    return content.strip()


# Initialize OpenAI client (back to working version)
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    client = OpenAI(api_key=openai_api_key)
else:
    client = None

# Compact schema for API calls (to avoid connection issues with large payloads)
COMPACT_SCHEMA = """
(:Building)-[:HAS_FLOOR]->(:Floor)
(:Floor)-[:HAS_SPACE]->(:Space)
(:Floor)-[:HAS_WALL]->(:WallSegment)  
(:Floor)-[:HAS_ANNOTATION]->(a:Annotation)
Properties: Space.raw_points, WallSegment.start_x/y/z,end_x/y/z, Annotation.text,insert_x/y/z
"""

def smart_query_router(user_question: str) -> str:
    """Route question to appropriate handler - intelligent analysis or Cypher query"""
    question_lower = user_question.lower()
    
    # Check for intelligent analysis triggers
    intelligent_triggers = ["do que se trata", "sobre o que", "what is this project", "project about", 
                          "análise completa", "análise do projeto", "resumo do projeto", "entenda o projeto"]
    
    if any(term in question_lower for term in intelligent_triggers):
        try:
            from intelligent_project_analyzer import analyze_project_intelligently
            return analyze_project_intelligently()
        except Exception as e:
            return f"❌ Erro na análise inteligente: {e}"
    
    # Otherwise, use regular Cypher conversion
    return text_to_cypher(user_question)


def text_to_cypher(user_question: str, model: str = "gpt-4o") -> str:  # noqa: D401
    """Call OpenAI to convert text to Cypher and return the query string."""

    if not client or not client.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    # Use compact prompt to avoid connection issues
    user_content = f"Convert to Cypher: {user_question}\nSchema: {COMPACT_SCHEMA}\nReturn only the Cypher query:"

    # Retry mechanism for better reliability
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a Cypher query expert for Neo4j CAD data."},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.0,
                max_tokens=200,
                timeout=20  # Shorter timeout to fail faster
            )
            content = response.choices[0].message.content.strip()
            
            # Clean up the response (remove markdown, explanations, etc.)
            if "```" in content:
                # Extract from code block
                import re
                match = re.search(r"```(?:cypher)?\n?(.*?)\n?```", content, re.S)
                if match:
                    content = match.group(1).strip()
            
            # Remove common prefixes
            if content.startswith("```"):
                content = content.replace("```", "").strip()
            if content.startswith("cypher"):
                content = content[6:].strip()
                
            return content
            
        except Exception as e:
            if attempt < 2:  # Not the last attempt
                import time
                time.sleep(1)  # Brief delay before retry
                continue
            else:
                # Last attempt failed, provide fallback
                return _generate_fallback_query(user_question)

def _generate_fallback_query(user_question: str) -> str:
    """Generate a fallback Cypher query using semantic understanding."""
    
    try:
        # Import here to avoid circular imports
        from semantic_query_enhancer import semantic_enhancer
        
        # Use semantic enhancer to generate smart query
        smart_results = semantic_enhancer.execute_smart_search(user_question)
        
        # Return the best matching query
        if smart_results["best_match"]:
            return smart_results["best_match"]["cypher"]
            
        # If no smart match, try the first suggested query
        if smart_results["query_results"]:
            for result in smart_results["query_results"]:
                if "cypher" in result and "error" not in result:
                    return result["cypher"]
    
    except Exception:
        # If semantic enhancer fails, use basic patterns
        pass
    
    # Basic fallback patterns (as backup)
    question_lower = user_question.lower()
    
    if any(term in question_lower for term in ["do que se trata", "sobre o que", "what is this project", "project about", "análise completa", "análise do projeto", "resumo do projeto", "entenda o projeto"]):
        # 🧠 Trigger para análise inteligente completa
        from intelligent_project_analyzer import analyze_project_intelligently
        return analyze_project_intelligently()
    elif any(term in question_lower for term in ["nome", "name", "projeto", "project", "titulo"]):
        return """
        MATCH (b:Building) RETURN b.name AS project_name
        UNION
        MATCH (a:Annotation) WHERE a.text =~ '.*[A-Z]{2,}\\d+-[A-Z]{2,}.*' RETURN a.text AS project_name LIMIT 5
        """
    elif any(term in question_lower for term in ["escala", "scale"]):
        return """
        MATCH (a:Annotation) 
        WHERE a.text =~ '.*1:\\d+.*' OR toLower(a.text) CONTAINS 'escala'
        OR a.text_value =~ '.*1:\\d+.*' OR toLower(a.text_value) CONTAINS 'escala'
        RETURN COALESCE(a.text, a.text_value) AS scale_info
        """
    elif "annotation" in question_lower:
        return "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) RETURN a.text, a.insert_x, a.insert_y LIMIT 20"
    elif "wall" in question_lower:
        return "MATCH (:Floor)-[:HAS_WALL]->(w:WallSegment) RETURN w.start_x, w.start_y, w.end_x, w.end_y LIMIT 20"
    elif "space" in question_lower:
        return "MATCH (:Floor)-[:HAS_SPACE]->(s:Space) RETURN s.uid, s.layer, s.point_count LIMIT 20"
    elif "how many" in question_lower or "quantos" in question_lower:
        if "space" in question_lower or "sala" in question_lower:
            return "MATCH (:Floor)-[:HAS_SPACE]->(s:Space) RETURN count(s) AS total_spaces"
        elif "wall" in question_lower or "parede" in question_lower:
            return "MATCH (:Floor)-[:HAS_WALL]->(w:WallSegment) RETURN count(w) AS total_walls"
        else:
            return "MATCH (n) RETURN labels(n) AS element_types, count(n) AS count ORDER BY count DESC"
    
    # Default exploration
    return "MATCH (n) RETURN labels(n) AS node_types, count(n) AS count ORDER BY node_types"

async def smart_query_router_async(user_question: str) -> str:
    """Async version of smart query router"""
    import concurrent.futures
    
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, smart_query_router, user_question)


async def text_to_cypher_async(user_question: str, model: str = "gpt-4o") -> str:  # noqa: D401
    """Async version that runs the sync function in a thread pool."""
    import concurrent.futures
    
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, text_to_cypher, user_question, model)


# ---------------------------------------------------------------------------
# Cypher execution helpers
# ---------------------------------------------------------------------------


def _get_neo4j_driver() -> Driver:  # duplicated helper (could share via utils)
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "neo4j")
    return GraphDatabase.driver(uri, auth=(user, password))



def execute_cypher_query(cypher: str) -> List[Dict[str, Any]]:  # noqa: D401
    """Validate & execute Cypher, returning list-of-dict results."""

    driver = _get_neo4j_driver()
    with driver.session() as session:
        # Validate:
        try:
            session.run(f"EXPLAIN {cypher}")
        except Exception as exc:
            raise ValueError(f"Cypher validation failed: {exc}") from exc

        # Execute:
        result = session.run(cypher)
        data = [record.data() for record in result]

    driver.close()
    return data 