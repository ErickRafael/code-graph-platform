"""
OCR Structures - Estruturas de dados para pipeline OCR inteligente

Define todas as classes, enums e estruturas de dados necessárias para o sistema OCR,
incluindo ROI management, contexto CAD, resultados OCR e métricas de qualidade.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from pathlib import Path
import json
from PIL import Image

from gap_analyzer import Region, RegionType


class OCREngine(Enum):
    """Motores OCR disponíveis."""
    MISTRAL = "mistral"
    TESSERACT = "tesseract"
    NONE = "none"
    UNKNOWN = "unknown"


class ProcessingStage(Enum):
    """Estágios do pipeline OCR."""
    ANALYSIS = "analysis"
    RENDERING = "rendering"
    PREPROCESSING = "preprocessing"
    OCR_EXTRACTION = "ocr_extraction"
    VALIDATION = "validation"
    ENRICHMENT = "enrichment"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(Enum):
    """Níveis de confiança para resultados OCR."""
    VERY_HIGH = "very_high"  # 0.9+
    HIGH = "high"           # 0.7-0.9
    MEDIUM = "medium"       # 0.5-0.7
    LOW = "low"            # 0.3-0.5
    VERY_LOW = "very_low"  # <0.3


@dataclass
class BoundingBox:
    """Representa uma caixa delimitadora em coordenadas de imagem."""
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    confidence: float = 1.0
    
    @property
    def width(self) -> int:
        return self.x_max - self.x_min
    
    @property
    def height(self) -> int:
        return self.y_max - self.y_min
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    @property
    def center(self) -> Tuple[int, int]:
        return ((self.x_min + self.x_max) // 2, (self.y_min + self.y_max) // 2)
    
    def overlaps_with(self, other: 'BoundingBox') -> bool:
        """Verifica se esta bbox sobrepõe com outra."""
        return not (self.x_max < other.x_min or other.x_max < self.x_min or
                   self.y_max < other.y_min or other.y_max < self.y_min)
    
    def intersection_area(self, other: 'BoundingBox') -> int:
        """Calcula área de interseção com outra bbox."""
        if not self.overlaps_with(other):
            return 0
        
        x_min = max(self.x_min, other.x_min)
        y_min = max(self.y_min, other.y_min)
        x_max = min(self.x_max, other.x_max)
        y_max = min(self.y_max, other.y_max)
        
        return (x_max - x_min) * (y_max - y_min)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max,
            "confidence": self.confidence,
            "width": self.width,
            "height": self.height,
            "area": self.area,
            "center": self.center
        }


@dataclass
class CADCoordinate:
    """Representa uma coordenada no sistema CAD."""
    x: float
    y: float
    z: float = 0.0
    
    def distance_to(self, other: 'CADCoordinate') -> float:
        """Calcula distância euclidiana para outro ponto."""
        import math
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx*dx + dy*dy + dz*dz)
    
    def to_dict(self) -> Dict[str, float]:
        """Converte para dicionário."""
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass
class OCRWord:
    """Representa uma palavra extraída via OCR."""
    text: str
    confidence: float
    bbox: Union[BoundingBox, Dict[str, Any]]
    font_size: Optional[float] = None
    is_numeric: bool = field(init=False)
    is_dimension: bool = field(init=False)
    
    def __post_init__(self):
        """Análise automática após inicialização."""
        self.is_numeric = self._is_numeric_text()
        self.is_dimension = self._is_dimension_text()
    
    def _is_numeric_text(self) -> bool:
        """Verifica se o texto é numérico/dimensional."""
        import re
        # Padrões comuns para dimensões
        numeric_patterns = [
            r'^\d+\.?\d*$',  # 123, 123.45
            r'^\d+\.?\d*\s*mm$',  # 123mm, 123.45 mm
            r'^\d+\.?\d*\s*cm$',  # 123cm
            r'^\d+\.?\d*\s*m$',   # 123m
            r'^\d+\.?\d*\s*"$',   # 123"
            r'^\d+\'\s*\d*\.?\d*"?$',  # 12'6", 12'
        ]
        
        clean_text = self.text.strip()
        return any(re.match(pattern, clean_text, re.IGNORECASE) for pattern in numeric_patterns)
    
    def _is_dimension_text(self) -> bool:
        """Verifica se parece texto dimensional."""
        if self.is_numeric:
            return True
        
        # Padrões de dimensão mais complexos
        import re
        dimension_patterns = [
            r'R\d+\.?\d*',  # R123, R12.5 (raios)
            r'Ø\d+\.?\d*',  # Ø123 (diâmetros)
            r'\d+\.?\d*\s*X\s*\d+\.?\d*',  # 123 X 456
            r'\d+\.?\d*\s*x\s*\d+\.?\d*',  # 123 x 456
        ]
        
        clean_text = self.text.strip()
        return any(re.match(pattern, clean_text, re.IGNORECASE) for pattern in dimension_patterns)
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Retorna nível de confiança categórico."""
        if self.confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif self.confidence >= 0.7:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif self.confidence >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        bbox_dict = self.bbox.to_dict() if hasattr(self.bbox, 'to_dict') else self.bbox
        return {
            "text": self.text,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "bbox": bbox_dict,
            "font_size": self.font_size,
            "is_numeric": self.is_numeric,
            "is_dimension": self.is_dimension
        }


@dataclass
class OCRResult:
    """Resultado completo de extração OCR de uma região."""
    region_id: str
    engine: OCREngine
    full_text: str
    words: List[OCRWord]
    processing_time: float
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def word_count(self) -> int:
        """Número de palavras extraídas."""
        return len(self.words)
    
    @property
    def high_confidence_words(self) -> List[OCRWord]:
        """Palavras com alta confiança (>0.7)."""
        return [w for w in self.words if w.confidence > 0.7]
    
    @property
    def dimension_words(self) -> List[OCRWord]:
        """Palavras que parecem dimensões."""
        return [w for w in self.words if w.is_dimension]
    
    @property
    def average_confidence(self) -> float:
        """Confiança média das palavras."""
        if not self.words:
            return 0.0
        return sum(w.confidence for w in self.words) / len(self.words)
    
    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Nível de confiança geral do resultado."""
        if self.confidence_score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif self.confidence_score >= 0.7:
            return ConfidenceLevel.HIGH
        elif self.confidence_score >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif self.confidence_score >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "region_id": self.region_id,
            "engine": self.engine.value,
            "full_text": self.full_text,
            "words": [w.to_dict() for w in self.words],
            "word_count": self.word_count,
            "processing_time": self.processing_time,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level.value,
            "average_confidence": self.average_confidence,
            "high_confidence_count": len(self.high_confidence_words),
            "dimension_count": len(self.dimension_words),
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class RenderedRegion:
    """Representa uma região renderizada como imagem para OCR."""
    region: Region
    image_path: Path
    image_size: Tuple[int, int]
    scale_factor: float
    actual_bounds: Dict[str, float]
    rendering_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def image_area(self) -> int:
        """Área da imagem em pixels."""
        return self.image_size[0] * self.image_size[1]
    
    @property
    def pixels_per_unit(self) -> float:
        """Pixels por unidade CAD."""
        region_width = self.actual_bounds['x_max'] - self.actual_bounds['x_min']
        if region_width > 0:
            return self.image_size[0] / region_width
        return 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "region": {
                "bounds": self.region.bounds,
                "region_type": self.region.region_type.value,
                "priority": self.region.priority,
                "confidence": self.region.confidence
            },
            "image_path": str(self.image_path),
            "image_size": self.image_size,
            "image_area": self.image_area,
            "scale_factor": self.scale_factor,
            "actual_bounds": self.actual_bounds,
            "pixels_per_unit": self.pixels_per_unit,
            "rendering_time": self.rendering_time,
            "metadata": self.metadata
        }


@dataclass
class CADContext:
    """Contexto CAD para processamento OCR inteligente."""
    region_type: RegionType
    nearby_entities: List[Dict[str, Any]]
    drawing_bounds: Dict[str, float]
    scale_info: Optional[Dict[str, Any]] = None
    layer_info: Optional[Dict[str, Any]] = None
    project_info: Optional[Dict[str, Any]] = None
    
    @property
    def expected_patterns(self) -> List[str]:
        """Padrões esperados baseados no contexto."""
        patterns = []
        
        if self.region_type == RegionType.TITLE_BLOCK:
            patterns.extend([
                r'[A-Z]{2,}\d+-[A-Z]{2,}',  # Códigos de projeto
                r'ESC\:?\s*1:\d+',  # Escalas
                r'\d{2}/\d{2}/\d{4}',  # Datas
                r'REV\:?\s*\w+',  # Revisões
            ])
        elif self.region_type == RegionType.DIMENSION:
            patterns.extend([
                r'\d+\.?\d*',  # Números
                r'R\d+\.?\d*',  # Raios
                r'Ø\d+\.?\d*',  # Diâmetros
            ])
        elif self.region_type == RegionType.LEGEND:
            patterns.extend([
                r'[A-Z]+\s*-\s*.+',  # Itens de legenda
                r'COR\:?\s*.+',  # Cores
            ])
        
        return patterns
    
    @property
    def contextual_prompt(self) -> str:
        """Prompt contextual para OCR baseado no tipo de região."""
        prompts = {
            RegionType.TITLE_BLOCK: (
                "Extract project information, drawing numbers, scales, dates, "
                "and revision information from this technical drawing title block. "
                "Focus on alphanumeric codes, scales (1:X format), and dates."
            ),
            RegionType.DIMENSION: (
                "Extract dimension values, measurements, and numerical annotations "
                "from this technical drawing. Look for numbers, units (mm, cm, m), "
                "radii (R), diameters (Ø), and dimensional tolerances."
            ),
            RegionType.LEGEND: (
                "Extract legend items, color codes, line types, and symbol "
                "descriptions from this technical drawing legend. "
                "Focus on descriptions and their associated symbols."
            ),
            RegionType.ANNOTATION: (
                "Extract technical annotations, notes, and text labels "
                "from this technical drawing region."
            ),
            RegionType.SUSPICIOUS_VOID: (
                "Extract any text that might be embedded or rasterized "
                "in this region of the technical drawing."
            ),
            RegionType.BORDER_AREA: (
                "Extract border annotations, drawing frame information, "
                "and edge notes from this technical drawing."
            )
        }
        
        return prompts.get(self.region_type, "Extract all text from this technical drawing region.")
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "region_type": self.region_type.value,
            "nearby_entities_count": len(self.nearby_entities),
            "drawing_bounds": self.drawing_bounds,
            "scale_info": self.scale_info,
            "layer_info": self.layer_info,
            "project_info": self.project_info,
            "expected_patterns": self.expected_patterns,
            "contextual_prompt": self.contextual_prompt
        }


@dataclass
class CorrelationResult:
    """Resultado de correlação entre dados OCR e CAD."""
    ocr_word: OCRWord
    cad_entity: Optional[Dict[str, Any]]
    correlation_type: str  # 'exact_match', 'spatial_proximity', 'semantic_similarity', 'no_correlation'
    confidence: float
    distance: Optional[float] = None  # Distância espacial se aplicável
    notes: List[str] = field(default_factory=list)
    
    @property
    def is_correlated(self) -> bool:
        """Verifica se há correlação válida."""
        return self.correlation_type != 'no_correlation' and self.confidence > 0.3
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "ocr_word": self.ocr_word.to_dict(),
            "cad_entity": self.cad_entity,
            "correlation_type": self.correlation_type,
            "confidence": self.confidence,
            "distance": self.distance,
            "is_correlated": self.is_correlated,
            "notes": self.notes
        }


@dataclass
class ValidationResult:
    """Resultado de validação cruzada CAD-OCR."""
    region_id: str
    correlations: List[CorrelationResult]
    ocr_only_words: List[OCRWord]  # Palavras só no OCR
    cad_only_entities: List[Dict[str, Any]]  # Entidades só no CAD
    quality_score: float
    validation_notes: List[str] = field(default_factory=list)
    
    @property
    def correlation_rate(self) -> float:
        """Taxa de correlação (palavras correlacionadas / total OCR)."""
        if not self.correlations:
            return 0.0
        correlated = sum(1 for c in self.correlations if c.is_correlated)
        return correlated / len(self.correlations)
    
    @property
    def discovery_count(self) -> int:
        """Número de descobertas (OCR only)."""
        return len(self.ocr_only_words)
    
    @property
    def high_confidence_discoveries(self) -> List[OCRWord]:
        """Descobertas com alta confiança."""
        return [w for w in self.ocr_only_words if w.confidence > 0.7]
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "region_id": self.region_id,
            "correlations": [c.to_dict() for c in self.correlations],
            "ocr_only_words": [w.to_dict() for w in self.ocr_only_words],
            "cad_only_entities_count": len(self.cad_only_entities),
            "correlation_rate": self.correlation_rate,
            "discovery_count": self.discovery_count,
            "high_confidence_discoveries": len(self.high_confidence_discoveries),
            "quality_score": self.quality_score,
            "validation_notes": self.validation_notes
        }


@dataclass
class ROIManager:
    """Gerenciador de Regiões de Interesse para processamento OCR."""
    regions: List[Region] = field(default_factory=list)
    rendered_regions: Dict[str, Any] = field(default_factory=dict)  # region_id -> RenderedRegion
    ocr_results: Dict[str, OCRResult] = field(default_factory=dict)  # region_id -> OCRResult
    validation_results: Dict[str, ValidationResult] = field(default_factory=dict)
    processing_stages: Dict[str, ProcessingStage] = field(default_factory=dict)
    
    def add_region(self, region: Region) -> str:
        """
        Adiciona uma região ao gerenciador.
        
        Returns:
            ID único da região
        """
        region_id = f"{region.region_type.value}_{len(self.regions):03d}"
        self.regions.append(region)
        self.processing_stages[region_id] = ProcessingStage.ANALYSIS
        return region_id
    
    def get_region_by_id(self, region_id: str) -> Optional[Region]:
        """Busca região por ID."""
        try:
            index = int(region_id.split('_')[-1])
            return self.regions[index] if index < len(self.regions) else None
        except (ValueError, IndexError):
            return None
    
    def get_regions_by_type(self, region_type: RegionType) -> List[Tuple[str, Region]]:
        """Busca regiões por tipo."""
        result = []
        for i, region in enumerate(self.regions):
            if region.region_type == region_type:
                region_id = f"{region.region_type.value}_{i:03d}"
                result.append((region_id, region))
        return result
    
    def get_regions_by_priority(self, min_priority: float = 0.5) -> List[Tuple[str, Region]]:
        """Busca regiões por prioridade mínima."""
        result = []
        for i, region in enumerate(self.regions):
            if region.priority >= min_priority:
                region_id = f"{region.region_type.value}_{i:03d}"
                result.append((region_id, region))
        return sorted(result, key=lambda x: x[1].priority, reverse=True)
    
    def update_stage(self, region_id: str, stage: ProcessingStage):
        """Atualiza estágio de processamento de uma região."""
        self.processing_stages[region_id] = stage
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """Retorna resumo do processamento."""
        stages_count = {}
        for stage in ProcessingStage:
            stages_count[stage.value] = sum(1 for s in self.processing_stages.values() if s == stage)
        
        total_regions = len(self.regions)
        completed_ocr = len(self.ocr_results)
        completed_validation = len(self.validation_results)
        
        return {
            "total_regions": total_regions,
            "completed_ocr": completed_ocr,
            "completed_validation": completed_validation,
            "completion_rate": completed_ocr / max(1, total_regions),
            "validation_rate": completed_validation / max(1, total_regions),
            "stages_distribution": stages_count
        }
    
    def get_quality_metrics(self) -> Dict[str, Any]:
        """Calcula métricas de qualidade geral."""
        if not self.ocr_results:
            return {"status": "no_results"}
        
        # Métricas de OCR
        total_confidence = sum(r.confidence_score for r in self.ocr_results.values())
        avg_confidence = total_confidence / len(self.ocr_results)
        
        total_words = sum(len(r.words) for r in self.ocr_results.values())
        high_conf_words = sum(len(r.high_confidence_words) for r in self.ocr_results.values())
        dimension_words = sum(len(r.dimension_words) for r in self.ocr_results.values())
        
        # Métricas de validação
        validation_metrics = {}
        if self.validation_results:
            total_quality = sum(v.quality_score for v in self.validation_results.values())
            avg_quality = total_quality / len(self.validation_results)
            
            total_discoveries = sum(v.discovery_count for v in self.validation_results.values())
            total_correlations = sum(v.correlation_rate for v in self.validation_results.values())
            avg_correlation = total_correlations / len(self.validation_results)
            
            validation_metrics = {
                "average_quality_score": avg_quality,
                "total_discoveries": total_discoveries,
                "average_correlation_rate": avg_correlation
            }
        
        return {
            "ocr_metrics": {
                "average_confidence": avg_confidence,
                "total_words_extracted": total_words,
                "high_confidence_words": high_conf_words,
                "dimension_words_found": dimension_words,
                "high_confidence_rate": high_conf_words / max(1, total_words)
            },
            "validation_metrics": validation_metrics,
            "regions_processed": len(self.ocr_results),
            "total_processing_time": sum(r.processing_time for r in self.ocr_results.values())
        }
    
    def export_results(self, output_path: Path) -> Path:
        """
        Exporta todos os resultados para arquivo JSON.
        
        Args:
            output_path: Caminho do arquivo de saída
            
        Returns:
            Caminho do arquivo criado
        """
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "summary": self.get_processing_summary(),
            "quality_metrics": self.get_quality_metrics(),
            "regions": [
                {
                    "id": f"{r.region_type.value}_{i:03d}",
                    "region_data": {
                        "bounds": r.bounds,
                        "region_type": r.region_type.value,
                        "priority": r.priority,
                        "confidence": r.confidence,
                        "context": r.context
                    }
                }
                for i, r in enumerate(self.regions)
            ],
            "ocr_results": {
                region_id: result.to_dict() 
                for region_id, result in self.ocr_results.items()
            },
            "validation_results": {
                region_id: result.to_dict() 
                for region_id, result in self.validation_results.items()
            },
            "processing_stages": {
                region_id: stage.value 
                for region_id, stage in self.processing_stages.items()
            }
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def __len__(self) -> int:
        """Número de regiões gerenciadas."""
        return len(self.regions)


# Funções utilitárias

def create_cad_context(region: Region, drawing_bounds: Dict[str, float],
                      project_info: Optional[Dict[str, Any]] = None) -> CADContext:
    """
    Cria contexto CAD para uma região.
    
    Args:
        region: Região de interesse
        drawing_bounds: Bounds do desenho
        project_info: Informações do projeto (opcional)
        
    Returns:
        Contexto CAD configurado
    """
    return CADContext(
        region_type=region.region_type,
        nearby_entities=region.nearby_entities,
        drawing_bounds=drawing_bounds,
        project_info=project_info
    )


def merge_ocr_results(results: List[OCRResult]) -> OCRResult:
    """
    Combina múltiplos resultados OCR em um resultado consolidado.
    
    Args:
        results: Lista de resultados OCR
        
    Returns:
        Resultado OCR consolidado
    """
    if not results:
        raise ValueError("Nenhum resultado para combinar")
    
    if len(results) == 1:
        return results[0]
    
    # Combinar textos
    full_text = " ".join(r.full_text for r in results if r.full_text.strip())
    
    # Combinar palavras
    all_words = []
    for result in results:
        all_words.extend(result.words)
    
    # Calcular métricas consolidadas
    total_time = sum(r.processing_time for r in results)
    avg_confidence = sum(r.confidence_score for r in results) / len(results)
    
    # Combinar metadados
    combined_metadata = {
        "source_results_count": len(results),
        "engines_used": list(set(r.engine.value for r in results)),
        "combined_timestamp": datetime.now().isoformat()
    }
    
    return OCRResult(
        region_id=f"combined_{results[0].region_id}",
        engine=OCREngine.UNKNOWN,  # Múltiplos engines
        full_text=full_text,
        words=all_words,
        processing_time=total_time,
        confidence_score=avg_confidence,
        metadata=combined_metadata
    )


if __name__ == "__main__":
    # Exemplo de uso das estruturas
    from gap_analyzer import Region, RegionType
    
    # Criar região de exemplo
    example_region = Region(
        bounds={"x_min": 0, "y_min": 0, "x_max": 100, "y_max": 50},
        region_type=RegionType.TITLE_BLOCK,
        priority=0.9,
        confidence=0.8,
        context={"test": True},
        nearby_entities=[]
    )
    
    # Criar gerenciador ROI
    roi_manager = ROIManager()
    region_id = roi_manager.add_region(example_region)
    
    # Criar palavra OCR de exemplo
    bbox = BoundingBox(10, 10, 100, 30, confidence=0.9)
    word = OCRWord("ECB1-EST-001", confidence=0.85, bbox=bbox)
    
    # Criar resultado OCR
    ocr_result = OCRResult(
        region_id=region_id,
        engine=OCREngine.MISTRAL,
        full_text="ECB1-EST-001 TITLE BLOCK",
        words=[word],
        processing_time=1.5,
        confidence_score=0.85
    )
    
    roi_manager.ocr_results[region_id] = ocr_result
    roi_manager.update_stage(region_id, ProcessingStage.COMPLETED)
    
    # Mostrar métricas
    print("📊 Estruturas OCR - Exemplo de Uso")
    print(f"✅ Regiões: {len(roi_manager)}")
    print(f"📈 Qualidade: {roi_manager.get_quality_metrics()}")
    print(f"🎯 Resumo: {roi_manager.get_processing_summary()}")
    print(f"🔤 Palavra: {word.text} ({word.confidence_level.value})")
    print(f"📦 Dimensão? {word.is_dimension}")