from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from typing import Any, Dict, Optional, List
import json
from pathlib import Path
import tempfile

from pydantic import BaseModel

from query_interface import text_to_cypher, text_to_cypher_async, execute_cypher_query, build_prompt  # noqa: F401
from data_extraction import extract_cad_data
from graph_loader import transform_to_graph, load_to_neo4j


app = FastAPI(title="CAD Graph Platform")

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UploadResponse(BaseModel):
    message: str
    file_path: str
    entities_extracted: int
    nodes_created: int
    relationships_created: int


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload and process a CAD file (DWG/DXF)."""
    
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.dwg', '.dxf']:
        raise HTTPException(status_code=400, detail="Only DWG and DXF files are supported")
    
    # Validate file size (50MB limit)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB in bytes
        raise HTTPException(status_code=413, detail="File size must be less than 50MB")
    
    # Reset file pointer for subsequent operations
    await file.seek(0)
    
    # Create uploads directory if it doesn't exist
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    # Save uploaded file
    file_path = uploads_dir / file.filename
    try:
        # Use the content we already read for validation
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    try:
        # Extract CAD data to JSON
        print(f"Extracting CAD data from: {file_path}")
        json_path = extract_cad_data(file_path)
        print(f"JSON extracted to: {json_path}")
        
        # Check if entities file exists (preferred format)
        entities_path = json_path.parent / f"{json_path.stem}-entities.json"
        if entities_path.exists():
            print(f"Found entities file: {entities_path}")
            json_path = entities_path
        
        # Check if JSON file exists and is readable
        if not json_path.exists():
            raise Exception(f"JSON extraction failed - output file not found: {json_path}")
        
        # Try to read the JSON file with multiple encodings
        test_data = None
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(json_path, 'r', encoding=encoding) as f:
                    test_data = json.load(f)
                print(f"JSON file successfully parsed with {encoding} encoding, contains {len(test_data) if isinstance(test_data, list) else 'object'}")
                break
            except UnicodeDecodeError:
                continue
            except json.JSONDecodeError as je:
                raise Exception(f"JSON file format error: {je}")
        
        if test_data is None:
            raise Exception("Could not read JSON file with any supported encoding")
        
        # Transform to graph format
        print("Transforming to graph format...")
        graph_payload = transform_to_graph(json_path)
        print(f"Graph payload created with {len(graph_payload.get('nodes', []))} nodes")
        
        # Load into Neo4j
        print("Loading to Neo4j...")
        load_to_neo4j(graph_payload)
        print("Successfully loaded to Neo4j")
        
        # Count entities and graph elements
        entities_count = len(test_data) if isinstance(test_data, list) else len(test_data.get('entities', []))
        nodes_count = len(graph_payload.get('nodes', []))
        relationships_count = len(graph_payload.get('relationships', []))
        
        return UploadResponse(
            message="File processed successfully",
            file_path=str(file_path),
            entities_extracted=entities_count,
            nodes_created=nodes_count,
            relationships_created=relationships_count
        )
        
    except Exception as e:
        import traceback
        print(f"Upload processing error: {str(e)}")
        print(f"Full traceback: {traceback.format_exc()}")
        # Clean up file on error
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    cypher: str
    results: Any
    summary: Optional[str] = None

class SmartQueryResponse(BaseModel):
    interpretation: Dict[str, Any]
    primary_result: Dict[str, Any]
    alternative_results: List[Dict[str, Any]]
    explanation: str


OPENAI_SUMMARY_MODEL = "gpt-4o"


@app.post("/api/query", response_model=QueryResponse)
async def run_query(req: QueryRequest):
    """Endpoint that converts NL question to Cypher, executes, returns results."""

    try:
        cypher = await text_to_cypher_async(req.question)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        results = execute_cypher_query(cypher)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Cypher execution failed: {exc}") from exc

    # Optional summary step
    summary: Optional[str] = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI  # local import to avoid mandatory dependency at runtime

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            messages = [
                {
                    "role": "system",
                    "content": "You are an assistant that summarises query results for end users.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {req.question}\nCypher: {cypher}\nResults: {json.dumps(results, indent=2)}\n"
                        "Provide a concise, human-readable answer."
                    ),
                },
            ]
            response = client.chat.completions.create(model=OPENAI_SUMMARY_MODEL, messages=messages, temperature=0.2)
            summary = response.choices[0].message.content.strip()
        except Exception:  # noqa: BLE001
            summary = None

    return QueryResponse(cypher=cypher, results=results, summary=summary)


@app.post("/api/smart-query", response_model=SmartQueryResponse)
async def smart_query(req: QueryRequest):
    """Advanced query endpoint with semantic understanding and multiple approaches."""
    
    try:
        from semantic_query_enhancer import semantic_enhancer
        
        # Execute smart search
        smart_results = semantic_enhancer.execute_smart_search(req.question)
        
        if not smart_results["query_results"]:
            raise HTTPException(status_code=400, detail="No relevant data found for your question")
        
        # Find best result
        primary_result = smart_results["best_match"] or smart_results["query_results"][0]
        alternative_results = [r for r in smart_results["query_results"] if r != primary_result]
        
        # Generate explanation
        intent = smart_results["interpretation"]["detected_intent"]
        explanation = f"Interpretei sua pergunta como: {intent}. "
        
        if primary_result.get("results"):
            result_count = len(primary_result["results"])
            explanation += f"Encontrei {result_count} resultado(s) relevante(s). "
        
        if alternative_results:
            explanation += f"Também verifiquei {len(alternative_results)} abordagem(s) alternativa(s)."
        
        return SmartQueryResponse(
            interpretation=smart_results["interpretation"],
            primary_result=primary_result,
            alternative_results=alternative_results[:3],  # Limit alternatives
            explanation=explanation
        )
        
    except ImportError:
        raise HTTPException(status_code=500, detail="Semantic enhancer not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Smart query failed: {str(e)}")


@app.get("/api/suggest-questions")
async def suggest_questions():
    """Suggest example questions based on available data."""
    
    try:
        from semantic_query_enhancer import semantic_enhancer
        
        with semantic_enhancer.driver.session() as session:
            # Check what data is available
            stats = session.run("MATCH (n) RETURN labels(n) AS types, count(n) AS count").data()
            
            suggestions = {
                "data_summary": stats,
                "suggested_questions": [
                    {
                        "category": "Informações do Projeto",
                        "questions": [
                            "Qual o nome do projeto?",
                            "Qual é o código do projeto?",
                            "Que tipo de projeto é este?",
                            "Onde está localizado o projeto?"
                        ]
                    },
                    {
                        "category": "Escala e Medidas",
                        "questions": [
                            "Qual a escala do projeto?",
                            "Qual o tamanho do desenho?",
                            "Quais são as dimensões principais?",
                            "Em que unidade estão as medidas?"
                        ]
                    },
                    {
                        "category": "Elementos Arquitetônicos",
                        "questions": [
                            "Quantas salas tem o projeto?",
                            "Onde estão as paredes?",
                            "Tem escadas no projeto?",
                            "Quais são os espaços principais?"
                        ]
                    },
                    {
                        "category": "Análise de Dados",
                        "questions": [
                            "Que tipos de elementos tem no desenho?",
                            "Quais são as anotações principais?",
                            "Em quantos layers está organizado?",
                            "Que informações técnicas posso encontrar?"
                        ]
                    }
                ],
                "tips": [
                    "Você pode perguntar em português ou inglês",
                    "Não precisa usar termos técnicos - eu entendo linguagem natural",
                    "Posso buscar informações em diferentes locais (anotações, metadados, nomes)",
                    "Se não encontrar algo, tento abordagens alternativas"
                ]
            }
            
            return suggestions
            
    except Exception as e:
        return {
            "suggested_questions": [
                {
                    "category": "Básicas",
                    "questions": [
                        "What annotations are in the drawing?",
                        "Show me all wall segments",
                        "How many spaces are there?",
                        "What is the project scale?"
                    ]
                }
            ],
            "error": f"Could not generate advanced suggestions: {str(e)}"
        }

# Serve static files (frontend)
if os.path.exists("/app/static"):
    app.mount("/", StaticFiles(directory="/app/static", html=True), name="static") 