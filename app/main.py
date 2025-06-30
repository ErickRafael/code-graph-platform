from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import time
from typing import Any, Dict, Optional, List
import json
from pathlib import Path
import tempfile
from dotenv import load_dotenv

from pydantic import BaseModel

# Carregar variáveis de ambiente do diretório pai
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from query_interface import text_to_cypher, text_to_cypher_async, smart_query_router_async, execute_cypher_query, build_prompt  # noqa: F401
from data_extraction import extract_cad_data
from enhanced_data_extraction import enhanced_extract_cad_data, EnhancedCADExtractor
from graph_loader import transform_to_graph, transform_to_graph_streaming, transform_enhanced_to_graph, load_to_neo4j
# ✅ REATIVADO: Imports OCR para enriquecimento de grafos
from ocr_integration_endpoint import ocr_router
from async_ocr_processor import async_ocr_router, get_async_processor

# Formatting functions for different query types
def format_legend_response(primary_result, alternative_results):
    """Format response for legend queries with visual information when available."""
    legends = []
    legend_with_colors = []
    
    # First check if we have visual legend data
    has_visual_data = False
    if primary_result.get("results"):
        # Check if this is a visual legend query with color/pattern data
        first_result = primary_result["results"][0] if primary_result["results"] else {}
        if any(key in first_result for key in ['color', 'hex_code', 'pattern', 'visual_signature']):
            has_visual_data = True
            
    if has_visual_data:
        # Format visual legend results with colors and patterns
        for result in primary_result["results"]:
            legend_text = result.get('legend_text', result.get('element', ''))
            color = result.get('color', '')
            hex_code = result.get('hex_code', '')
            pattern = result.get('pattern', '')
            visual_signature = result.get('visual_signature', '')
            
            if legend_text:
                # Build comprehensive legend item with visual info
                legend_item = f"**{legend_text}**"
                visual_parts = []
                
                if color and color != 'None':
                    visual_parts.append(f"🎨 {color}")
                if hex_code and hex_code != 'None':
                    visual_parts.append(f"({hex_code})")
                if pattern and pattern != 'None':
                    visual_parts.append(f"📐 {pattern}")
                
                if visual_parts:
                    legend_item += f" → {' '.join(visual_parts)}"
                elif visual_signature and visual_signature != 'sem definição visual':
                    legend_item += f" → {visual_signature}"
                
                legend_with_colors.append(legend_item)
        
        # Also check alternative results for more visual data
        if alternative_results:
            for alt_result in alternative_results:
                if "cor" in alt_result.get("description", "").lower() and alt_result.get("results"):
                    # Process color grouping results
                    for result in alt_result["results"]:
                        color_name = result.get('color_name', '')
                        elements = result.get('elements', [])
                        if color_name and elements:
                            legend_with_colors.append(f"\n**Cor {color_name}:**")
                            for elem in elements:
                                legend_with_colors.append(f"  • {elem}")
        
        if legend_with_colors:
            return "📋 **Legendas com cores e padrões:**\n" + "\n".join(legend_with_colors)
    
    # Fallback to traditional text-only legend formatting
    # Check primary results
    if primary_result.get("results"):
        for result in primary_result["results"]:
            # Look for various legend-related fields
            for key, value in result.items():
                if value and isinstance(value, str) and len(value.strip()) > 2:
                    # Filter out obvious non-legend content
                    value_clean = value.strip()
                    if not any(skip in value_clean.lower() for skip in ['select', 'match', 'return', 'where', 'null']):
                        legends.append(value_clean)
    
    # Check alternative results for more legend content
    if alternative_results:
        for alt_result in alternative_results:
            if alt_result.get("results"):
                for result in alt_result["results"]:
                    # Look for text fields that might contain legends
                    text_fields = ['text', 'annotation_text', 'legend_text', 'description']
                    for field in text_fields:
                        if field in result and result[field]:
                            text = str(result[field]).strip()
                            # Filter legend-like content (avoid coordinate data, etc.)
                            if (len(text) > 2 and len(text) < 100 and 
                                not text.startswith('{\\C2;') and 
                                not text.startswith('N=') and
                                not text.startswith('\\A1;') and
                                'faixa' in text.lower() or 'área' in text.lower() or 'via' in text.lower() or 
                                'pista' in text.lower() or 'taxiway' in text.lower() or 'twy' in text.lower() or
                                'resa' in text.lower() or 'pavimento' in text.lower() or 'vegetação' in text.lower() or
                                'drenagem' in text.lower() or 'equipamento' in text.lower()):
                                legends.append(text)
    
    if not legends:
        return "🔍 **Nenhuma legenda encontrada no projeto.**"
    
    # Remove duplicates and sort
    unique_legends = sorted(list(set(legends)))
    
    # Filter out very short or technical entries
    filtered_legends = [leg for leg in unique_legends if len(leg) > 3 and not leg.isdigit()]
    
    if not filtered_legends:
        return "🔍 **Nenhuma legenda clara encontrada.**"
    
    if len(filtered_legends) == 1:
        return f"📋 **Legenda encontrada:**\n• {filtered_legends[0]}"
    
    response = f"📋 **{len(filtered_legends)} legendas encontradas:**\n"
    for legend in filtered_legends[:15]:  # Show max 15
        response += f"• {legend}\n"
    
    if len(filtered_legends) > 15:
        response += f"... e mais {len(filtered_legends) - 15} legendas (veja Query Details)"
    
    return response

def format_scale_response(primary_result, alternative_results=None):
    """Format response for scale queries."""
    import re
    
    # First check alternative results for exact scale notations
    if alternative_results:
        for alt_result in alternative_results:
            # Skip results with errors
            if alt_result.get("error"):
                continue
                
            # Check if there are results
            if alt_result.get("results"):
                for result in alt_result["results"]:
                    if "exact_scale_notation" in result and result["exact_scale_notation"]:
                        scale_text = result["exact_scale_notation"]
                        
                        # Extract the numeric ratio from the scale text  
                        scale_match = re.search(r'1:(\d+)', scale_text)
                        if scale_match:
                            ratio = int(scale_match.group(1))
                            
                            if ratio >= 1500:
                                scale_type = "situação/implantação"
                                real_scale = f"1cm = {ratio/100}m"
                            elif ratio >= 500:
                                scale_type = "planta geral"
                                real_scale = f"1cm = {ratio/100}m"
                            elif ratio >= 100:
                                scale_type = "planta baixa"
                                real_scale = f"1cm = {ratio/100}m"
                            else:
                                scale_type = "detalhe"
                                real_scale = f"1cm = {ratio}cm"
                            
                            return f"📏 **{scale_text.upper()}**\n• Tipo: {scale_type.title()}\n• Proporção: {real_scale}"
    
    # Check primary results for metadata scales
    if primary_result.get("results"):
        for result in primary_result["results"]:
            # Check for metadata scales
            if "metadata_scales" in result and result["metadata_scales"]:
                metadata = result["metadata_scales"]
                if isinstance(metadata, dict):
                    # Look for scale factors > 1 (meaningful scales)
                    scale_fields = ['cmlscale', 'dimscale', 'ltscale']
                    for field in scale_fields:
                        if field in metadata and metadata[field] and metadata[field] > 1:
                            ratio = int(metadata[field])
                            
                            if ratio >= 1500:
                                scale_type = "situação/implantação"
                                real_scale = f"1cm = {ratio/100}m"
                            elif ratio >= 500:
                                scale_type = "planta geral"
                                real_scale = f"1cm = {ratio/100}m"
                            elif ratio >= 100:
                                scale_type = "planta baixa"
                                real_scale = f"1cm = {ratio/100}m"
                            else:
                                scale_type = "detalhe"
                                real_scale = f"1cm = {ratio}cm"
                            
                            return f"📏 **ESCALA 1:{ratio}**\n• Tipo: {scale_type.title()}\n• Proporção: {real_scale}\n• Fonte: Metadados CAD ({field})"
            
            # Check for direct text patterns
            for key, value in result.items():
                if value and isinstance(value, str):
                    scale_match = re.search(r'(?:ESCALA\s+)?(?:H\s+)?1:(\d+)', str(value))
                    if scale_match:
                        ratio = int(scale_match.group(1))
                        
                        if ratio >= 1500:
                            scale_type = "situação/implantação"
                            real_scale = f"1cm = {ratio/100}m"
                        elif ratio >= 500:
                            scale_type = "planta geral"
                            real_scale = f"1cm = {ratio/100}m"
                        elif ratio >= 100:
                            scale_type = "planta baixa"
                            real_scale = f"1cm = {ratio/100}m"
                        else:
                            scale_type = "detalhe"
                            real_scale = f"1cm = {ratio}cm"
                        
                        return f"📏 **ESCALA 1:{ratio}**\n• Tipo: {scale_type.title()}\n• Proporção: {real_scale}"
    
    return "📏 **Informação de escala não encontrada.**"

def format_count_response(primary_result):
    """Format response for counting queries."""
    if not primary_result.get("results"):
        return "🔢 **Nenhum elemento encontrado para contar.**"
    
    result = primary_result["results"][0]
    if 'count' in result:
        count = result['count']
        return f"🔢 **{count} elemento(s) encontrado(s)**"
    
    # If it's a list of results, count them
    count = len(primary_result["results"])
    return f"🔢 **{count} elemento(s) encontrado(s)**"

def format_project_info_response(primary_result):
    """Format response for project information queries."""
    if not primary_result.get("results"):
        return "📄 **Informações do projeto não encontradas.**"
    
    info_parts = []
    for result in primary_result["results"]:
        for key, value in result.items():
            if value and str(value).strip():
                info_parts.append(str(value).strip())
    
    if not info_parts:
        return "📄 **Informações do projeto não disponíveis.**"
    
    if len(info_parts) == 1:
        return f"📄 **Projeto:** {info_parts[0]}"
    
    return f"📄 **Informações do projeto:**\n" + "\n".join([f"• {info}" for info in info_parts[:5]])

def format_generic_response(primary_result, alternative_results, intent):
    """Generic formatter for other query types."""
    if not primary_result.get("results"):
        return f"ℹ️ **Nenhum resultado encontrado para: {intent}**"
    
    result_count = len(primary_result["results"])
    
    if result_count == 1:
        return f"ℹ️ **1 resultado encontrado**"
    
    return f"ℹ️ **{result_count} resultado(s) encontrado(s)**"


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
    ocr_job_id: Optional[str] = None


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
    
    # Validate file size - ETAPA 2: Removendo limite temporário para DWG
    content = await file.read()
    max_size = 50 * 1024 * 1024  # 50MB para ambos DWG e DXF para teste ETAPA 2
    if len(content) > max_size:
        size_mb = len(content) / (1024 * 1024)
        limit_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=413, 
            detail=f"File size ({size_mb:.1f}MB) must be less than {limit_mb}MB for {file_ext.upper()} files"
        )
    
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
        # Extract CAD data with enhanced pipeline (including OCR analysis)
        print(f"[UPLOAD] Starting CAD data extraction from: {file_path}")
        print(f"[UPLOAD] File size: {file_path.stat().st_size} bytes")
        print(f"[UPLOAD] File extension: {file_path.suffix.lower()}")
        
        # ✅ REATIVADO: Pipeline enhanced com OCR para enriquecimento de grafos
        use_enhanced = True  # Habilitar enhanced para OCR e análise visual
        # Força desabilitação do OCR no enhanced_data_extraction.py
        # ✅ REATIVADO: Análise visual para detecção de cores e padrões
        enable_visual_analysis = True  # os.getenv("ENABLE_VISUAL_ANALYSIS", "true").lower() == "true"
        print(f"[UPLOAD] Enhanced OCR pipeline enabled: {use_enhanced}")
        print(f"[UPLOAD] Visual analysis enabled: {enable_visual_analysis}")
        
        extraction_start_time = time.time()
        
        if use_enhanced:
            # Use enhanced extraction with gap analysis AND visual analysis
            print("[UPLOAD] Using enhanced extraction with OCR pipeline and visual analysis...")
            enhanced_result = enhanced_extract_cad_data(
                file_path, 
                enable_ocr=True,  # ✅ REATIVADO: OCR habilitado para enriquecimento
                enable_visual_analysis=enable_visual_analysis
            )
            print("[UPLOAD] Enhanced extraction completed successfully")
            
            # Get the traditional JSON path for backward compatibility
            json_path = Path(enhanced_result["vector_data"]["json_path"])
            
            # Log enhanced extraction metrics
            metrics = enhanced_result["extraction_metadata"]["metrics"]
            print(f"[UPLOAD] Enhanced extraction completed:")
            print(f"[UPLOAD]   - Vector entities: {metrics['extraction_stats']['vector_entities']}")
            print(f"[UPLOAD]   - Suspicious regions: {metrics['extraction_stats']['suspicious_regions']}")
            print(f"[UPLOAD]   - Rendered regions: {metrics['extraction_stats']['rendered_regions']}")
            print(f"[UPLOAD]   - Total time: {metrics['timing']['total_time']:.2f}s")
        else:
            # Use traditional extraction
            print("[UPLOAD] Using traditional extraction...")
            json_path = extract_cad_data(file_path)
            extraction_time = time.time() - extraction_start_time
            print(f"[UPLOAD] Traditional JSON extracted to: {json_path} in {extraction_time:.2f}s")
        
        # Check if entities file exists (preferred format)
        print(f"[UPLOAD] Checking for entities file...")
        entities_path = json_path.parent / f"{json_path.stem}-entities.json"
        if entities_path.exists():
            print(f"[UPLOAD] Found entities file: {entities_path}")
            json_path = entities_path
        else:
            print(f"[UPLOAD] No entities file found, using: {json_path}")
        
        # Check if JSON file exists and is readable
        print(f"[UPLOAD] Verifying JSON file exists: {json_path}")
        if not json_path.exists():
            raise Exception(f"JSON extraction failed - output file not found: {json_path}")
        
        json_file_size = json_path.stat().st_size
        print(f"[UPLOAD] JSON file size: {json_file_size} bytes")
        
        # Try to read the JSON file with multiple encodings
        print(f"[UPLOAD] Reading JSON file...")
        parse_start_time = time.time()
        test_data = None
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(json_path, 'r', encoding=encoding) as f:
                    test_data = json.load(f)
                parse_time = time.time() - parse_start_time
                data_count = len(test_data) if isinstance(test_data, list) else 'object'
                print(f"[UPLOAD] JSON file successfully parsed with {encoding} encoding in {parse_time:.2f}s, contains {data_count}")
                break
            except UnicodeDecodeError:
                print(f"[UPLOAD] Failed to decode with {encoding}, trying next encoding")
                continue
            except json.JSONDecodeError as je:
                raise Exception(f"JSON file format error: {je}")
        
        if test_data is None:
            raise Exception("Could not read JSON file with any supported encoding")
        
        # Transform to graph format
        print("[UPLOAD] Transforming to graph format...")
        graph_start_time = time.time()
        
        # Determine entity count efficiently (reuse already parsed data)
        entities_count = len(test_data) if isinstance(test_data, list) else len(test_data.get('OBJECTS', []))
        print(f"[UPLOAD] Entity count: {entities_count:,}")
        
        # STREAMING PRIORITY: Use streaming for large files regardless of enhanced processing
        if entities_count > 5000:  # Aggressive threshold for better memory management
            print(f"[UPLOAD] Large file detected ({entities_count:,} entities) - using streaming transformation...")
            # Smaller chunks for better memory control
            chunk_size = 2000 if entities_count > 20000 else 3000
            
            # Add timeout protection
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("[UPLOAD] Streaming transformation timeout after 120 seconds")
            
            # Set 2 minute timeout for streaming
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(120)
            
            try:
                graph_payload = transform_to_graph_streaming(json_path, chunk_size=chunk_size)
                signal.alarm(0)  # Cancel timeout
            except TimeoutError as e:
                print(f"[UPLOAD] {e}")
                print("[UPLOAD] Falling back to traditional transformation...")
                graph_payload = transform_to_graph(json_path)
                signal.alarm(0)  # Cancel timeout
        # Use enhanced transformation if we have enhanced data with visual analysis
        elif use_enhanced and 'enhanced_result' in locals() and enhanced_result.get('visual_nodes'):
            print("[UPLOAD] Using enhanced transformation with visual data...")
            graph_payload = transform_enhanced_to_graph(enhanced_result)
        else:
            print(f"[UPLOAD] Using traditional transformation for {entities_count:,} entities...")
            graph_payload = transform_to_graph(json_path)
        
        graph_time = time.time() - graph_start_time
        print(f"[UPLOAD] Graph payload created with {len(graph_payload.get('nodes', []))} nodes in {graph_time:.2f}s")
        
        # Force garbage collection after transformation
        import gc
        gc.collect()
        print("[UPLOAD] Memory cleanup performed after transformation")
        
        # If enhanced extraction was used, enrich with OCR data
        if use_enhanced and 'enhanced_result' in locals():
            print("Enriching graph with OCR data...")
            
            # Check if we have OCR results to process
            if enhanced_result.get("ocr_pipeline", {}).get("ready_for_ocr", False):
                # Get the rendered regions
                rendered_regions_count = enhanced_result["ocr_pipeline"]["rendered_regions_count"]
                
                # TODO: In production, this would call the actual OCR processor
                # For now, create placeholder enrichment data
                ocr_enrichment_data = {
                    "ocr_nodes": [],
                    "validation_relationships": [],
                    "discovery_relationships": []
                }
                
                # Simulate OCR results based on rendered regions
                if rendered_regions_count > 0:
                    print(f"Processing {rendered_regions_count} rendered regions for OCR...")
                    
                    # In production: 
                    # ocr_results = process_ocr_pipeline(enhanced_result)
                    # validation_report = cross_validate_cad_ocr(ocr_results, entities)
                    # ocr_enrichment_data = get_neo4j_enrichment_data(validation_report)
                    
                    # For now, create sample OCR enrichment
                    gap_data = enhanced_result.get("gap_analysis", {}).get("coverage_data", {})
                    if gap_data and gap_data.get("suspicious_regions"):
                        for i, region in enumerate(gap_data["suspicious_regions"][:3]):
                            ocr_enrichment_data["ocr_nodes"].append({
                                "text": f"OCR Text {i+1}",
                                "confidence": 0.85,
                                "region_id": f"region_{i}",
                                "region_type": region.get("region_type", "unknown"),
                                "processing_engine": "placeholder",
                                "extracted_info": {}
                            })
                
                # Enrich graph if we have OCR data
                if ocr_enrichment_data["ocr_nodes"]:
                    from graph_loader import enhance_graph_with_ocr
                    graph_payload = enhance_graph_with_ocr(graph_payload, ocr_enrichment_data)
                    print(f"Graph enriched with {len(ocr_enrichment_data['ocr_nodes'])} OCR nodes")
        
        # Load into Neo4j with retry logic
        print("[UPLOAD] Loading to Neo4j...")
        neo4j_start_time = time.time()
        
        # Circuit breaker pattern for Neo4j loading
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                load_to_neo4j(graph_payload)
                neo4j_time = time.time() - neo4j_start_time
                print(f"[UPLOAD] Successfully loaded to Neo4j in {neo4j_time:.2f}s")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"[UPLOAD] Failed to load to Neo4j after {max_retries} attempts: {e}")
                    raise
                wait_time = retry_delay * (2 ** attempt)
                print(f"[UPLOAD] Neo4j load failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                time.sleep(wait_time)
                gc.collect()  # Clean memory before retry
        
        # Count entities and graph elements
        entities_count = len(test_data) if isinstance(test_data, list) else len(test_data.get('entities', []))
        nodes_count = len(graph_payload.get('nodes', []))
        relationships_count = len(graph_payload.get('relationships', []))
        
        # Check if async OCR processing was requested
        if use_enhanced and os.getenv("ENABLE_ASYNC_OCR", "false").lower() == "true":
            # Submit for async OCR processing
            processor = get_async_processor()
            job_id = processor.submit_job(file_path, {"priority": "high"})
            
            return UploadResponse(
                message=f"File processed successfully. OCR job {job_id} submitted for background processing.",
                file_path=str(file_path),
                entities_extracted=entities_count,
                nodes_created=nodes_count,
                relationships_created=relationships_count,
                ocr_job_id=job_id
            )
        
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

class IntelligentAnalysisResponse(BaseModel):
    project_type: str
    main_purpose: str
    scale: str
    complexity_level: str
    key_elements: List[str]
    insights: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    summary: str
    analysis_time: float


OPENAI_SUMMARY_MODEL = "gpt-4o"


@app.post("/api/query", response_model=QueryResponse)
async def run_query(req: QueryRequest):
    """Endpoint that converts NL question to Cypher, executes, returns results."""

    try:
        # Use smart router to handle intelligent analysis or Cypher queries
        result = await smart_query_router_async(req.question)
        
        # Check if it's an intelligent analysis (contains markdown formatting)
        if result.startswith('#') or '**' in result or '•' in result:
            # Return intelligent analysis directly
            return QueryResponse(
                cypher="-- Intelligent Analysis --",
                results=[{"analysis": result}],
                summary=result  # Use intelligent analysis as summary
            )
        else:
            # It's a Cypher query, continue with execution
            cypher = result
            
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
        
        # Generate smart explanation based on intent and results
        intent = smart_results["interpretation"].get("intent", smart_results["interpretation"].get("detected_intent", "unknown"))
        
        if intent == "intelligent_project_analysis":
            # Handle intelligent analysis response
            explanation = primary_result.get("analysis", "Análise não disponível")
        elif intent == "legend_search":
            explanation = format_legend_response(primary_result, alternative_results)
        elif intent == "scale_info":
            explanation = format_scale_response(primary_result, alternative_results)
        elif intent == "count_query":
            explanation = format_count_response(primary_result)
        elif intent == "project_info":
            explanation = format_project_info_response(primary_result)
        else:
            # Generic format
            explanation = format_generic_response(primary_result, alternative_results, intent)
        
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


@app.post("/api/intelligent-analysis", response_model=IntelligentAnalysisResponse)
async def intelligent_analysis():
    """Dedicated endpoint for comprehensive intelligent project analysis."""
    
    try:
        import time
        start_time = time.time()
        
        from intelligent_project_analyzer import IntelligentProjectAnalyzer
        
        analyzer = IntelligentProjectAnalyzer()
        analysis = analyzer.analyze_complete_project()
        analyzer.close()
        
        analysis_time = time.time() - start_time
        
        # Convert dataclass insights to dict
        insights_dict = []
        for insight in analysis.insights:
            insights_dict.append({
                "category": insight.category,
                "title": insight.title,
                "description": insight.description,
                "confidence": insight.confidence,
                "supporting_data": insight.supporting_data
            })
        
        return IntelligentAnalysisResponse(
            project_type=analysis.project_type,
            main_purpose=analysis.main_purpose,
            scale=analysis.scale,
            complexity_level=analysis.complexity_level,
            key_elements=analysis.key_elements,
            insights=insights_dict,
            statistics=analysis.statistics,
            summary=analysis.summary,
            analysis_time=analysis_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intelligent analysis failed: {str(e)}")


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
                    },
                    {
                        "category": "Análise Visual",
                        "questions": [
                            "Quais cores aparecem nas legendas?",
                            "Que padrões visuais são usados?",
                            "Como são identificados os elementos verdes?",
                            "Quais elementos têm padrão pontilhado?",
                            "Qual o esquema de cores do projeto?"
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


@app.get("/api/graph-stats")
async def get_graph_stats():
    """Get current graph statistics including node counts and types."""
    try:
        from semantic_query_enhancer import semantic_enhancer
        
        with semantic_enhancer.driver.session() as session:
            # Get total node count
            node_count_result = session.run("MATCH (n) RETURN count(n) AS total_nodes")
            total_nodes = node_count_result.single()["total_nodes"]
            
            # Get total relationship count
            rel_count_result = session.run("MATCH ()-[r]->() RETURN count(r) AS total_relationships")
            total_relationships = rel_count_result.single()["total_relationships"]
            
            # Get node types
            node_types_result = session.run("MATCH (n) RETURN DISTINCT labels(n) AS labels")
            node_types = []
            for record in node_types_result:
                labels = record["labels"]
                if labels:  # Skip nodes without labels
                    node_types.extend(labels)
            
            # Remove duplicates and sort
            node_types = sorted(list(set(node_types)))
            
            # Get last activity (approximate by checking latest timestamp if available)
            try:
                last_activity_result = session.run("""
                    MATCH (n)
                    WHERE n.created_at IS NOT NULL
                    RETURN max(n.created_at) AS last_updated
                """)
                last_updated_record = last_activity_result.single()
                last_updated = last_updated_record["last_updated"] if last_updated_record and last_updated_record["last_updated"] else "Unknown"
            except:
                # Fallback if no timestamp fields exist
                last_updated = "Recent"
            
            return {
                "nodes": total_nodes,
                "relationships": total_relationships,
                "node_types": node_types,
                "last_updated": str(last_updated)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get graph stats: {str(e)}")


@app.post("/api/query-stream")
async def stream_query(request: QueryRequest):
    """Stream query responses for real-time chat experience."""
    
    async def generate_stream():
        try:
            from semantic_query_enhancer import semantic_enhancer
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'content': 'Processing query...'})}\n\n"
            
            # Process the query using existing smart query logic
            enhanced_query = semantic_enhancer.enhance_query(request.question)
            
            # Send enhanced query info
            yield f"data: {json.dumps({'type': 'query_enhanced', 'content': f'Enhanced query: {enhanced_query}'})}\n\n"
            
            # Execute the query
            result = semantic_enhancer.execute_smart_search(enhanced_query)
            
            # Stream the results in chunks
            if result.get("primary_result"):
                primary = result["primary_result"]
                
                # Send Cypher query
                if primary.get("cypher"):
                    cypher_content = f"```cypher\n{primary['cypher']}\n```"
                    yield f"data: {json.dumps({'type': 'cypher', 'content': cypher_content})}\n\n"
                
                # Send description
                if primary.get("description"):
                    yield f"data: {json.dumps({'type': 'description', 'content': primary['description']})}\n\n"
                
                # Send results
                if primary.get("results"):
                    results_text = f"Found {len(primary['results'])} results:\n\n"
                    for i, record in enumerate(primary["results"][:5]):  # Limit to first 5 results
                        results_text += f"**Result {i+1}:**\n"
                        for key, value in record.items():
                            results_text += f"- {key}: {value}\n"
                        results_text += "\n"
                    
                    yield f"data: {json.dumps({'type': 'results', 'content': results_text})}\n\n"
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'complete', 'content': 'Query completed successfully!'})}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            error_msg = f"Query failed: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
    )

@app.post("/api/visual-analysis")
async def run_visual_analysis(file: UploadFile = File(...)):
    """Run visual analysis on uploaded CAD file to extract colors and patterns from legends."""
    
    if not file.filename.lower().endswith(('.dwg', '.dxf')):
        raise HTTPException(status_code=400, detail="Only DWG and DXF files are supported")
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = Path(tmp_file.name)
        
        # Run enhanced extraction with visual analysis enabled
        result = enhanced_extract_cad_data(
            file_path=tmp_file_path,
            enable_ocr=True,
            enable_visual_analysis=True
        )
        
        # Cleanup temporary file
        tmp_file_path.unlink()
        
        # Extract visual analysis results
        visual_analysis = result.get('visual_analysis', {})
        
        return {
            "status": "success",
            "visual_analysis": visual_analysis,
            "legend_elements": visual_analysis.get('legend_elements', []),
            "color_summary": {
                "total_colors": len(set(elem.get('color_name', '') for elem in visual_analysis.get('legend_elements', []))),
                "total_patterns": len(set(elem.get('pattern_type', '') for elem in visual_analysis.get('legend_elements', []))),
                "total_elements": visual_analysis.get('total_elements', 0)
            },
            "confidence": visual_analysis.get('analysis_confidence', 0.0)
        }
        
    except Exception as e:
        # Cleanup on error
        if 'tmp_file_path' in locals() and tmp_file_path.exists():
            tmp_file_path.unlink()
        
        raise HTTPException(status_code=500, detail=f"Visual analysis failed: {str(e)}")

@app.get("/api/visual-search")
async def visual_search(query: str, search_type: str = "all"):
    """
    Search for visual elements in the graph database.
    
    search_type: 'colors', 'patterns', 'legends', or 'all'
    """
    
    try:
        from semantic_query_enhancer import semantic_enhancer
        
        # Create a query based on search type
        enhanced_query = f"{search_type} {query}"
        
        # Force specific intent detection
        if search_type == "colors":
            intent = "color_search"
        elif search_type == "patterns": 
            intent = "pattern_search"
        elif search_type == "legends":
            intent = "visual_legend_search"
        else:
            # Let the enhancer detect intent
            intent = None
        
        # Execute smart search
        if intent:
            # Manually create the enhancement for specific visual searches
            enhancements = {
                "original_question": enhanced_query,
                "detected_intent": intent,
                "semantic_terms": [],
                "suggested_queries": [],
                "context_queries": [],
                "explanation": ""
            }
            
            if intent == "color_search":
                color_term = semantic_enhancer._extract_color_term(query.lower())
                enhancements["suggested_queries"] = semantic_enhancer._generate_color_search_queries(color_term)
                enhancements["explanation"] = f"Buscando por cores{' (' + color_term + ')' if color_term else ''} em legendas visuais"
            elif intent == "pattern_search":
                pattern_term = semantic_enhancer._extract_pattern_term(query.lower())
                enhancements["suggested_queries"] = semantic_enhancer._generate_pattern_search_queries(pattern_term)
                enhancements["explanation"] = f"Buscando por padrões visuais{' (' + pattern_term + ')' if pattern_term else ''}"
            elif intent == "visual_legend_search":
                enhancements["suggested_queries"] = semantic_enhancer._generate_visual_legend_search_queries()
                enhancements["explanation"] = "Análise completa de legendas visuais incluindo cores e padrões"
            
            # Execute queries
            query_results = []
            with semantic_enhancer.driver.session() as session:
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
            
            # Find best result
            successful_results = [r for r in query_results if r["success"] and r["result_count"] > 0]
            best_match = max(successful_results, key=lambda x: x["result_count"]) if successful_results else None
            
            return {
                "status": "success",
                "search_type": search_type,
                "interpretation": {
                    "original_question": enhanced_query,
                    "detected_intent": intent,
                    "explanation": enhancements["explanation"]
                },
                "query_results": query_results,
                "best_match": best_match,
                "total_queries_executed": len(query_results),
                "successful_queries": len([r for r in query_results if r["success"]])
            }
        else:
            # Use regular smart search
            result = semantic_enhancer.execute_smart_search(enhanced_query)
            result["search_type"] = search_type
            result["status"] = "success"
            return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visual search failed: {str(e)}")

# Include OCR routers
# ✅ REATIVADO: Routers OCR para enriquecimento de grafos
app.include_router(ocr_router)
app.include_router(async_ocr_router)

# Serve static files (frontend)
if os.path.exists("/app/static"):
    app.mount("/", StaticFiles(directory="/app/static", html=True), name="static") 