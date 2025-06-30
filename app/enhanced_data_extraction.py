"""
Enhanced Data Extraction - Pipeline CAD com análise OCR inteligente

Integra o pipeline de extração tradicional com análise de gaps e renderização seletiva
para OCR, fornecendo extração completa de dados CAD incluindo texto rasterizado.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import asdict

from data_extraction import extract_cad_data as extract_cad_data_base
from gap_analyzer import CadGapAnalyzer, analyze_cad_gaps, CADCoverage
from selective_renderer import SelectiveCADRenderer, RenderingConfig, render_cad_regions
from ocr_structures import (
    ROIManager, CADContext, ProcessingStage, RegionType,
    create_cad_context
)


class EnhancedCADExtractor:
    """
    Extrator CAD aprimorado com capacidades OCR inteligentes.
    
    Combina extração vetorial tradicional com análise de gaps e OCR
    para capturar informações completas de desenhos técnicos.
    """
    
    def __init__(self, 
                 enable_ocr: bool = True,
                 gap_analysis_enabled: bool = True,
                 rendering_config: Optional[RenderingConfig] = None,
                 smart_gap_analysis: bool = True):
        """
        Inicializa o extrator aprimorado.
        
        Args:
            enable_ocr: Habilitar pipeline OCR
            gap_analysis_enabled: Habilitar análise de gaps
            rendering_config: Configuração de renderização
            smart_gap_analysis: Desabilitar gaps automaticamente para arquivos grandes
        """
        self.enable_ocr = enable_ocr
        self.gap_analysis_enabled = gap_analysis_enabled
        self.smart_gap_analysis = smart_gap_analysis
        self.rendering_config = rendering_config or RenderingConfig()
        
        # Componentes com otimizações para arquivos grandes
        self.gap_analyzer = CadGapAnalyzer(
            max_entities=3000,  # Reduzido para 3000 entidades
            analysis_timeout=20.0  # Reduzido para 20 segundos
        ) if gap_analysis_enabled else None
        self.renderer = SelectiveCADRenderer(self.rendering_config) if enable_ocr else None
        self.roi_manager = ROIManager()
        
        # Métricas
        self.extraction_metrics = {}
        
    def extract_enhanced_cad_data(self, file_path: Path, 
                                 output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Extrai dados CAD com pipeline aprimorado incluindo OCR.
        
        Args:
            file_path: Caminho para arquivo CAD
            output_dir: Diretório de saída (opcional)
            
        Returns:
            Dados extraídos incluindo entidades vetoriais e OCR
        """
        start_time = time.time()
        file_path = Path(file_path)
        
        if output_dir is None:
            output_dir = file_path.parent / "enhanced_extraction"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🔍 Iniciando extração aprimorada: {file_path.name}")
        
        try:
            # 1. Extração vetorial tradicional
            print("📐 Extraindo dados vetoriais...")
            vector_extraction_start = time.time()
            json_path = extract_cad_data_base(file_path)
            vector_extraction_time = time.time() - vector_extraction_start
            
            # Carregar entidades extraídas
            with open(json_path, 'r', encoding='utf-8') as f:
                cad_data = json.load(f)
            
            # Normalizar estrutura
            if isinstance(cad_data, list):
                entities = cad_data
            elif isinstance(cad_data, dict) and 'entities' in cad_data:
                entities = cad_data['entities']
            else:
                entities = []
            
            print(f"   ✅ {len(entities)} entidades vetoriais extraídas")
            
            # 2. Análise de gaps (se habilitada e inteligente)
            gap_coverage = None
            gap_analysis_time = 0
            
            # SMART GAP ANALYSIS: Desabilitar para arquivos grandes automaticamente
            effective_gap_analysis = self.gap_analysis_enabled
            if self.smart_gap_analysis and len(entities) > 2000:
                print(f"🔍 ⚡ SMART: Arquivo grande ({len(entities)} entidades) - desabilitando análise de gaps para melhor performance")
                effective_gap_analysis = False
            
            if effective_gap_analysis and entities:
                print("🔍 Analisando gaps de cobertura...")
                gap_analysis_start = time.time()
                gap_coverage = self.gap_analyzer.analyze_coverage(entities)
                gap_analysis_time = time.time() - gap_analysis_start
                
                print(f"   ✅ {len(gap_coverage.suspicious_regions)} regiões suspeitas identificadas")
            elif not effective_gap_analysis:
                print("🔍 ⚡ Análise de gaps desabilitada - usando extração tradicional otimizada")
                # Criar cobertura mínima sem análise
                gap_coverage = self._create_minimal_gap_coverage(entities)
                
                # Adicionar regiões ao ROI manager
                for region in gap_coverage.suspicious_regions:
                    region_id = self.roi_manager.add_region(region)
                    self.roi_manager.update_stage(region_id, ProcessingStage.ANALYSIS)
            
            # 3. Renderização seletiva (se OCR habilitado)
            rendered_regions = []
            rendering_time = 0
            
            if self.enable_ocr and gap_coverage and gap_coverage.suspicious_regions:
                print("🎨 Renderizando regiões prioritárias...")
                rendering_start = time.time()
                
                # Filtrar apenas regiões de alta prioridade para renderização
                high_priority_regions = [
                    r for r in gap_coverage.suspicious_regions 
                    if r.priority > 0.5
                ]
                
                if high_priority_regions and file_path.suffix.lower() in ['.dxf', '.dwg']:
                    try:
                        rendered_regions = render_cad_regions(
                            file_path, 
                            high_priority_regions,
                            output_dir / "rendered_regions",
                            self.rendering_config
                        )
                        
                        # Atualizar ROI manager
                        for rendered in rendered_regions:
                            region_type = rendered.region.region_type.value
                            # Encontrar region_id correspondente
                            for region_id, stage in self.roi_manager.processing_stages.items():
                                if region_id.startswith(region_type):
                                    self.roi_manager.rendered_regions[region_id] = rendered
                                    self.roi_manager.update_stage(region_id, ProcessingStage.RENDERING)
                                    break
                        
                        print(f"   ✅ {len(rendered_regions)} regiões renderizadas")
                        
                    except Exception as e:
                        print(f"   ⚠️ Erro na renderização: {str(e)}")
                
                rendering_time = time.time() - rendering_start
            
            # 4. Compilar resultados
            total_time = time.time() - start_time
            
            # Métricas de extração
            self.extraction_metrics = {
                "file_info": {
                    "name": file_path.name,
                    "size_mb": file_path.stat().st_size / (1024 * 1024),
                    "type": file_path.suffix.lower()
                },
                "timing": {
                    "total_time": total_time,
                    "vector_extraction_time": vector_extraction_time,
                    "gap_analysis_time": gap_analysis_time,
                    "rendering_time": rendering_time
                },
                "extraction_stats": {
                    "vector_entities": len(entities),
                    "text_entities": len([e for e in entities if e.get("type") in ["TEXT", "MTEXT"]]),
                    "suspicious_regions": len(gap_coverage.suspicious_regions) if gap_coverage else 0,
                    "rendered_regions": len(rendered_regions),
                    "ocr_enabled": self.enable_ocr,
                    "gap_analysis_enabled": self.gap_analysis_enabled
                }
            }
            
            # Resultado consolidado
            enhanced_result = {
                "extraction_metadata": {
                    "timestamp": time.time(),
                    "source_file": str(file_path),
                    "output_directory": str(output_dir),
                    "metrics": self.extraction_metrics
                },
                "vector_data": {
                    "entities": entities,
                    "json_path": str(json_path),
                    "drawing_bounds": gap_coverage.drawing_bounds if gap_coverage else None
                },
                "gap_analysis": {
                    "enabled": self.gap_analysis_enabled,
                    "coverage_data": asdict(gap_coverage) if gap_coverage else None,
                    "roi_summary": self.roi_manager.get_processing_summary()
                },
                "ocr_pipeline": {
                    "enabled": self.enable_ocr,
                    "rendered_regions_count": len(rendered_regions),
                    "rendering_config": asdict(self.rendering_config) if self.enable_ocr else None,
                    "ready_for_ocr": len(rendered_regions) > 0
                }
            }
            
            # IMPORTANTE: Não salvar ainda - análise visual pode adicionar dados
            print(f"✅ Extração aprimorada base concluída em {total_time:.2f}s")
            
            return enhanced_result
            
        except Exception as e:
            error_info = {
                "error": str(e),
                "file_path": str(file_path),
                "timestamp": time.time(),
                "processing_time": time.time() - start_time
            }
            
            error_path = output_dir / f"{file_path.stem}_extraction_error.json"
            with open(error_path, 'w') as f:
                json.dump(error_info, f, indent=2)
            
            print(f"❌ Erro na extração: {str(e)}")
            raise
    
    def get_ocr_ready_regions(self) -> List[Tuple[str, Any]]:
        """
        Retorna regiões prontas para processamento OCR.
        
        Returns:
            Lista de (region_id, rendered_region) prontas para OCR
        """
        ready_regions = []
        
        for region_id, rendered_region in self.roi_manager.rendered_regions.items():
            stage = self.roi_manager.processing_stages.get(region_id)
            if stage == ProcessingStage.RENDERING and rendered_region:
                ready_regions.append((region_id, rendered_region))
        
        return ready_regions
    
    def create_cad_contexts(self, drawing_bounds: Dict[str, float],
                           project_info: Optional[Dict[str, Any]] = None) -> Dict[str, CADContext]:
        """
        Cria contextos CAD para todas as regiões gerenciadas.
        
        Args:
            drawing_bounds: Bounds do desenho
            project_info: Informações do projeto
            
        Returns:
            Dict com region_id -> CADContext
        """
        contexts = {}
        
        for i, region in enumerate(self.roi_manager.regions):
            region_id = f"{region.region_type.value}_{i:03d}"
            contexts[region_id] = create_cad_context(region, drawing_bounds, project_info)
        
        return contexts
    
    def get_extraction_report(self) -> Dict[str, Any]:
        """
        Gera relatório detalhado da extração.
        
        Returns:
            Relatório completo com métricas e status
        """
        roi_summary = self.roi_manager.get_processing_summary()
        quality_metrics = self.roi_manager.get_quality_metrics()
        
        return {
            "extraction_metrics": self.extraction_metrics,
            "roi_processing": roi_summary,
            "quality_metrics": quality_metrics,
            "pipeline_status": {
                "gap_analysis": "enabled" if self.gap_analysis_enabled else "disabled",
                "ocr_pipeline": "enabled" if self.enable_ocr else "disabled",
                "total_regions": len(self.roi_manager),
                "ocr_ready_regions": len(self.get_ocr_ready_regions())
            },
            "next_steps": self._get_next_steps()
        }
    
    def _get_next_steps(self) -> List[str]:
        """Determina próximos passos baseado no estado atual."""
        steps = []
        
        ocr_ready = self.get_ocr_ready_regions()
        
        if ocr_ready:
            steps.append(f"Processar {len(ocr_ready)} regiões com OCR")
        
        pending_regions = [
            region_id for region_id, stage in self.roi_manager.processing_stages.items()
            if stage in [ProcessingStage.ANALYSIS, ProcessingStage.RENDERING]
        ]
        
        if pending_regions:
            steps.append(f"Completar processamento de {len(pending_regions)} regiões pendentes")
        
        if not steps:
            steps.append("Pipeline de extração básica concluído - OCR opcional")
        
        return steps
    
    def _create_minimal_gap_coverage(self, entities: List[Dict[str, Any]]) -> 'CADCoverage':
        """Cria cobertura mínima sem análise custosa para arquivos grandes."""
        from gap_analyzer import CADCoverage, Region, RegionType
        
        # Calcular bounds básicos
        x_coords, y_coords = [], []
        text_entities = []
        
        for entity in entities:
            entity_type = entity.get("type", "")
            
            if entity_type in ["TEXT", "MTEXT"]:
                text_entities.append(entity)
                
            # Extrair coordenadas simples para bounds
            if entity_type == "LINE":
                start = entity.get("start", {})
                end = entity.get("end", {})
                x_coords.extend([start.get("x", 0), end.get("x", 0)])
                y_coords.extend([start.get("y", 0), end.get("y", 0)])
            elif entity_type in ["TEXT", "MTEXT"]:
                insert = entity.get("insert", {})
                if isinstance(insert, dict):
                    x_coords.append(insert.get("x", 0))
                    y_coords.append(insert.get("y", 0))
        
        if not x_coords or not y_coords:
            drawing_bounds = {"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 100}
        else:
            drawing_bounds = {
                "x_min": min(x_coords), "y_min": min(y_coords),
                "x_max": max(x_coords), "y_max": max(y_coords)
            }
        
        # Criar apenas uma região de title block essencial
        width = drawing_bounds["x_max"] - drawing_bounds["x_min"]
        height = drawing_bounds["y_max"] - drawing_bounds["y_min"]
        
        tb_width = min(width * 0.3, 200)
        tb_height = min(height * 0.2, 100)
        
        title_block_region = Region(
            bounds={
                "x_min": drawing_bounds["x_max"] - tb_width,
                "y_min": drawing_bounds["y_min"],
                "x_max": drawing_bounds["x_max"],
                "y_max": drawing_bounds["y_min"] + tb_height,
            },
            region_type=RegionType.TITLE_BLOCK,
            priority=0.8,
            confidence=0.7,
            context={"smart_gap_analysis": "minimal_coverage", "large_file_optimization": True},
            nearby_entities=[]
        )
        
        return CADCoverage(
            drawing_bounds=drawing_bounds,
            text_entities=text_entities,
            total_entities=len(entities),
            text_coverage_map={},
            suspicious_regions=[title_block_region]
        )


def enhanced_extract_cad_data(file_path: Path, 
                             enable_ocr: bool = True,
                             enable_visual_analysis: bool = False,
                             output_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Função de conveniência para extração CAD aprimorada.
    
    Args:
        file_path: Caminho para arquivo CAD
        enable_ocr: Habilitar pipeline OCR
        enable_visual_analysis: Habilitar análise visual de legendas e cores
        output_dir: Diretório de saída
        
    Returns:
        Dados extraídos com pipeline aprimorado
    """
    extractor = EnhancedCADExtractor(enable_ocr=enable_ocr)
    result = extractor.extract_enhanced_cad_data(file_path, output_dir)
    
    # Adicionar análise visual se habilitada
    if enable_visual_analysis:
        try:
            from visual_graph_enricher import enrich_graph_with_visual_analysis
            result = enrich_graph_with_visual_analysis(result, file_path)
            print("✅ Análise visual Fase 1 (extração direta CAD) concluída")
        except Exception as e:
            print(f"⚠️ Erro na análise visual: {e}")
    
    # Salvar resultado final (com dados visuais se aplicável)
    if output_dir is None:
        output_dir = file_path.parent / "enhanced_extraction"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result_path = output_dir / f"{file_path.stem}_enhanced_extraction.json"
    with open(result_path, 'w', encoding='utf-8') as f:
        import json
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"📊 Resultado final salvo em: {result_path}")
    
    return result


def compare_extraction_methods(file_path: Path) -> Dict[str, Any]:
    """
    Compara extração tradicional vs aprimorada.
    
    Args:
        file_path: Arquivo CAD para comparar
        
    Returns:
        Comparação detalhada dos métodos
    """
    print("🔬 Comparando métodos de extração...")
    
    # Extração tradicional
    traditional_start = time.time()
    traditional_json = extract_cad_data_base(file_path)
    traditional_time = time.time() - traditional_start
    
    with open(traditional_json, 'r') as f:
        traditional_data = json.load(f)
    
    traditional_entities = len(traditional_data) if isinstance(traditional_data, list) else len(traditional_data.get('entities', []))
    
    # Extração aprimorada
    enhanced_start = time.time()
    enhanced_result = enhanced_extract_cad_data(file_path, enable_ocr=True)
    enhanced_time = time.time() - enhanced_start
    
    enhanced_entities = enhanced_result["vector_data"]["entities"]
    gap_data = enhanced_result["gap_analysis"]["coverage_data"]
    
    # Comparação
    comparison = {
        "file_info": {
            "name": file_path.name,
            "size_mb": file_path.stat().st_size / (1024 * 1024)
        },
        "traditional_extraction": {
            "processing_time": traditional_time,
            "entities_count": traditional_entities,
            "text_entities": len([e for e in (traditional_data if isinstance(traditional_data, list) else traditional_data.get('entities', [])) if e.get("type") in ["TEXT", "MTEXT"]])
        },
        "enhanced_extraction": {
            "processing_time": enhanced_time,
            "entities_count": len(enhanced_entities),
            "text_entities": len([e for e in enhanced_entities if e.get("type") in ["TEXT", "MTEXT"]]),
            "suspicious_regions": len(gap_data["suspicious_regions"]) if gap_data else 0,
            "ocr_ready_regions": enhanced_result["ocr_pipeline"]["rendered_regions_count"]
        },
        "improvements": {
            "processing_overhead": enhanced_time - traditional_time,
            "additional_regions_identified": len(gap_data["suspicious_regions"]) if gap_data else 0,
            "ocr_coverage_potential": f"{(enhanced_result['ocr_pipeline']['rendered_regions_count'] / max(1, len(enhanced_entities))) * 100:.1f}%"
        },
        "recommendations": []
    }
    
    # Recomendações baseadas nos resultados
    if comparison["enhanced_extraction"]["suspicious_regions"] > 0:
        comparison["recommendations"].append(
            f"Processar {comparison['enhanced_extraction']['suspicious_regions']} regiões suspeitas com OCR"
        )
    
    if comparison["improvements"]["processing_overhead"] < 5.0:
        comparison["recommendations"].append("Baixo overhead - usar extração aprimorada por padrão")
    
    if comparison["enhanced_extraction"]["ocr_ready_regions"] == 0:
        comparison["recommendations"].append("Arquivo bem estruturado - extração tradicional suficiente")
    
    return comparison


if __name__ == "__main__":
    # Exemplo de uso
    import sys
    
    if len(sys.argv) > 1:
        cad_file = Path(sys.argv[1])
        
        if cad_file.exists():
            if len(sys.argv) > 2 and sys.argv[2] == "--compare":
                # Modo comparação
                comparison = compare_extraction_methods(cad_file)
                print(f"\n📊 Comparação de Métodos:")
                print(f"Tradicional: {comparison['traditional_extraction']['processing_time']:.2f}s")
                print(f"Aprimorado: {comparison['enhanced_extraction']['processing_time']:.2f}s")
                print(f"Regiões adicionais: {comparison['improvements']['additional_regions_identified']}")
                print(f"Recomendações: {comparison['recommendations']}")
            else:
                # Modo extração aprimorada
                result = enhanced_extract_cad_data(cad_file)
                
                print(f"\n📈 Relatório de Extração:")
                print(f"Entidades vetoriais: {len(result['vector_data']['entities'])}")
                print(f"Regiões suspeitas: {result['gap_analysis']['coverage_data']['suspicious_regions'] if result['gap_analysis']['coverage_data'] else 0}")
                print(f"Regiões renderizadas: {result['ocr_pipeline']['rendered_regions_count']}")
                print(f"Tempo total: {result['extraction_metadata']['metrics']['timing']['total_time']:.2f}s")
        else:
            print(f"Arquivo não encontrado: {cad_file}")
    else:
        print("Uso:")
        print("  python enhanced_data_extraction.py arquivo.dxf")
        print("  python enhanced_data_extraction.py arquivo.dwg --compare")