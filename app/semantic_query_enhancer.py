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
            "escala": ["scale", "escala", "esc", "proportion", "1:", "1/"],
            "tamanho": ["size", "dimensions", "medidas", "dimensoes"],
            "metros": ["meters", "m", "units", "unidades"],
            "normas": ["normas", "standards", "specifications", "specs", "codigo", "abnt", "nbr"],
            
            # Visual and color terms
            "cor": ["color", "cor", "cores", "colors", "tonalidade", "shade"],
            "verde": ["green", "verde", "vegetation", "vegetação"],
            "azul": ["blue", "azul", "water", "agua"],
            "amarelo": ["yellow", "amarelo", "equipment", "equipamento"],
            "vermelho": ["red", "vermelho", "warning", "alerta"],
            "cinza": ["gray", "grey", "cinza", "pavement", "pavimento"],
            "branco": ["white", "branco", "background", "fundo"],
            "padrão": ["pattern", "padrão", "padrões", "patterns", "textura", "texture"],
            "pontilhado": ["dotted", "pontilhado", "dots", "pontos"],
            "tracejado": ["dashed", "tracejado", "dashes", "traços"],
            "sólido": ["solid", "sólido", "cheio", "filled"],
            "listrado": ["striped", "listrado", "stripes", "listras"],
            "hachurado": ["hatched", "hachurado", "crosshatched", "hachuras"],
            "legenda": ["legend", "legenda", "legendas", "legends", "indicação", "indication"],
            
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
        
        # OCR-specific enhancement patterns
        self.ocr_patterns = {
            "discovered_text": [
                "descoberto", "discovered", "novo", "new", "adicional"
            ],
            "validated_text": [
                "validado", "validated", "confirmado", "confirmed"
            ],
            "high_confidence": [
                "alta confiança", "high confidence", "certeza"
            ]
        }
    
    def _get_neo4j_driver(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password123")
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
            enhancements["explanation"] = "Buscando informações de escala em anotações, metadados, e padrões numéricos (1:X, H 1:X, etc.)"
            
        elif enhancements["detected_intent"] == "annotation_search":
            enhancements["suggested_queries"] = self._generate_annotation_queries()
            enhancements["explanation"] = "Buscando todas as anotações e textos do desenho"
            
        elif enhancements["detected_intent"] == "element_search":
            element_type = self._identify_element_type(question_lower)
            enhancements["suggested_queries"] = self._generate_element_queries(element_type)
            enhancements["explanation"] = f"Searching for {element_type} elements in various data types"
            
        elif enhancements["detected_intent"] == "count_query":
            count_type = self._identify_count_type(question_lower)
            enhancements["suggested_queries"] = self._generate_count_queries(count_type)
            enhancements["explanation"] = f"Counting {count_type} elements"
            
        elif enhancements["detected_intent"] == "ocr_query":
            ocr_type = self._identify_ocr_query_type(question_lower)
            enhancements["suggested_queries"] = self._generate_ocr_queries(ocr_type)
            enhancements["explanation"] = f"Searching OCR data for {ocr_type} information"
            
        elif enhancements["detected_intent"] == "technical_standards":
            enhancements["suggested_queries"] = self._generate_technical_standards_queries()
            enhancements["explanation"] = "Searching for technical standards and norms"
            
        elif enhancements["detected_intent"] == "color_search":
            color_term = self._extract_color_term(question_lower)
            enhancements["suggested_queries"] = self._generate_color_search_queries(color_term)
            enhancements["explanation"] = f"Buscando por cores{'(' + color_term + ')' if color_term else ''} em legendas visuais"
            
        elif enhancements["detected_intent"] == "pattern_search":
            pattern_term = self._extract_pattern_term(question_lower)
            enhancements["suggested_queries"] = self._generate_pattern_search_queries(pattern_term)
            enhancements["explanation"] = f"Buscando por padrões visuais{'(' + pattern_term + ')' if pattern_term else ''}"
            
        elif enhancements["detected_intent"] == "visual_legend_search":
            enhancements["suggested_queries"] = self._generate_visual_legend_search_queries()
            enhancements["explanation"] = "Análise completa de legendas visuais incluindo cores e padrões"
            
        elif enhancements["detected_intent"] == "legend_search":
            enhancements["suggested_queries"] = self._generate_legend_queries()
            enhancements["explanation"] = "Buscando legendas, cores e indicações do projeto"
            
        else:
            # General exploration (now includes OCR data)
            enhancements["suggested_queries"] = self._generate_exploration_queries()
            enhancements["explanation"] = "Exploring the drawing data to find relevant information"
        
        return enhancements
    
    def execute_smart_search(self, user_question: str) -> Dict[str, Any]:
        """Execute smart search with multiple query approaches and return best results."""
        
        enhancements = self.enhance_query(user_question)
        query_results = []
        
        with self.driver.session() as session:
            for query_info in enhancements["suggested_queries"]:
                try:
                    result = session.run(query_info["cypher"])
                    data = result.data()
                    
                    query_results.append({
                        "description": query_info["description"],
                        "cypher": query_info["cypher"],
                        "results": data,
                        "success": True,
                        "result_count": len(data)
                    })
                except Exception as e:
                    query_results.append({
                        "description": query_info["description"],
                        "cypher": query_info["cypher"],
                        "results": [],
                        "success": False,
                        "error": str(e),
                        "result_count": 0
                    })
        
        # Find the best result (most results, or first successful one)
        best_match = None
        if query_results:
            # Sort by success and result count
            successful_results = [r for r in query_results if r["success"] and r["result_count"] > 0]
            if successful_results:
                best_match = max(successful_results, key=lambda x: x["result_count"])
            elif any(r["success"] for r in query_results):
                best_match = next(r for r in query_results if r["success"])
        
        return {
            "interpretation": {
                "original_question": user_question,
                "detected_intent": enhancements["detected_intent"],
                "semantic_terms": enhancements["semantic_terms"],
                "explanation": enhancements["explanation"]
            },
            "query_results": query_results,
            "best_match": best_match,
            "total_queries_executed": len(query_results),
            "successful_queries": len([r for r in query_results if r["success"]])
        }
    
    def _detect_intent(self, question_lower: str) -> str:
        """Detect the user's intent from their question with improved logic."""
        
        # Visual and color searches - HIGHEST PRIORITY for visual queries
        if any(term in question_lower for term in ["cores da legenda", "colors of legend", "cores das legendas", "visual legend"]):
            return "visual_legend_search"
        elif any(term in question_lower for term in ["cor", "cores", "color", "colors", "verde", "azul", "amarelo", "vermelho"]):
            return "color_search"
        elif any(term in question_lower for term in ["padrão", "padrões", "pattern", "patterns", "pontilhado", "tracejado", "sólido"]):
            return "pattern_search"
        
        # Legend queries - HIGHEST PRIORITY 
        elif any(term in question_lower for term in ["legenda", "legendas", "legend", "legends", "indicações", "indications", "simbolo", "simbolos", "symbol", "symbols"]):
            return "legend_search"
        
        # OCR-specific queries
        elif any(term in question_lower for term in ["ocr", "descoberto", "discovered", "validado", "validated", "confiança", "confidence"]):
            return "ocr_query"
        
        # Technical standards
        elif any(term in question_lower for term in ["norma", "standard", "técnica", "codigo", "abnt", "nbr", "fck", "mpa"]):
            return "technical_standards"
        
        # Scale and dimensions - improved detection
        elif any(term in question_lower for term in ["escala", "scale", "tamanho", "size", "dimensao", "dimensões", "medida", "medidas"]):
            # More specific patterns for scale questions
            if any(term in question_lower for term in ["qual", "what", "onde", "where", "mostra", "show", "tem", "has", "existe", "e", "is"]):
                return "scale_info"
            elif any(term in question_lower for term in ["quantos", "how many", "conta", "count"]):
                return "count_query"  # For questions like "quantas escalas tem?"
            else:
                return "scale_info"  # Default to scale info for scale-related questions
        
        # Counting queries - be more specific about what is being counted
        elif any(term in question_lower for term in ["quantos", "how many", "conta", "count", "numero", "number"]):
            return "count_query"
        
        # Project information
        elif (any(term in question_lower for term in ["nome", "name", "titulo", "title", "codigo", "code", "trata", "sobre"]) 
              and any(term in question_lower for term in ["projeto", "project", "drawing"])) or "qual" in question_lower and any(term in question_lower for term in ["projeto", "project"]):
            return "project_info"
        
        # Geometric features - improved detection
        elif any(term in question_lower for term in ["circle", "circular", "circulo", "round", "feature", "geometric"]):
            return "element_search" 
        
        # Building elements
        elif any(term in question_lower for term in ["parede", "wall", "porta", "door", "janela", "window", "escada", "stair", "sala", "room", "space", "ambiente"]):
            return "element_search"
        
        # Annotation searching - better patterns
        elif (any(term in question_lower for term in ["annotation", "annotations", "anotação", "anotações", "texto", "text"]) 
              and any(term in question_lower for term in ["what", "quais", "que", "show", "mostra", "are", "estão", "tem", "have", "in", "no", "na"])):
            return "annotation_search"
        elif any(term in question_lower for term in ["annotation", "anotação", "texto", "text"]):
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
        """Identify what type of element the user is asking about with improved detection."""
        
        # Geometric features first (most specific)
        if any(term in question_lower for term in ["circle", "circular", "circulo", "round"]):
            return "circles"
        elif any(term in question_lower for term in ["feature", "geometric", "geometr"]):
            return "features"
        
        # Building elements
        elif any(term in question_lower for term in ["parede", "wall", "muro"]):
            return "walls"
        elif any(term in question_lower for term in ["porta", "door", "opening"]):
            return "doors"
        elif any(term in question_lower for term in ["janela", "window"]):
            return "windows"
        elif any(term in question_lower for term in ["escada", "stair", "steps"]):
            return "stairs"
        elif any(term in question_lower for term in ["sala", "room", "space", "ambiente"]):
            return "spaces"
        
        # Text and annotations
        elif any(term in question_lower for term in ["annotation", "anotação", "texto", "text"]):
            return "annotations"
            
        else:
            return "annotations"
    
    def _identify_count_type(self, question_lower: str) -> str:
        """Identify what the user wants to count with improved detection."""
        
        # Geometric features first
        if any(term in question_lower for term in ["circle", "circular", "circulo", "round"]):
            return "circles"
        elif any(term in question_lower for term in ["feature", "geometric", "geometr"]):
            return "features"
        
        # Building elements
        elif any(term in question_lower for term in ["sala", "room", "space", "ambiente"]):
            return "spaces"
        elif any(term in question_lower for term in ["parede", "wall"]):
            return "walls"
        elif any(term in question_lower for term in ["andar", "floor", "nivel"]):
            return "floors"
        elif any(term in question_lower for term in ["escada", "stair"]):
            return "stairs"
            
        else:
            return "elements"
    
    def _generate_project_info_queries(self) -> List[Dict[str, str]]:
        """Generate queries to find project information."""
        
        return [
            {
                "description": "Nome do projeto e informações do Building",
                "cypher": "MATCH (b:Building) RETURN b.name AS project_name, b.uid, b.type"
            },
            {
                "description": "Códigos de projeto identificados no desenho",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE a.text =~ '.*[A-Z]{2,}\\d+-[A-Z]{2,}-[A-Z]{2,}.*' 
                   OR a.text =~ '.*ECB\\d+.*'
                   OR a.text =~ '.*[A-Z]{3,}\\d+.*'
                RETURN DISTINCT a.text AS project_codes, a.insert_x, a.insert_y
                ORDER BY size(a.text) DESC
                LIMIT 15
                """
            },
            {
                "description": "Informações do projeto em anotações",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE (size(a.text) > 15 
                  AND (toLower(a.text) CONTAINS 'projeto' 
                       OR toLower(a.text) CONTAINS 'torre'
                       OR toLower(a.text) CONTAINS 'edificio'
                       OR toLower(a.text) CONTAINS 'empreendimento'
                       OR toLower(a.text) CONTAINS 'corporativo'
                       OR toLower(a.text) CONTAINS 'residencial'))
                   OR (toLower(a.text) CONTAINS 'aeroporto'
                       OR toLower(a.text) CONTAINS 'airport')
                RETURN a.text AS project_info, a.insert_x, a.insert_y
                ORDER BY size(a.text) DESC
                LIMIT 10
                """
            }
        ]
    
    def _generate_scale_queries(self) -> List[Dict[str, str]]:
        """Generate queries to find scale information with improved patterns."""
        
        return [
            {
                "description": "Escalas definidas no projeto (qualquer formato)",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE toLower(a.text) CONTAINS 'escala' 
                   OR toLower(a.text) CONTAINS 'scale'
                   OR a.text =~ '.*1:\\d+.*'
                   OR a.text =~ '.*H\\s*1:\\d+.*'
                   OR a.text =~ '.*V\\s*1:\\d+.*'
                   OR a.text =~ '.*ESC.*1:\\d+.*'
                   OR a.text =~ '.*ESCALA.*1:\\d+.*'
                RETURN DISTINCT a.text AS scale_info, 
                       a.insert_x, a.insert_y, a.layer,
                       CASE 
                         WHEN a.text =~ '.*H\\s*1:(\\d+).*' THEN 'Escala horizontal: 1:' + 
                              toString(toInteger(substring(a.text, indexof(a.text, 'H 1:') + 4, 10)))
                         WHEN a.text =~ '.*V\\s*1:(\\d+).*' THEN 'Escala vertical: 1:' + 
                              toString(toInteger(substring(a.text, indexof(a.text, 'V 1:') + 4, 10)))
                         WHEN a.text =~ '.*1:(\\d+).*' THEN 'Escala: 1:' + 
                              toString(toInteger(substring(a.text, indexof(a.text, '1:') + 2, 10)))
                         ELSE 'Informação de escala encontrada'
                       END AS interpretation
                ORDER BY size(a.text) DESC
                """
            },
            {
                "description": "Dados de escala no cabeçalho/header do desenho",
                "cypher": """
                MATCH (m:Metadata) 
                WHERE any(prop in keys(m) WHERE 
                    toLower(toString(m[prop])) CONTAINS 'scale' OR 
                    toLower(toString(m[prop])) CONTAINS 'escala')
                RETURN m AS metadata_scales
                """
            },
            {
                "description": "Anotações próximas à palavra ESCALA (contexto)",
                "cypher": """
                MATCH (label:Annotation), (value:Annotation)
                WHERE toLower(label.text) = 'escala' 
                  AND abs(label.insert_x - value.insert_x) < 100
                  AND abs(label.insert_y - value.insert_y) < 50
                  AND label.uid <> value.uid
                RETURN label.text AS label_text, 
                       value.text AS scale_value,
                       value.insert_x, value.insert_y,
                       'Valor próximo ao rótulo ESCALA' AS context
                ORDER BY abs(label.insert_x - value.insert_x) + abs(label.insert_y - value.insert_y)
                """
            },
            {
                "description": "Busca inteligente por padrões numéricos de escala",
                "cypher": """
                MATCH (a:Annotation)
                WHERE a.text =~ '.*1:\\d+.*'
                   OR a.text =~ '.*\\d+:\\d+.*'
                   OR a.text IN ['1:50', '1:100', '1:200', '1:500', '1:750', '1:1000', '1:1500', '1:2000', '1:5000']
                RETURN a.text AS exact_scale_notation,
                       a.insert_x, a.insert_y, a.layer,
                       CASE 
                         WHEN a.text CONTAINS '1:50' THEN 'Escala grande (detalhes) - 1cm = 50cm'
                         WHEN a.text CONTAINS '1:100' THEN 'Escala comum (plantas) - 1cm = 1m'
                         WHEN a.text CONTAINS '1:500' THEN 'Escala média (implantação) - 1cm = 5m'
                         WHEN a.text CONTAINS '1:1000' THEN 'Escala pequena (situação) - 1cm = 10m'
                         WHEN a.text CONTAINS '1:1500' THEN 'Escala pequena (situação) - 1cm = 15m'
                         WHEN a.text CONTAINS '1:2000' THEN 'Escala pequena (urbana) - 1cm = 20m'
                         ELSE 'Escala identificada: ' + a.text
                       END AS scale_meaning
                ORDER BY 
                  CASE 
                    WHEN a.text CONTAINS 'ESCALA' THEN 1
                    WHEN a.text CONTAINS 'ESC' THEN 2
                    ELSE 3
                  END,
                  size(a.text) DESC
                """
            }
        ]
    
    def _generate_annotation_queries(self) -> List[Dict[str, str]]:
        """Generate queries to find all annotations in the drawing."""
        
        return [
            {
                "description": "Todas as anotações do desenho",
                "cypher": """
                MATCH (a:Annotation) 
                RETURN a.text AS annotation_text, 
                       a.insert_x, a.insert_y, a.layer,
                       size(a.text) AS text_length
                ORDER BY size(a.text) DESC
                LIMIT 50
                """
            },
            {
                "description": "Anotações por layers principais",
                "cypher": """
                MATCH (a:Annotation) 
                RETURN a.layer AS layer, 
                       count(a) AS annotation_count,
                       collect(DISTINCT substring(a.text, 0, 50)) AS sample_texts
                ORDER BY annotation_count DESC
                LIMIT 10
                """
            },
            {
                "description": "Anotações mais importantes (textos maiores)",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE size(a.text) > 5
                RETURN a.text AS important_text, 
                       a.insert_x, a.insert_y, a.layer,
                       size(a.text) AS text_length
                ORDER BY size(a.text) DESC
                LIMIT 20
                """
            },
            {
                "description": "Estatísticas gerais de anotações",
                "cypher": """
                MATCH (a:Annotation) 
                RETURN count(a) AS total_annotations,
                       avg(size(a.text)) AS avg_text_length,
                       size(collect(DISTINCT a.layer)) AS unique_layers,
                       min(size(a.text)) AS min_text_length,
                       max(size(a.text)) AS max_text_length
                """
            }
        ]
    
    def _generate_element_queries(self, element_type: str) -> List[Dict[str, str]]:
        """Generate queries for specific element types based on actual data structure."""
        
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
            # Realistic approach: spaces are inferred from annotations, not actual Space nodes
            return [
                {
                    "description": "Espaços identificados em anotações",
                    "cypher": """MATCH (a:Annotation) 
                    WHERE toLower(a.text) CONTAINS 'sala' 
                       OR toLower(a.text) CONTAINS 'room'
                       OR toLower(a.text) CONTAINS 'ambiente'
                       OR toLower(a.text) CONTAINS 'escritorio'
                       OR toLower(a.text) CONTAINS 'office'
                    RETURN count(a) AS space_references, collect(DISTINCT a.text) AS space_types"""
                },
                {
                    "description": "Análise de configuração espacial através de paredes",
                    "cypher": """MATCH (:Floor)-[:HAS_WALL]->(w:WallSegment) 
                    RETURN count(w) AS wall_segments, 
                           count(DISTINCT w.layer) AS wall_layers,
                           'Espaços podem ser inferidos através da configuração das paredes' AS analysis_note"""
                }
            ]
        elif element_type == "circles":
            return [
                {
                    "description": "Features circulares no desenho",
                    "cypher": """MATCH (f:Feature) WHERE f.type = 'CIRCLE' 
                    RETURN count(f) AS circle_count, 
                           collect(DISTINCT f.layer) AS circle_layers,
                           avg(f.radius) AS average_radius"""
                },
                {
                    "description": "Detalhes dos círculos encontrados",
                    "cypher": """MATCH (f:Feature) WHERE f.type = 'CIRCLE' 
                    RETURN f.center_x, f.center_y, f.radius, f.layer 
                    ORDER BY f.radius DESC LIMIT 10"""
                }
            ]
        elif element_type == "stairs":
            return [
                {
                    "description": "Escadas identificadas em anotações",
                    "cypher": """
                    MATCH (a:Annotation) 
                    WHERE toLower(a.text) CONTAINS 'escada' 
                       OR toLower(a.text) CONTAINS 'stair'
                       OR toLower(a.text) CONTAINS 'degrau'
                    RETURN a.text AS stair_annotation, a.insert_x, a.insert_y, a.layer
                    ORDER BY a.text
                    """
                }
            ]
        elif element_type == "features":
            return [
                {
                    "description": "Todas as features geométricas",
                    "cypher": """MATCH (f:Feature) 
                    RETURN f.type AS feature_type, count(f) AS count, collect(DISTINCT f.layer) AS layers
                    ORDER BY count DESC"""
                },
                {
                    "description": "Detalhamento das features por tipo",
                    "cypher": """MATCH (f:Feature) 
                    RETURN f.type, f.layer, count(f) AS count_per_layer
                    ORDER BY f.type, count_per_layer DESC"""
                }
            ]
        else:
            # Smart fallback that checks multiple node types
            return [
                {
                    "description": f"Busca inteligente por '{element_type}' em anotações",
                    "cypher": f"""
                    MATCH (a:Annotation) 
                    WHERE toLower(a.text) CONTAINS '{element_type.lower()}' 
                    RETURN a.text AS found_text, a.insert_x, a.insert_y, a.layer
                    ORDER BY size(a.text) DESC
                    LIMIT 15
                    """
                },
                {
                    "description": f"Verificar se '{element_type}' existe como tipo de feature",
                    "cypher": f"""
                    MATCH (f:Feature) 
                    WHERE toLower(f.type) CONTAINS '{element_type.lower()}'
                    RETURN f.type AS feature_type, count(f) AS count
                    ORDER BY count DESC
                    """
                }
            ]
    
    def _generate_count_queries(self, count_type: str) -> List[Dict[str, str]]:
        """Generate counting queries based on actual data structure."""
        
        if count_type == "spaces":
            return [
                {
                    "description": "Referências a espaços em anotações (não há nós Space diretos)",
                    "cypher": """MATCH (a:Annotation) 
                    WHERE toLower(a.text) CONTAINS 'sala' 
                       OR toLower(a.text) CONTAINS 'room'
                       OR toLower(a.text) CONTAINS 'ambiente'
                       OR toLower(a.text) CONTAINS 'escritorio'
                       OR toLower(a.text) CONTAINS 'office'
                       OR toLower(a.text) CONTAINS 'banheiro'
                       OR toLower(a.text) CONTAINS 'cozinha'
                    RETURN count(a) AS space_references,
                           'Nota: Espaços identificados através de anotações, não geometria' AS note"""
                },
                {
                    "description": "Análise estrutural para inferir espaços",
                    "cypher": """MATCH (:Floor)-[:HAS_WALL]->(w:WallSegment) 
                    RETURN count(w) AS wall_segments,
                           count(DISTINCT w.layer) AS wall_layers,
                           'Configuração de paredes sugere presença de espaços fechados' AS structural_analysis"""
                }
            ]
        elif count_type == "walls":
            return [
                {
                    "description": "Total de segmentos de parede", 
                    "cypher": "MATCH (:Floor)-[:HAS_WALL]->(w:WallSegment) RETURN count(w) AS total_walls"
                }
            ]
        elif count_type == "circles":
            return [
                {
                    "description": "Total de elementos circulares",
                    "cypher": "MATCH (f:Feature) WHERE f.type = 'CIRCLE' RETURN count(f) AS total_circles"
                }
            ]
        elif count_type == "features":
            return [
                {
                    "description": "Contagem de features por tipo",
                    "cypher": "MATCH (f:Feature) RETURN f.type AS feature_type, count(f) AS count ORDER BY count DESC"
                }
            ]
        else:
            return [
                {
                    "description": "Contagem geral de elementos no desenho",
                    "cypher": "MATCH (n) RETURN labels(n) AS element_type, count(n) AS count ORDER BY count DESC"
                }
            ]
    
    def _identify_ocr_query_type(self, question_lower: str) -> str:
        """Identify what type of OCR query the user is asking about."""
        
        if any(term in question_lower for term in ["descoberto", "discovered", "novo", "new"]):
            return "discoveries"
        elif any(term in question_lower for term in ["validado", "validated", "confirmado", "confirmed"]):
            return "validations"
        elif any(term in question_lower for term in ["confiança", "confidence", "qualidade", "quality"]):
            return "quality"
        elif any(term in question_lower for term in ["região", "region", "area"]):
            return "regions"
        else:
            return "general_ocr"
    
    def _generate_ocr_queries(self, ocr_type: str) -> List[Dict[str, str]]:
        """Generate OCR-specific queries."""
        
        if ocr_type == "discoveries":
            return [
                {
                    "description": "Textos descobertos pelo OCR",
                    "cypher": """
                    MATCH (ocr:OCRText)-[:DISCOVERS]->(floor:Floor)
                    RETURN ocr.text AS discovered_text, ocr.confidence, ocr.region_type
                    ORDER BY ocr.confidence DESC
                    """
                },
                {
                    "description": "Contagem de descobertas por tipo",
                    "cypher": """
                    MATCH (ocr:OCRText)-[:DISCOVERS]->(floor:Floor)
                    RETURN ocr.region_type, count(ocr) AS discovery_count
                    ORDER BY discovery_count DESC
                    """
                }
            ]
        elif ocr_type == "validations":
            return [
                {
                    "description": "Textos validados pelo OCR",
                    "cypher": """
                    MATCH (ocr:OCRText)-[r:VALIDATES]->(floor:Floor)
                    RETURN ocr.text AS ocr_text, r.cad_text AS original_text, r.confidence
                    ORDER BY r.confidence DESC
                    """
                },
                {
                    "description": "Taxa de validação por região",
                    "cypher": """
                    MATCH (region:OCRRegion)-[:CONTAINS_TEXT]->(ocr:OCRText)
                    OPTIONAL MATCH (ocr)-[:VALIDATES]->()
                    RETURN region.region_type, 
                           count(ocr) AS total_texts,
                           count(CASE WHEN exists((ocr)-[:VALIDATES]->()) THEN 1 END) AS validated_texts
                    ORDER BY region.region_type
                    """
                }
            ]
        elif ocr_type == "quality":
            return [
                {
                    "description": "Qualidade do OCR por região",
                    "cypher": """
                    MATCH (region:OCRRegion)
                    RETURN region.region_type, region.average_confidence, region.text_count
                    ORDER BY region.average_confidence DESC
                    """
                },
                {
                    "description": "Textos com alta confiança",
                    "cypher": """
                    MATCH (ocr:OCRText)
                    WHERE ocr.confidence > 0.8
                    RETURN ocr.text, ocr.confidence, ocr.region_type
                    ORDER BY ocr.confidence DESC
                    LIMIT 20
                    """
                }
            ]
        elif ocr_type == "regions":
            return [
                {
                    "description": "Regiões OCR disponíveis",
                    "cypher": """
                    MATCH (region:OCRRegion)
                    RETURN region.region_type, region.text_count, region.average_confidence
                    ORDER BY region.text_count DESC
                    """
                },
                {
                    "description": "Textos por região",
                    "cypher": """
                    MATCH (region:OCRRegion)-[:CONTAINS_TEXT]->(ocr:OCRText)
                    RETURN region.region_type, collect(ocr.text) AS texts
                    ORDER BY region.region_type
                    """
                }
            ]
        else:
            return [
                {
                    "description": "Visão geral dos dados OCR",
                    "cypher": """
                    MATCH (ocr:OCRText)
                    RETURN count(ocr) AS total_ocr_texts,
                           avg(ocr.confidence) AS average_confidence,
                           collect(DISTINCT ocr.region_type) AS region_types
                    """
                }
            ]
    
    def _generate_exploration_queries(self) -> List[Dict[str, str]]:
        """Generate exploratory queries for general questions (now includes OCR)."""
        
        return [
            {
                "description": "Visão geral dos dados",
                "cypher": "MATCH (n) RETURN labels(n) AS types, count(n) AS count ORDER BY count DESC"
            },
            {
                "description": "Anotações mais relevantes",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE size(a.text) > 5 AND size(a.text) < 100
                RETURN a.text 
                ORDER BY size(a.text) DESC 
                LIMIT 15
                """
            },
            {
                "description": "Dados OCR disponíveis",
                "cypher": """
                MATCH (ocr:OCRText)
                RETURN count(ocr) AS total_ocr_texts,
                       avg(ocr.confidence) AS avg_confidence,
                       collect(DISTINCT ocr.region_type) AS region_types
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
    
    def _generate_technical_standards_queries(self) -> List[Dict[str, str]]:
        """Generate queries to find technical standards and norms."""
        
        return [
            {
                "description": "Padrões técnicos (fck, MPa, códigos)",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE a.text =~ '.*fck\\s*\\d+\\s*MPa.*'
                   OR a.text =~ '.*\\d+\\s*MPa.*'
                   OR a.text =~ '.*NBR\\s*\\d+.*'
                   OR a.text =~ '.*ABNT.*'
                RETURN DISTINCT a.text AS technical_standards
                ORDER BY a.text
                """
            },
            {
                "description": "Códigos e normas em formato padrão",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE a.text =~ '.*[A-Z]{2,}\\d+.*'
                   OR a.text =~ '.*\\d+/\\d+.*'
                   OR toLower(a.text) CONTAINS 'norma'
                   OR toLower(a.text) CONTAINS 'codigo'
                RETURN DISTINCT a.text AS standards_codes
                ORDER BY size(a.text) DESC
                LIMIT 20
                """
            },
            {
                "description": "Especificações técnicas estruturais",
                "cypher": """
                MATCH (a:Annotation) 
                WHERE a.text =~ '.*\\d+x\\d+.*'
                   OR a.text =~ '.*h=\\d+.*'
                   OR toLower(a.text) CONTAINS 'estrutural'
                   OR toLower(a.text) CONTAINS 'laje'
                   OR toLower(a.text) CONTAINS 'viga'
                RETURN DISTINCT a.text AS structural_specs
                ORDER BY a.text
                """
            }
        ]
    
    def execute_smart_search(self, user_question: str) -> Dict[str, Any]:
        """Execute a smart search that tries multiple approaches."""
        
        # 🧠 PRIMEIRO: Check for intelligent analysis triggers
        question_lower = user_question.lower()
        intelligent_triggers = ["do que se trata", "sobre o que", "what is this project", "project about", 
                              "análise completa", "análise do projeto", "resumo do projeto", "entenda o projeto"]
        
        if any(term in question_lower for term in intelligent_triggers):
            print("🧠 [SMART] Detected intelligent analysis trigger")
            try:
                from intelligent_project_analyzer import analyze_project_intelligently
                analysis_result = analyze_project_intelligently()
                
                # Return in SmartQueryResponse format
                return {
                    "interpretation": {
                        "intent": "intelligent_project_analysis",
                        "confidence": 0.95,
                        "suggested_queries": [{"description": "Análise Inteligente Completa", "confidence": 0.95}]
                    },
                    "query_results": [{"analysis": analysis_result, "description": "Análise Inteligente Completa", "results": [{"content": analysis_result}]}],
                    "best_match": {"analysis": analysis_result, "description": "Análise Inteligente Completa", "results": [{"content": analysis_result}]}
                }
            except Exception as e:
                print(f"❌ [SMART] Intelligent analysis failed: {e}")
                # Fall through to regular processing
        
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
    
    def _generate_legend_queries(self) -> List[Dict[str, str]]:
        """Generate queries for finding legends, colors, and indications."""
        return [
            {
                "description": "Legendas com análise visual completa",
                "cypher": """
                MATCH (item:LegendItem)
                OPTIONAL MATCH (item)-[:HAS_COLOR]->(color:ColorScheme)
                OPTIONAL MATCH (item)-[:HAS_PATTERN]->(pattern:VisualPattern)
                RETURN item.text AS legend_text,
                       color.color_name AS color,
                       color.hex_code AS hex_code,
                       pattern.pattern_type AS pattern,
                       CASE 
                         WHEN color.color_name IS NOT NULL AND pattern.pattern_type IS NOT NULL 
                         THEN color.color_name + ' + ' + pattern.pattern_type
                         WHEN color.color_name IS NOT NULL 
                         THEN color.color_name
                         WHEN pattern.pattern_type IS NOT NULL 
                         THEN pattern.pattern_type
                         ELSE 'sem cor/padrão identificado'
                       END AS visual_signature
                ORDER BY item.text
                """
            },
            {
                "description": "Legendas e indicações principais (texto)",
                "cypher": """
                MATCH (a:Annotation)
                WHERE toLower(a.text) CONTAINS 'legenda' OR 
                      toLower(a.text) CONTAINS 'indicaç' OR
                      toLower(a.text) CONTAINS 'faixa' OR
                      toLower(a.text) CONTAINS 'pavimento' OR
                      toLower(a.text) CONTAINS 'cor' OR
                      toLower(a.text) CONTAINS 'resa' OR
                      toLower(a.text) CONTAINS 'pista' OR
                      toLower(a.text) CONTAINS 'equipamento' OR
                      toLower(a.text) CONTAINS 'vegetação' OR
                      toLower(a.text) CONTAINS 'drenagem' OR
                      toLower(a.text) CONTAINS 'existente' OR
                      toLower(a.text) CONTAINS 'implantar' OR
                      toLower(a.text) CONTAINS 'demolir'
                RETURN DISTINCT a.text AS legenda
                ORDER BY a.text
                LIMIT 50
                """
            },
            {
                "description": "Textos de atributos de blocos (legendas em blocos)",
                "cypher": """
                MATCH (a:Annotation)
                WHERE labels(a) = ['Annotation'] AND a.type = 'ATTRIB'
                RETURN DISTINCT a.text AS legenda, a.tag AS tag, a.parent_block AS bloco
                ORDER BY a.text
                LIMIT 50
                """
            },
            {
                "description": "Textos extraídos de blocos INSERT",
                "cypher": """
                MATCH (a:Annotation)
                WHERE a.parent_block IS NOT NULL
                RETURN DISTINCT a.text AS texto_bloco, a.parent_block AS nome_bloco
                ORDER BY a.parent_block, a.text
                LIMIT 50
                """
            },
            {
                "description": "Legendas detectadas por OCR",
                "cypher": """
                MATCH (ocr:OCRText)
                WHERE toLower(ocr.text) CONTAINS 'legenda' OR
                      toLower(ocr.text) CONTAINS 'indicaç' OR
                      toLower(ocr.text) CONTAINS 'faixa' OR
                      toLower(ocr.text) CONTAINS 'pavimento' OR
                      toLower(ocr.text) CONTAINS 'cor'
                RETURN DISTINCT ocr.text AS legenda_ocr, ocr.confidence AS confianca
                ORDER BY ocr.confidence DESC
                LIMIT 30
                """
            },
            {
                "description": "Todas as anotações longas (possíveis legendas)",
                "cypher": """
                MATCH (a:Annotation)
                WHERE size(a.text) > 20 AND size(a.text) < 200
                RETURN DISTINCT a.text AS texto
                ORDER BY size(a.text) DESC
                LIMIT 30
                """
            },
            {
                "description": "Agrupamento de legendas por cor",
                "cypher": """
                MATCH (item:LegendItem)-[:HAS_COLOR]->(color:ColorScheme)
                WITH color.color_name AS color_name, color.hex_code AS hex_code, 
                     collect(item.text) AS elements
                RETURN color_name, hex_code, elements, size(elements) AS element_count
                ORDER BY element_count DESC
                """
            }
        ]
    
    def _generate_color_search_queries(self, color_term: str = None) -> List[Dict[str, str]]:
        """Generate queries for searching by colors in visual legends."""
        return [
            {
                "description": "Busca por cores em legendas visuais",
                "cypher": f"""
                MATCH (item:LegendItem)-[:HAS_COLOR]->(color:ColorScheme)
                {"WHERE toLower(color.color_name) CONTAINS toLower('" + color_term + "')" if color_term else ""}
                RETURN item.text AS legend_text, 
                       color.color_name AS color_name,
                       color.hex_code AS hex_code,
                       color.rgb_values AS rgb_values
                ORDER BY item.text
                """
            },
            {
                "description": "Esquema de cores do projeto",
                "cypher": """
                MATCH (color:ColorScheme)
                WITH color.color_name AS color_name, count(*) AS usage_count
                RETURN color_name, usage_count
                ORDER BY usage_count DESC
                """
            },
            {
                "description": "Cores relacionadas a elementos específicos",
                "cypher": """
                MATCH (item:LegendItem)-[:HAS_COLOR]->(color:ColorScheme)
                WHERE toLower(item.text) CONTAINS 'vegetação' OR
                      toLower(item.text) CONTAINS 'pavimento' OR
                      toLower(item.text) CONTAINS 'agua' OR
                      toLower(item.text) CONTAINS 'equipamento'
                RETURN item.text AS element_type, 
                       color.color_name AS associated_color,
                       color.hex_code AS hex_code
                ORDER BY element_type
                """
            }
        ]
    
    def _generate_pattern_search_queries(self, pattern_term: str = None) -> List[Dict[str, str]]:
        """Generate queries for searching by visual patterns."""
        return [
            {
                "description": "Busca por padrões visuais",
                "cypher": f"""
                MATCH (item:LegendItem)-[:HAS_PATTERN]->(pattern:VisualPattern)
                {"WHERE toLower(pattern.pattern_type) CONTAINS toLower('" + pattern_term + "')" if pattern_term else ""}
                RETURN item.text AS legend_text,
                       pattern.pattern_type AS pattern_type,
                       pattern.pattern_direction AS direction
                ORDER BY pattern.pattern_type, item.text
                """
            },
            {
                "description": "Padrões por tipo",
                "cypher": """
                MATCH (pattern:VisualPattern)
                RETURN pattern.pattern_type, 
                       count(*) AS usage_count,
                       collect(DISTINCT pattern.pattern_direction) AS directions
                ORDER BY usage_count DESC
                """
            },
            {
                "description": "Elementos com padrões específicos",
                "cypher": """
                MATCH (item:LegendItem)-[:HAS_PATTERN]->(pattern:VisualPattern)
                WHERE pattern.pattern_type IN ['dotted', 'dashed', 'striped', 'hatched']
                RETURN pattern.pattern_type AS pattern_type,
                       collect(item.text) AS elements_with_pattern
                ORDER BY pattern.pattern_type
                """
            }
        ]
    
    def _generate_visual_legend_search_queries(self) -> List[Dict[str, str]]:
        """Generate comprehensive visual legend search queries."""
        return [
            {
                "description": "Análise completa de legendas visuais",
                "cypher": """
                MATCH (group:LegendGroup)-[:CONTAINS_LEGEND_ITEM]->(item:LegendItem)
                OPTIONAL MATCH (item)-[:HAS_COLOR]->(color:ColorScheme)
                OPTIONAL MATCH (item)-[:HAS_PATTERN]->(pattern:VisualPattern)
                RETURN item.text AS legend_text,
                       color.color_name AS color,
                       color.hex_code AS hex_code,
                       pattern.pattern_type AS pattern,
                       pattern.pattern_direction AS pattern_direction
                ORDER BY item.text
                """
            },
            {
                "description": "Grupos de legendas por cores",
                "cypher": """
                MATCH (item:LegendItem)-[:HAS_COLOR]->(color:ColorScheme)
                WITH color.color_name AS color_name, collect(item.text) AS elements
                RETURN color_name, elements, size(elements) AS element_count
                ORDER BY element_count DESC
                """
            },
            {
                "description": "Mapeamento cor-padrão-elemento",
                "cypher": """
                MATCH (item:LegendItem)
                OPTIONAL MATCH (item)-[:HAS_COLOR]->(color:ColorScheme)
                OPTIONAL MATCH (item)-[:HAS_PATTERN]->(pattern:VisualPattern)
                RETURN item.text AS element,
                       color.color_name AS color,
                       pattern.pattern_type AS pattern,
                       CASE 
                         WHEN color.color_name IS NOT NULL AND pattern.pattern_type IS NOT NULL 
                         THEN color.color_name + ' + ' + pattern.pattern_type
                         WHEN color.color_name IS NOT NULL 
                         THEN color.color_name
                         WHEN pattern.pattern_type IS NOT NULL 
                         THEN pattern.pattern_type
                         ELSE 'sem definição visual'
                       END AS visual_signature
                ORDER BY element
                """
            },
            {
                "description": "Estatísticas de legendas visuais",
                "cypher": """
                MATCH (group:LegendGroup)
                OPTIONAL MATCH (group)-[:CONTAINS_LEGEND_ITEM]->(item:LegendItem)
                OPTIONAL MATCH (item)-[:HAS_COLOR]->(color:ColorScheme)
                OPTIONAL MATCH (item)-[:HAS_PATTERN]->(pattern:VisualPattern)
                RETURN group.total_elements AS total_elements,
                       group.analysis_confidence AS confidence,
                       count(DISTINCT color) AS unique_colors,
                       count(DISTINCT pattern) AS unique_patterns,
                       count(item) AS processed_items
                """
            }
        ]
    
    def _extract_color_term(self, question_lower: str) -> Optional[str]:
        """Extract specific color term from the question."""
        color_terms = ["verde", "azul", "amarelo", "vermelho", "cinza", "branco", 
                      "green", "blue", "yellow", "red", "gray", "grey", "white"]
        
        for term in color_terms:
            if term in question_lower:
                return term
        return None
    
    def _extract_pattern_term(self, question_lower: str) -> Optional[str]:
        """Extract specific pattern term from the question."""
        pattern_terms = ["pontilhado", "tracejado", "sólido", "listrado", "hachurado",
                        "dotted", "dashed", "solid", "striped", "hatched"]
        
        for term in pattern_terms:
            if term in question_lower:
                return term
        return None

# Global instance
semantic_enhancer = SemanticQueryEnhancer()