"""
OCR Integration Endpoint - Endpoints específicos para funcionalidades OCR

Fornece APIs dedicadas para análise de gaps, renderização seletiva e
gerenciamento do pipeline OCR sem afetar o fluxo principal de upload.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import os

from enhanced_data_extraction import EnhancedCADExtractor, compare_extraction_methods
from gap_analyzer import analyze_cad_gaps
from selective_renderer import render_cad_regions, RenderingConfig
from ocr_structures import ROIManager, ProcessingStage


# Criar router para endpoints OCR
ocr_router = APIRouter(prefix="/api/ocr", tags=["OCR Analysis"])


class GapAnalysisRequest(BaseModel):
    """Request para análise de gaps."""
    json_file_path: str
    grid_size: float = 100.0
    min_region_size: float = 50.0


class GapAnalysisResponse(BaseModel):
    """Response da análise de gaps."""
    total_entities: int
    text_entities_count: int
    suspicious_regions_count: int
    drawing_bounds: Dict[str, float]
    top_priority_regions: List[Dict[str, Any]]
    processing_time: float


class RenderingRequest(BaseModel):
    """Request para renderização seletiva."""
    dxf_file_path: str
    regions_to_render: List[Dict[str, Any]]  # Serialized regions
    output_directory: Optional[str] = None
    dpi: int = 300


class RenderingResponse(BaseModel):
    """Response da renderização."""
    rendered_count: int
    output_directory: str
    rendered_regions: List[Dict[str, Any]]
    processing_time: float


class EnhancedExtractionRequest(BaseModel):
    """Request para extração aprimorada."""
    file_path: str
    enable_ocr: bool = True
    enable_gap_analysis: bool = True
    output_directory: Optional[str] = None


class EnhancedExtractionResponse(BaseModel):
    """Response da extração aprimorada."""
    extraction_metadata: Dict[str, Any]
    vector_data_summary: Dict[str, Any]
    gap_analysis_summary: Dict[str, Any]
    ocr_pipeline_summary: Dict[str, Any]
    next_steps: List[str]


@ocr_router.post("/analyze-gaps", response_model=GapAnalysisResponse)
async def analyze_gaps(request: GapAnalysisRequest):
    """
    Analisa gaps de cobertura de texto em dados CAD extraídos.
    
    Identifica regiões do desenho que podem conter texto não capturado
    pelos parsers vetoriais tradicionais.
    """
    try:
        import time
        start_time = time.time()
        
        json_path = Path(request.json_file_path)
        if not json_path.exists():
            raise HTTPException(status_code=404, detail=f"JSON file not found: {json_path}")
        
        # Executar análise de gaps
        coverage = analyze_cad_gaps(
            json_path,
            grid_size=request.grid_size,
            min_region_size=request.min_region_size
        )
        
        processing_time = time.time() - start_time
        
        # Preparar top 5 regiões prioritárias para resposta
        top_regions = []
        for region in coverage.suspicious_regions[:5]:
            top_regions.append({
                "region_type": region.region_type.value,
                "priority": region.priority,
                "confidence": region.confidence,
                "bounds": region.bounds,
                "context": region.context,
                "nearby_entities_count": len(region.nearby_entities)
            })
        
        return GapAnalysisResponse(
            total_entities=coverage.total_entities,
            text_entities_count=len(coverage.text_entities),
            suspicious_regions_count=len(coverage.suspicious_regions),
            drawing_bounds=coverage.drawing_bounds,
            top_priority_regions=top_regions,
            processing_time=processing_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gap analysis failed: {str(e)}")


@ocr_router.post("/render-regions", response_model=RenderingResponse)
async def render_regions(request: RenderingRequest):
    """
    Renderiza regiões específicas de um arquivo DXF como imagens para OCR.
    
    Converte regiões de interesse em imagens de alta qualidade otimizadas
    para processamento OCR posterior.
    """
    try:
        import time
        from gap_analyzer import Region, RegionType
        
        start_time = time.time()
        
        dxf_path = Path(request.dxf_file_path)
        if not dxf_path.exists():
            raise HTTPException(status_code=404, detail=f"DXF file not found: {dxf_path}")
        
        if dxf_path.suffix.lower() != '.dxf':
            raise HTTPException(status_code=400, detail="Only DXF files are supported for rendering")
        
        # Reconstruir objetos Region a partir dos dados serializados
        regions = []
        for region_data in request.regions_to_render:
            region = Region(
                bounds=region_data["bounds"],
                region_type=RegionType(region_data["region_type"]),
                priority=region_data["priority"],
                confidence=region_data["confidence"],
                context=region_data.get("context", {}),
                nearby_entities=region_data.get("nearby_entities", [])
            )
            regions.append(region)
        
        # Configurar renderização
        rendering_config = RenderingConfig(dpi=request.dpi)
        
        # Determinar diretório de saída
        if request.output_directory:
            output_dir = Path(request.output_directory)
        else:
            output_dir = dxf_path.parent / "rendered_regions"
        
        # Renderizar regiões
        rendered_regions = render_cad_regions(
            dxf_path,
            regions,
            output_dir,
            rendering_config
        )
        
        processing_time = time.time() - start_time
        
        # Preparar resposta
        rendered_data = []
        for rendered in rendered_regions:
            rendered_data.append({
                "region_type": rendered.region.region_type.value,
                "image_size": rendered.image.size,
                "actual_bounds": rendered.actual_bounds,
                "scale_factor": rendered.scale_factor,
                "metadata": rendered.metadata
            })
        
        return RenderingResponse(
            rendered_count=len(rendered_regions),
            output_directory=str(output_dir),
            rendered_regions=rendered_data,
            processing_time=processing_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")


@ocr_router.post("/enhanced-extraction", response_model=EnhancedExtractionResponse)
async def enhanced_extraction(request: EnhancedExtractionRequest):
    """
    Executa extração CAD aprimorada com pipeline completo de análise OCR.
    
    Combina extração vetorial tradicional com análise de gaps e renderização
    seletiva para preparar dados para processamento OCR.
    """
    try:
        file_path = Path(request.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"CAD file not found: {file_path}")
        
        # Configurar diretório de saída
        if request.output_directory:
            output_dir = Path(request.output_directory)
        else:
            output_dir = file_path.parent / "enhanced_extraction"
        
        # Executar extração aprimorada
        extractor = EnhancedCADExtractor(
            enable_ocr=request.enable_ocr,
            gap_analysis_enabled=request.enable_gap_analysis
        )
        
        result = extractor.extract_enhanced_cad_data(file_path, output_dir)
        
        # Gerar relatório
        report = extractor.get_extraction_report()
        
        # Preparar resposta
        return EnhancedExtractionResponse(
            extraction_metadata=result["extraction_metadata"],
            vector_data_summary={
                "entities_count": len(result["vector_data"]["entities"]),
                "text_entities": len([e for e in result["vector_data"]["entities"] if e.get("type") in ["TEXT", "MTEXT"]]),
                "json_path": result["vector_data"]["json_path"],
                "drawing_bounds": result["vector_data"]["drawing_bounds"]
            },
            gap_analysis_summary=result["gap_analysis"],
            ocr_pipeline_summary=result["ocr_pipeline"],
            next_steps=report["next_steps"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enhanced extraction failed: {str(e)}")


@ocr_router.get("/extraction-comparison/{file_name}")
async def extraction_comparison(file_name: str, background_tasks: BackgroundTasks):
    """
    Compara métodos de extração tradicional vs aprimorada para um arquivo.
    
    Útil para avaliar o benefício do pipeline OCR para diferentes tipos de desenho.
    """
    try:
        # Buscar arquivo em diretórios comuns
        possible_paths = [
            Path("uploads") / file_name,
            Path("test-files") / file_name,
            Path(".") / file_name
        ]
        
        file_path = None
        for path in possible_paths:
            if path.exists():
                file_path = path
                break
        
        if not file_path:
            raise HTTPException(status_code=404, detail=f"File not found: {file_name}")
        
        # Executar comparação em background se arquivo grande
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        
        if file_size_mb > 10:  # Arquivos > 10MB em background
            background_tasks.add_task(compare_extraction_methods, file_path)
            return {
                "status": "comparison_started",
                "message": f"Comparison started for large file ({file_size_mb:.1f}MB)",
                "estimated_time": "2-5 minutes"
            }
        else:
            # Executar comparação diretamente
            comparison = compare_extraction_methods(file_path)
            return {
                "status": "completed",
                "comparison": comparison
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@ocr_router.get("/roi-status")
async def get_roi_status():
    """
    Retorna status atual do gerenciador ROI global.
    
    Útil para monitorar progresso do pipeline OCR em arquivos processados.
    """
    try:
        # Verificar se existe ROI manager ativo (seria melhor usar singleton ou cache)
        roi_manager = ROIManager()  # Placeholder - em produção usar instância compartilhada
        
        summary = roi_manager.get_processing_summary()
        quality_metrics = roi_manager.get_quality_metrics()
        
        return {
            "roi_summary": summary,
            "quality_metrics": quality_metrics,
            "active_regions": len(roi_manager.regions),
            "stages_distribution": {
                stage.value: sum(1 for s in roi_manager.processing_stages.values() if s == stage)
                for stage in ProcessingStage
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ROI status failed: {str(e)}")


@ocr_router.get("/health")
async def ocr_health_check():
    """
    Verifica saúde dos componentes OCR.
    
    Testa disponibilidade de dependências e configurações necessárias.
    """
    health_status = {
        "timestamp": time.time(),
        "overall_status": "healthy",
        "components": {},
        "warnings": []
    }
    
    try:
        # Testar importações críticas
        try:
            from gap_analyzer import CadGapAnalyzer
            health_status["components"]["gap_analyzer"] = "ok"
        except Exception as e:
            health_status["components"]["gap_analyzer"] = f"error: {str(e)}"
            health_status["overall_status"] = "degraded"
        
        try:
            from selective_renderer import SelectiveCADRenderer
            health_status["components"]["selective_renderer"] = "ok"
        except Exception as e:
            health_status["components"]["selective_renderer"] = f"error: {str(e)}"
            health_status["overall_status"] = "degraded"
        
        try:
            import ezdxf
            health_status["components"]["ezdxf"] = "ok"
        except Exception as e:
            health_status["components"]["ezdxf"] = f"error: {str(e)}"
            health_status["overall_status"] = "unhealthy"
        
        try:
            import matplotlib
            health_status["components"]["matplotlib"] = "ok"
        except Exception as e:
            health_status["components"]["matplotlib"] = f"error: {str(e)}"
            health_status["overall_status"] = "degraded"
        
        # Verificar configurações
        ocr_enabled = os.getenv("ENABLE_OCR_PIPELINE", "false").lower() == "true"
        health_status["configuration"] = {
            "ocr_pipeline_enabled": ocr_enabled,
            "mistral_api_key_configured": bool(os.getenv("MISTRAL_API_KEY"))
        }
        
        # Avisos
        if not ocr_enabled:
            health_status["warnings"].append("OCR pipeline disabled - set ENABLE_OCR_PIPELINE=true to enable")
        
        if not os.getenv("MISTRAL_API_KEY"):
            health_status["warnings"].append("MISTRAL_API_KEY not configured - OCR will fall back to Tesseract only")
        
        return health_status
        
    except Exception as e:
        return {
            "timestamp": time.time(),
            "overall_status": "unhealthy",
            "error": str(e)
        }


# Adicionar router ao app principal seria feito em main.py:
# app.include_router(ocr_router)

if __name__ == "__main__":
    # Teste rápido dos endpoints
    import uvicorn
    from fastapi import FastAPI
    
    test_app = FastAPI(title="OCR Integration Test")
    test_app.include_router(ocr_router)
    
    print("🧪 OCR Integration Endpoints Test Server")
    print("Endpoints disponíveis:")
    print("  - POST /api/ocr/analyze-gaps")
    print("  - POST /api/ocr/render-regions") 
    print("  - POST /api/ocr/enhanced-extraction")
    print("  - GET  /api/ocr/extraction-comparison/{file_name}")
    print("  - GET  /api/ocr/roi-status")
    print("  - GET  /api/ocr/health")
    
    uvicorn.run(test_app, host="0.0.0.0", port=8001)