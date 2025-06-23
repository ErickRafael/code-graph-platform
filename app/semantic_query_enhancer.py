"""Semantic Query Enhancement for CAD Data

This module provides intelligent query interpretation and correlation
to help users find information even when they don't use technical terms.
"""

from typing import List, Dict, Any, Tuple, Optional
import re
from neo4j import GraphDatabase
import os

class SemanticQueryEnhancer:
    """Enhances user queries with semantic understanding and smart correlations."""
    
    def __init__(self):
        self.driver = self._get_neo4j_driver()
        
        # Semantic mappings for common user terms
        self.term_mappings = {
            # Project identification
            "nome do projeto": ["project name", "project title", "nome", "titulo"],
            "projeto": ["project", "drawing", "plan", "planta"],
            "codigo do projeto": ["project code", "codigo", "referencia", "reference"],
            
            # Scale and measurements
            "escala": ["scale", "escala", "esc", "proportion"],
            "tamanho": ["size", "dimensions", "medidas", "dimensoes"],
            "metros": ["meters", "m", "units", "unidades"],
            
            # Building elements
            "parede": ["wall", "walls", "parede", "paredes", "muro"],
            "porta": ["door", "doors", "porta", "portas", "opening"],
            "janela": ["window", "windows", "janela", "janelas"],
            "escada": ["stairs", "stair", "escada", "escadas", "steps"],
            "elevador": ["elevator", "lift", "elevador", "ascensor"],
            
            # Spaces and areas
            "sala": ["room", "space", "sala", "ambiente", "area"],
            "banheiro": ["bathroom", "toilet", "wc", "banheiro", "lavabo"],
            "cozinha": ["kitchen", "cozinha", "copa"],
            "escritorio": ["office", "escritorio", "work"],
            
            # Technical elements
            "estrutura": ["structure", "structural", "estrutura", "estrutural"],
            "fundacao": ["foundation", "fundacao", "base"],
            "laje": ["slab", "laje", "floor"],
            "viga": ["beam", "viga", "structural"],
            "pilar": ["column", "pilar", "support"],
            
            # Infrastructure
            "eletrica": ["electrical", "eletrica", "power", "energia"],
            "hidraulica": ["plumbing", "hydraulic", "hidraulica", "agua"],
            "ar condicionado": ["hvac", "ac", "ventilation", "climatizacao"],
            
            # Drawing types
            "planta baixa": ["floor plan", "plan", "planta", "layout"],
            "corte": ["section", "cross-section", "corte", "secao"],
            "fachada": ["elevation", "facade", "fachada", "vista"],
            "detalhes": ["details", "detail", "detalhes", "detalhe"]
        }
        
        # Patterns for common information types
        self.info_patterns = {
            "project_codes": [
                r"[A-Z]{2,}\d+-[A-Z]{2,}-[A-Z]{2,}-[A-Z]{2,}-\d+-[A-Z]{2,}\d+-[A-Z]\d+",  # ECB1-EST-AP-CORP-221-PV32-R00
                r"[A-Z]{3,}\d+",  # ECB1, SBBI
                r"[A-Z]+-\d{3}-\d{4}",  # GRL-010-3004
            ],
            "scales": [
                r"1:\d+",  # 1:50, 1:100
                r"ESC:\s*1:\d+",  # ESC: 1:1000
                r"ESCALA\s+\d+:\d+",  # ESCALA 1:50
            ],
            "building_types": [
                r"AEROPORTO|AIRPORT",
                r"CORPORATIVO|CORPORATE",
                r"RESIDENCIAL|RESIDENTIAL", 
                r"COMERCIAL|COMMERCIAL",
                r"INDUSTRIAL"
            ]
        }
    
    def _get_neo4j_driver(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "neo4j")
        return GraphDatabase.driver(uri, auth=(user, password))
    
    def enhance_query(self, user_question: str) -> Dict[str, Any]:
        """Enhance user query with semantic understanding and smart correlations."""
        
        question_lower = user_question.lower()
        enhancements = {
            "original_question": user_question,
            "detected_intent": self._detect_intent(question_lower),
            "semantic_terms": self._extract_semantic_terms(question_lower),
            "suggested_queries": [],
            "context_queries": [],
            "explanation": ""
        }
        
        # Generate smart queries based on intent
        if enhancements["detected_intent"] == "project_info":
            enhancements["suggested_queries"] = self._generate_project_info_queries()
            enhancements["explanation"] = "Searching for project information in multiple locations (building names, annotations, metadata)"
            
        elif enhancements["detected_intent"] == "scale_info":
            enhancements["suggested_queries"] = self._generate_scale_queries()
            enhancements["explanation"] = "Looking for scale information in annotations and metadata"
            
        elif enhancements["detected_intent"] == "element_search":
            element_type = self._identify_element_type(question_lower)
            enhancements["suggested_queries"] = self._generate_element_queries(element_type)
            enhancements["explanation"] = f"Searching for {element_type} elements in various data types"
            
        elif enhancements["detected_intent"] == "count_query":
            count_type = self._identify_count_type(question_lower)
            enhancements["suggested_queries"] = self._generate_count_queries(count_type)
            enhancements["explanation"] = f"Counting {count_type} elements"
            
        else:
            # General exploration
            enhancements["suggested_queries"] = self._generate_exploration_queries()
            enhancements["explanation"] = "Exploring the drawing data to find relevant information"
        
        return enhancements
    
    def _detect_intent(self, question_lower: str) -> str:
        """Detect the user's intent from their question."""
        
        # More specific pattern matching
        if any(term in question_lower for term in ["quantos", "how many", "conta", "count", "numero", "number"]):
            return "count_query"
        elif any(term in question_lower for term in ["escala", "scale", "tamanho", "size", "dimensao", "medida"]):
            return "scale_info"
        elif any(term in question_lower for term in ["nome", "name", "titulo", "title", "codigo", "code"]) and any(term in question_lower for term in ["projeto", "project", "drawing"]):
            return "project_info"
        elif any(term in question_lower for term in ["parede", "wall", "porta", "door", "janela", "window", "escada", "stair", "sala", "room", "space"]):
            return "element_search"
        else:
            return "general_exploration"
    
    def _extract_semantic_terms(self, question_lower: str) -> List[str]:
        """Extract semantic terms that might relate to CAD elements."""
        
        terms = []
        for main_term, variants in self.term_mappings.items():
            if any(variant in question_lower for variant in variants):
                terms.append(main_term)
        return terms
    
    def _identify_element_type(self, question_lower: str) -> str:
        """Identify what type of element the user is asking about."""
        
        if any(term in question_lower for term in ["parede", "wall", "muro"]):
            return "walls"
        elif any(term in question_lower for term in ["porta", "door", "opening"]):
            return "doors"
        elif any(term in question_lower for term in ["janela", "window"]):
            return "windows"
        elif any(term in question_lower for term in ["escada", "stair", "steps"]):
            return "stairs"
        elif any(term in question_lower for term in ["sala", "room", "space", "ambiente"]):
            return "spaces"
        else:
            return "annotations"
    
    def _identify_count_type(self, question_lower: str) -> str:
        """Identify what the user wants to count."""
        
        if any(term in question_lower for term in ["sala", "room", "space", "ambiente"]):
            return "spaces"
        elif any(term in question_lower for term in ["parede", "wall"]):
            return "walls"
        elif any(term in question_lower for term in ["andar", "floor", "nivel"]):
            return "floors"
        else:
            return "elements"
    
    def _generate_project_info_queries(self) -> List[Dict[str, str]]:
        """Generate queries to find project information."""
        
        return [
            {
                "description": "Nome do projeto do Building",
                "cypher": "MATCH (b:Building) RETURN b.name AS project_name, b.uid"
            },
            {
                "description": "Códigos de projeto em anotações",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE a.text =~ '.*[A-Z]{2,}\\d+-[A-Z]{2,}-[A-Z]{2,}.*' 
                   OR a.text =~ '.*[A-Z]{3,}\\d+.*'
                RETURN DISTINCT a.text AS project_codes
                ORDER BY length(a.text) DESC
                LIMIT 10
                """
            },
            {
                "description": "Títulos e nomes em anotações grandes",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE length(a.text) > 10 
                  AND (toLower(a.text) CONTAINS 'projeto' 
                       OR toLower(a.text) CONTAINS 'torre'
                       OR toLower(a.text) CONTAINS 'edificio'
                       OR toLower(a.text) CONTAINS 'building')
                RETURN a.text AS project_info
                ORDER BY length(a.text) DESC
                LIMIT 10
                """
            }
        ]
    
    def _generate_scale_queries(self) -> List[Dict[str, str]]:
        """Generate queries to find scale information."""
        
        return [
            {
                "description": "Escalas em formato padrão (1:X)",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE a.text =~ '.*1:\\d+.*'
                RETURN a.text AS scale_info, a.insert_x, a.insert_y
                """
            },
            {
                "description": "Anotações sobre escala",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE toLower(a.text) CONTAINS 'escala' 
                   OR toLower(a.text) CONTAINS 'esc'
                   OR toLower(a.text) CONTAINS 'scale'
                RETURN a.text AS scale_annotations
                """
            },
            {
                "description": "Metadados de escala do arquivo",
                "cypher": """
                MATCH (m:Metadata) 
                RETURN m.type, m.dimscale, m.ltscale, m.cmlscale, m.celtscale
                """
            }
        ]
    
    def _generate_element_queries(self, element_type: str) -> List[Dict[str, str]]:
        """Generate queries for specific element types."""
        
        if element_type == "walls":
            return [
                {
                    "description": "Segmentos de parede",
                    "cypher": "MATCH (:Floor)-[:HAS_WALL]->(w:WallSegment) RETURN count(w) AS total_walls, collect(DISTINCT w.layer) AS layers"
                },
                {
                    "description": "Paredes por layer",
                    "cypher": "MATCH (:Floor)-[:HAS_WALL]->(w:WallSegment) RETURN w.layer, count(w) AS wall_count ORDER BY wall_count DESC"
                }
            ]
        elif element_type == "spaces":
            return [
                {
                    "description": "Espaços/salas",
                    "cypher": "MATCH (:Floor)-[:HAS_SPACE]->(s:Space) RETURN count(s) AS total_spaces, collect(DISTINCT s.layer) AS layers"
                },
                {
                    "description": "Espaços por layer",
                    "cypher": "MATCH (:Floor)-[:HAS_SPACE]->(s:Space) RETURN s.layer, count(s) AS space_count ORDER BY space_count DESC"
                }
            ]
        elif element_type == "stairs":
            return [
                {
                    "description": "Escadas em anotações",
                    "cypher": """
                    MATCH (a:Annotation) 
                    WHERE toLower(a.text) CONTAINS 'escada' 
                       OR toLower(a.text) CONTAINS 'stair'
                       OR toLower(a.text) CONTAINS 'degrau'
                    RETURN a.text, a.insert_x, a.insert_y
                    """
                }
            ]
        else:
            return [
                {
                    "description": f"Elementos relacionados a {element_type}",
                    "cypher": f"""
                    MATCH (a:Annotation) 
                    WHERE toLower(a.text) CONTAINS '{element_type}' 
                    RETURN a.text, a.insert_x, a.insert_y
                    LIMIT 20
                    """
                }
            ]
    
    def _generate_count_queries(self, count_type: str) -> List[Dict[str, str]]:
        """Generate counting queries."""
        
        if count_type == "spaces":
            return [
                {
                    "description": "Total de espaços",
                    "cypher": "MATCH (:Floor)-[:HAS_SPACE]->(s:Space) RETURN count(s) AS total_spaces"
                }
            ]
        elif count_type == "walls":
            return [
                {
                    "description": "Total de paredes", 
                    "cypher": "MATCH (:Floor)-[:HAS_WALL]->(w:WallSegment) RETURN count(w) AS total_walls"
                }
            ]
        else:
            return [
                {
                    "description": "Contagem geral de elementos",
                    "cypher": "MATCH (n) RETURN labels(n) AS element_type, count(n) AS count ORDER BY count DESC"
                }
            ]
    
    def _generate_exploration_queries(self) -> List[Dict[str, str]]:
        """Generate exploratory queries for general questions."""
        
        return [
            {
                "description": "Visão geral dos dados",
                "cypher": "MATCH (n) RETURN labels(n) AS types, count(n) AS count ORDER BY count DESC"
            },
            {
                "description": "Anotações mais relevantes",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE length(a.text) > 5 AND length(a.text) < 100
                RETURN a.text 
                ORDER BY length(a.text) DESC 
                LIMIT 15
                """
            },
            {
                "description": "Layers disponíveis",
                "cypher": """
                MATCH (n) 
                WHERE n.layer IS NOT NULL 
                RETURN DISTINCT n.layer AS layers, labels(n) AS element_types
                ORDER BY n.layer
                """
            }
        ]
    
    def execute_smart_search(self, user_question: str) -> Dict[str, Any]:
        """Execute a smart search that tries multiple approaches."""
        
        enhancements = self.enhance_query(user_question)
        results = {
            "interpretation": enhancements,
            "query_results": [],
            "best_match": None
        }
        
        with self.driver.session() as session:
            for query_info in enhancements["suggested_queries"]:
                try:
                    result = session.run(query_info["cypher"])
                    data = [record.data() for record in result]
                    
                    query_result = {
                        "description": query_info["description"],
                        "cypher": query_info["cypher"],
                        "results": data,
                        "result_count": len(data)
                    }
                    results["query_results"].append(query_result)
                    
                    # Determine best match based on result relevance
                    if data and not results["best_match"]:
                        results["best_match"] = query_result
                        
                except Exception as e:
                    results["query_results"].append({
                        "description": query_info["description"],
                        "cypher": query_info["cypher"],
                        "error": str(e)
                    })
        
        return results

# Global instance
semantic_enhancer = SemanticQueryEnhancer()