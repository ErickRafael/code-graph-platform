"""Natural language query interface using Claude Code SDK.

This is an optimized version using Claude instead of OpenAI.
"""

from typing import Any, Dict, List, Optional
import json
import os
import re
import asyncio
from dataclasses import dataclass

# Claude Code SDK (would need: pip install claude-code-sdk)
# from claude_code_sdk import query, ClaudeCodeOptions

from neo4j import GraphDatabase, Driver

# ---------------------------------------------------------------------------
# Configuration & Schema (reused from original)
# ---------------------------------------------------------------------------

GRAPH_SCHEMA = """
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

FEW_SHOT_EXAMPLES = [
    {
        "q": "How many spaces are on floor 1?",
        "c": "MATCH (:Floor {level: 1})-[:HAS_SPACE]->(s:Space) RETURN count(s) AS space_count"
    },
    {
        "q": "List the names of all floors in the building",
        "c": "MATCH (:Building)-[:HAS_FLOOR]->(f:Floor) RETURN f.name ORDER BY f.level"
    },
    {
        "q": "What annotations are in the drawing?",
        "c": "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) RETURN a.text, a.layer ORDER BY a.text"
    },
    {
        "q": "Show all circular features with radius > 100",
        "c": "MATCH (:Floor)-[:HAS_FEATURE]->(f:Feature) WHERE f.type = 'CIRCLE' AND f.radius > 100 RETURN f"
    },
    {
        "q": "Calculate total wall length per floor",
        "c": """
MATCH (floor:Floor)-[:HAS_WALL]->(w:WallSegment)
WITH floor, w, 
     sqrt((w.end_x - w.start_x)^2 + (w.end_y - w.start_y)^2) AS length
RETURN floor.name, sum(length) AS total_wall_length
ORDER BY floor.level
"""
    }
]

# ---------------------------------------------------------------------------
# Claude SDK Implementation
# ---------------------------------------------------------------------------

@dataclass
class QuerySession:
    """Tracks multi-turn conversation state"""
    session_id: str
    history: List[Dict[str, str]]
    last_query: Optional[str] = None
    last_result: Optional[List[Dict]] = None

class ClaudeQueryInterface:
    """Enhanced query interface using Claude Code SDK"""
    
    def __init__(self):
        self.sessions: Dict[str, QuerySession] = {}
        self._driver = self._get_neo4j_driver()
    
    def _get_neo4j_driver(self) -> Driver:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "neo4j")
        return GraphDatabase.driver(uri, auth=(user, password))
    
    async def text_to_cypher_claude(self, user_question: str, session_id: Optional[str] = None) -> str:
        """Convert natural language to Cypher using Claude SDK"""
        
        # Build context from session if available
        context = ""
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            if session.last_query and session.last_result:
                context = f"""
Previous query: {session.last_query}
Previous Cypher: {session.history[-1].get('cypher', '')}
Result sample: {json.dumps(session.last_result[:3])}
"""
        
        # This would use actual Claude SDK
        # For now, showing the structure:
        system_prompt = f"""
You are a Cypher query expert for Neo4j CAD data.

Schema:
{GRAPH_SCHEMA}

Examples:
{json.dumps(FEW_SHOT_EXAMPLES, indent=2)}

{context}

Rules:
1. Return ONLY valid Cypher query
2. Use appropriate WHERE clauses for filtering
3. Include meaningful column aliases in RETURN
4. For complex calculations, use WITH clauses
5. Optimize for performance with proper index usage
"""
        
        # Simulated Claude SDK call:
        # options = ClaudeCodeOptions(
        #     max_turns=1,
        #     system_prompt=system_prompt,
        #     temperature=0.0
        # )
        
        # async for response in query(user_question, options):
        #     return self._extract_cypher(response)
        
        # Placeholder return
        return self._generate_cypher_placeholder(user_question)
    
    async def query_with_refinement(self, user_question: str, session_id: str, max_turns: int = 3) -> Dict[str, Any]:
        """Execute query with automatic refinement capability"""
        
        # Initialize session if new
        if session_id not in self.sessions:
            self.sessions[session_id] = QuerySession(session_id=session_id, history=[])
        
        session = self.sessions[session_id]
        
        for turn in range(max_turns):
            # Generate Cypher
            cypher = await self.text_to_cypher_claude(user_question, session_id)
            
            # Validate and execute
            try:
                results = self._execute_cypher(cypher)
                
                # Store in session
                session.history.append({
                    "question": user_question,
                    "cypher": cypher,
                    "turn": turn
                })
                session.last_query = user_question
                session.last_result = results
                
                # Check if refinement needed
                if await self._needs_refinement(user_question, results):
                    refinement = await self._suggest_refinement(user_question, cypher, results)
                    if refinement and turn < max_turns - 1:
                        user_question = refinement
                        continue
                
                return {
                    "status": "success",
                    "cypher": cypher,
                    "results": results,
                    "turns_used": turn + 1,
                    "refined": turn > 0
                }
                
            except Exception as e:
                # Try to auto-fix the query
                fixed_cypher = await self._auto_fix_cypher(cypher, str(e))
                if fixed_cypher and fixed_cypher != cypher:
                    try:
                        results = self._execute_cypher(fixed_cypher)
                        return {
                            "status": "success",
                            "cypher": fixed_cypher,
                            "results": results,
                            "auto_fixed": True
                        }
                    except:
                        pass
                
                return {
                    "status": "error",
                    "error": str(e),
                    "cypher": cypher
                }
    
    async def generate_complex_aggregation(self, requirement: str) -> str:
        """Generate complex aggregation queries with multiple steps"""
        
        system_prompt = f"""
You are a Neo4j expert specializing in complex aggregations.
Schema: {GRAPH_SCHEMA}

Generate sophisticated queries with:
1. Multiple WITH clauses for step-by-step calculation
2. Window functions where applicable  
3. Conditional aggregations
4. Proper grouping and ordering
5. Performance optimization
"""
        
        # This would use Claude SDK with multiple turns
        # to iteratively build complex query
        
        # Example of what it might generate:
        if "area" in requirement.lower() and "floor" in requirement.lower():
            return """
// Calculate areas with multiple aggregation levels
MATCH (b:Building)-[:HAS_FLOOR]->(f:Floor)-[:HAS_SPACE]->(s:Space)
WITH f, s, s.raw_points AS points
// Calculate area using shoelace formula
WITH f, s, reduce(area = 0, i IN range(0, size(points)-2) |
    area + (points[i][0] * points[i+1][1] - points[i+1][0] * points[i][1])
) AS raw_area
WITH f, s, abs(raw_area / 2.0) AS space_area
// Aggregate by floor
WITH f, collect({space: s.uid, area: space_area}) AS spaces, 
     sum(space_area) AS total_floor_area
// Add building level aggregation
MATCH (b:Building)-[:HAS_FLOOR]->(f)
RETURN b.name AS building,
       f.name AS floor, 
       f.level AS level,
       total_floor_area,
       size(spaces) AS space_count,
       spaces
ORDER BY f.level
"""
        
        return "// Complex query generation placeholder"
    
    async def _needs_refinement(self, question: str, results: List[Dict]) -> bool:
        """Determine if query results need refinement"""
        
        # Simple heuristics (would use Claude for smarter detection)
        if not results:
            return True
        if len(results) > 100:  # Too many results
            return True
        if "calculate" in question.lower() and not any("sum" in str(r) for r in results):
            return True
        
        return False
    
    async def _suggest_refinement(self, question: str, cypher: str, results: List[Dict]) -> Optional[str]:
        """Suggest query refinement based on results"""
        
        # This would use Claude to analyze results and suggest improvement
        # For now, simple logic:
        if not results:
            return f"{question} (include more details or broaden the search)"
        if len(results) > 100:
            return f"{question} (limit to most relevant results)"
        
        return None
    
    async def _auto_fix_cypher(self, broken_query: str, error: str) -> Optional[str]:
        """Attempt to automatically fix Cypher syntax errors"""
        
        # Would use Claude to fix, for now basic fixes:
        if "variable not defined" in error.lower():
            # Try to fix undefined variables
            return broken_query.replace("RETURN", "WITH * RETURN")
        
        return None
    
    def _execute_cypher(self, cypher: str) -> List[Dict[str, Any]]:
        """Execute validated Cypher query"""
        with self._driver.session() as session:
            # Validate first
            session.run(f"EXPLAIN {cypher}")
            
            # Execute
            result = session.run(cypher)
            return [record.data() for record in result]
    
    def _extract_cypher(self, content: str) -> str:
        """Extract Cypher from Claude response"""
        # Remove any markdown code blocks
        if "```" in content:
            match = re.search(r"```(?:cypher)?\n?(.*?)\n?```", content, re.S)
            if match:
                return match.group(1).strip()
        
        return content.strip()
    
    def _generate_cypher_placeholder(self, question: str) -> str:
        """Temporary placeholder for demo"""
        question_lower = question.lower()
        
        # Simple pattern matching for demo
        if "how many" in question_lower and "space" in question_lower:
            return "MATCH (:Floor)-[:HAS_SPACE]->(s:Space) RETURN count(s) AS total_spaces"
        elif "floor" in question_lower and "name" in question_lower:
            return "MATCH (:Building)-[:HAS_FLOOR]->(f:Floor) RETURN f.name ORDER BY f.level"
        elif "annotation" in question_lower:
            return "MATCH (:Floor)-[:HAS_ANNOTATION]->(a:Annotation) RETURN a.text, a.layer LIMIT 20"
        else:
            return "MATCH (n) RETURN n LIMIT 10"

# ---------------------------------------------------------------------------
# FastAPI Integration Functions
# ---------------------------------------------------------------------------

# Global instance
claude_interface = ClaudeQueryInterface()

async def process_query_claude(user_question: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Main entry point for Claude-powered queries"""
    
    if not session_id:
        # Single-turn query
        cypher = await claude_interface.text_to_cypher_claude(user_question)
        try:
            results = claude_interface._execute_cypher(cypher)
            return {
                "status": "success",
                "cypher": cypher,
                "results": results,
                "model": "claude-opus-4"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "cypher": cypher,
                "model": "claude-opus-4"
            }
    else:
        # Multi-turn with refinement
        return await claude_interface.query_with_refinement(user_question, session_id)

async def generate_cad_insights(building_uid: str) -> Dict[str, Any]:
    """Generate comprehensive insights about a CAD file"""
    
    # Gather basic statistics
    with claude_interface._driver.session() as session:
        stats_query = """
        MATCH (b:Building {uid: $uid})-[:HAS_FLOOR]->(f:Floor)
        OPTIONAL MATCH (f)-[:HAS_SPACE]->(s:Space)
        OPTIONAL MATCH (f)-[:HAS_WALL]->(w:WallSegment)
        OPTIONAL MATCH (f)-[:HAS_ANNOTATION]->(a:Annotation)
        WITH b, f, count(DISTINCT s) AS spaces, 
             count(DISTINCT w) AS walls,
             count(DISTINCT a) AS annotations
        RETURN b.name AS building_name,
               collect({
                   floor: f.name,
                   level: f.level,
                   spaces: spaces,
                   walls: walls,
                   annotations: annotations
               }) AS floor_stats
        """
        result = session.run(stats_query, uid=building_uid)
        stats = result.single()
    
    if not stats:
        return {"status": "error", "error": "Building not found"}
    
    # Would use Claude to generate insights
    # For demo, return structured analysis:
    insights = {
        "building": stats["building_name"],
        "summary": {
            "total_floors": len(stats["floor_stats"]),
            "total_spaces": sum(f["spaces"] for f in stats["floor_stats"]),
            "total_walls": sum(f["walls"] for f in stats["floor_stats"]),
            "total_annotations": sum(f["annotations"] for f in stats["floor_stats"])
        },
        "analysis": {
            "space_distribution": "Analyzing space distribution across floors...",
            "complexity_score": "Calculating architectural complexity...",
            "data_quality": "Assessing CAD data completeness..."
        },
        "recommendations": [
            "Consider adding more detailed annotations for spaces",
            "Wall segments could benefit from material property tags",
            "Floor level naming could be standardized"
        ]
    }
    
    return {
        "status": "success",
        "insights": insights,
        "generated_by": "claude-opus-4"
    }

# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Demo async execution
    async def demo():
        # Simple query
        result = await process_query_claude("How many floors are in the building?")
        print(f"Simple query result: {json.dumps(result, indent=2)}")
        
        # Complex aggregation
        complex_cypher = await claude_interface.generate_complex_aggregation(
            "Calculate total area per floor with space breakdown"
        )
        print(f"Complex query generated:\n{complex_cypher}")
        
        # Multi-turn refinement
        refined_result = await process_query_claude(
            "Show me all annotations about the project", 
            session_id="demo-session-123"
        )
        print(f"Refined query result: {json.dumps(refined_result, indent=2)}")
    
    # Run demo
    asyncio.run(demo())