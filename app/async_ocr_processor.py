"""
Async OCR Processor - Processamento assíncrono para pipeline OCR

Este módulo implementa processamento assíncrono usando Celery para operações OCR
demoradas, permitindo que o endpoint retorne rapidamente enquanto o OCR é processado
em background.
"""

import asyncio
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
import threading
from queue import Queue, Empty
from enum import Enum

from enhanced_data_extraction import EnhancedCADExtractor
# Lazy import para evitar carregamento desnecessário do OpenCV
# from contextual_ocr_processor import ContextualOCRProcessor
from cross_validator import cross_validate_cad_ocr
from ocr_quality_dashboard import analyze_ocr_quality
from graph_loader import enhance_graph_with_ocr


class JobStatus(Enum):
    """Status do job de processamento OCR."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OCRJob:
    """Representa um job de processamento OCR."""
    
    def __init__(self, job_id: str, file_path: Path, options: Dict[str, Any]):
        self.job_id = job_id
        self.file_path = file_path
        self.options = options
        self.status = JobStatus.PENDING
        self.progress = 0.0
        self.current_stage = "Iniciando"
        self.result = None
        self.error = None
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self.metrics = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte job para dicionário."""
        return {
            "job_id": self.job_id,
            "file_path": str(self.file_path),
            "status": self.status.value,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "processing_time": (self.completed_at - self.started_at) if self.completed_at else None,
            "metrics": self.metrics,
            "error": str(self.error) if self.error else None
        }


class AsyncOCRProcessor:
    """
    Processador assíncrono para OCR.
    
    Usa ThreadPoolExecutor para processar OCR em threads separadas,
    mantendo o servidor responsivo.
    """
    
    def __init__(self, max_workers: int = 2):
        """
        Inicializa o processador assíncrono.
        
        Args:
            max_workers: Número máximo de workers paralelos
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs: Dict[str, OCRJob] = {}
        self.job_queue = Queue()
        self.job_counter = 0
        self.lock = threading.Lock()
        
        # Iniciar workers
        self.workers = []
        for i in range(max_workers):
            worker = threading.Thread(target=self._worker_loop, name=f"OCR-Worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        print(f"🚀 AsyncOCRProcessor iniciado com {max_workers} workers")
    
    def submit_job(self, file_path: Path, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Submete um job de OCR para processamento assíncrono.
        
        Args:
            file_path: Arquivo CAD para processar
            options: Opções de processamento
            
        Returns:
            ID do job
        """
        with self.lock:
            self.job_counter += 1
            job_id = f"ocr_job_{self.job_counter:06d}"
        
        job = OCRJob(job_id, file_path, options or {})
        
        with self.lock:
            self.jobs[job_id] = job
        
        self.job_queue.put(job)
        
        print(f"📋 Job OCR submetido: {job_id} para {file_path.name}")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retorna status de um job.
        
        Args:
            job_id: ID do job
            
        Returns:
            Status do job ou None se não encontrado
        """
        with self.lock:
            job = self.jobs.get(job_id)
        
        if not job:
            return None
        
        return job.to_dict()
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Retorna status de todos os jobs."""
        with self.lock:
            return [job.to_dict() for job in self.jobs.values()]
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancela um job (se ainda não iniciado).
        
        Args:
            job_id: ID do job
            
        Returns:
            True se cancelado, False caso contrário
        """
        with self.lock:
            job = self.jobs.get(job_id)
            
            if job and job.status == JobStatus.PENDING:
                job.status = JobStatus.CANCELLED
                job.completed_at = time.time()
                return True
        
        return False
    
    def _worker_loop(self):
        """Loop principal do worker."""
        while True:
            try:
                # Pegar próximo job da fila (timeout para permitir shutdown)
                job = self.job_queue.get(timeout=1.0)
                
                # Verificar se foi cancelado
                if job.status == JobStatus.CANCELLED:
                    continue
                
                # Processar job
                self._process_job(job)
                
            except Empty:
                # Fila vazia, continuar
                continue
            except Exception as e:
                print(f"❌ Erro no worker: {str(e)}")
    
    def _process_job(self, job: OCRJob):
        """Processa um job OCR."""
        print(f"🔄 Processando job: {job.job_id}")
        
        job.status = JobStatus.PROCESSING
        job.started_at = time.time()
        
        try:
            # Estágio 1: Extração aprimorada
            job.current_stage = "Extração CAD aprimorada"
            job.progress = 0.1
            
            extractor = EnhancedCADExtractor(enable_ocr=True)
            enhanced_result = extractor.extract_enhanced_cad_data(job.file_path)
            
            job.progress = 0.3
            job.metrics["extraction_time"] = time.time() - job.started_at
            job.metrics["regions_found"] = enhanced_result["ocr_pipeline"]["rendered_regions_count"]
            
            # Verificar se há regiões para OCR
            if not enhanced_result["ocr_pipeline"]["ready_for_ocr"]:
                job.current_stage = "Concluído - Sem regiões para OCR"
                job.progress = 1.0
                job.status = JobStatus.COMPLETED
                job.completed_at = time.time()
                job.result = {
                    "message": "Nenhuma região suspeita encontrada para OCR",
                    "enhanced_result": enhanced_result
                }
                return
            
            # Estágio 2: Processamento OCR
            job.current_stage = "Processamento OCR"
            job.progress = 0.4
            
            ocr_start = time.time()
            
            # Obter regiões prontas para OCR
            ocr_ready_regions = extractor.get_ocr_ready_regions()
            
            # Processar com OCR contextual
            # Lazy import apenas quando necessário
            from contextual_ocr_processor import ContextualOCRProcessor
            ocr_processor = ContextualOCRProcessor(use_gpu=job.options.get("use_gpu", False))
            ocr_results = []
            
            for i, (region_id, rendered_region) in enumerate(ocr_ready_regions):
                # Atualizar progresso
                job.progress = 0.4 + (0.3 * (i / max(1, len(ocr_ready_regions))))
                job.current_stage = f"OCR região {i+1}/{len(ocr_ready_regions)}"
                
                # Criar contexto CAD
                cad_context = extractor.create_cad_contexts(
                    enhanced_result["vector_data"]["drawing_bounds"],
                    {"file": job.file_path.name}
                ).get(region_id)
                
                # Processar região
                result = ocr_processor.process_region(rendered_region, cad_context)
                if result:
                    ocr_results.append(result)
            
            job.metrics["ocr_time"] = time.time() - ocr_start
            job.metrics["ocr_results"] = len(ocr_results)
            job.progress = 0.7
            
            # Estágio 3: Validação cruzada
            job.current_stage = "Validação CAD-OCR"
            
            validation_start = time.time()
            validation_report = cross_validate_cad_ocr(
                ocr_results,
                enhanced_result["vector_data"]["entities"],
                [rr for _, rr in ocr_ready_regions]
            )
            
            job.metrics["validation_time"] = time.time() - validation_start
            job.metrics["validations"] = len(validation_report.exact_matches)
            job.metrics["discoveries"] = len(validation_report.discoveries)
            job.progress = 0.85
            
            # Estágio 4: Análise de qualidade
            job.current_stage = "Análise de qualidade"
            
            quality_report = analyze_ocr_quality(
                ocr_results,
                validation_report,
                [rr for _, rr in ocr_ready_regions],
                time.time() - job.started_at,
                {"name": job.file_path.name, "size_mb": job.file_path.stat().st_size / (1024*1024)}
            )
            
            job.metrics["health_score"] = quality_report.health_score
            job.progress = 0.95
            
            # Estágio 5: Preparar dados para Neo4j
            job.current_stage = "Preparando enriquecimento"
            
            from cross_validator import CADOCRCrossValidator
            validator = CADOCRCrossValidator()
            enrichment_data = validator.get_neo4j_enrichment_data(validation_report)
            
            # Resultado final
            job.result = {
                "success": True,
                "message": f"OCR concluído com sucesso",
                "summary": {
                    "regions_processed": len(ocr_ready_regions),
                    "ocr_results": len(ocr_results),
                    "validations": len(validation_report.exact_matches),
                    "discoveries": len(validation_report.discoveries),
                    "conflicts": len(validation_report.conflicts),
                    "health_score": quality_report.health_score,
                    "processing_time": time.time() - job.started_at
                },
                "enrichment_data": enrichment_data,
                "quality_report": asdict(quality_report)
            }
            
            job.status = JobStatus.COMPLETED
            job.progress = 1.0
            job.current_stage = "Concluído"
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = e
            job.current_stage = f"Erro: {str(e)}"
            print(f"❌ Erro no job {job.job_id}: {str(e)}")
            
        finally:
            job.completed_at = time.time()
            
            # Salvar resultado em arquivo
            self._save_job_result(job)
    
    def _save_job_result(self, job: OCRJob):
        """Salva resultado do job em arquivo."""
        results_dir = Path("ocr_results")
        results_dir.mkdir(exist_ok=True)
        
        result_file = results_dir / f"{job.job_id}_result.json"
        
        result_data = {
            **job.to_dict(),
            "result": job.result if job.status == JobStatus.COMPLETED else None
        }
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"💾 Resultado salvo: {result_file}")
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs antigos."""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        with self.lock:
            old_jobs = [
                job_id for job_id, job in self.jobs.items()
                if (current_time - job.created_at) > max_age_seconds
            ]
            
            for job_id in old_jobs:
                del self.jobs[job_id]
        
        if old_jobs:
            print(f"🧹 Removidos {len(old_jobs)} jobs antigos")
    
    def shutdown(self):
        """Desliga o processador."""
        self.executor.shutdown(wait=True)
        print("🛑 AsyncOCRProcessor desligado")


# Instância global do processador
_async_processor: Optional[AsyncOCRProcessor] = None


def get_async_processor() -> AsyncOCRProcessor:
    """Retorna instância global do processador assíncrono."""
    global _async_processor
    
    if _async_processor is None:
        max_workers = int(os.getenv("OCR_MAX_WORKERS", "2"))
        _async_processor = AsyncOCRProcessor(max_workers=max_workers)
    
    return _async_processor


# FastAPI integration endpoints
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

async_ocr_router = APIRouter(prefix="/api/ocr", tags=["OCR Async"])


class OCRJobRequest(BaseModel):
    file_path: str
    use_gpu: bool = False
    priority: str = "normal"


class OCRJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


@async_ocr_router.post("/submit", response_model=OCRJobResponse)
async def submit_ocr_job(request: OCRJobRequest):
    """Submete arquivo para processamento OCR assíncrono."""
    
    file_path = Path(request.file_path)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    processor = get_async_processor()
    
    job_id = processor.submit_job(
        file_path,
        {"use_gpu": request.use_gpu, "priority": request.priority}
    )
    
    return OCRJobResponse(
        job_id=job_id,
        status="submitted",
        message="Job OCR submetido para processamento"
    )


@async_ocr_router.get("/status/{job_id}")
async def get_ocr_job_status(job_id: str):
    """Retorna status de um job OCR."""
    
    processor = get_async_processor()
    status = processor.get_job_status(job_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    
    return status


@async_ocr_router.get("/jobs")
async def list_ocr_jobs():
    """Lista todos os jobs OCR."""
    
    processor = get_async_processor()
    return {"jobs": processor.get_all_jobs()}


@async_ocr_router.delete("/cancel/{job_id}")
async def cancel_ocr_job(job_id: str):
    """Cancela um job OCR pendente."""
    
    processor = get_async_processor()
    
    if processor.cancel_job(job_id):
        return {"message": f"Job {job_id} cancelado"}
    else:
        raise HTTPException(status_code=400, detail="Job não pode ser cancelado")


if __name__ == "__main__":
    # Teste do processador assíncrono
    import os
    os.environ.setdefault("OCR_MAX_WORKERS", "2")
    
    print("🧪 Testando processador OCR assíncrono")
    
    processor = get_async_processor()
    
    # Simular job
    test_file = Path("test-files/synthetic_test_drawing.dxf")
    if test_file.exists():
        job_id = processor.submit_job(test_file)
        print(f"✅ Job submetido: {job_id}")
        
        # Aguardar um pouco
        time.sleep(2)
        
        # Verificar status
        status = processor.get_job_status(job_id)
        print(f"📊 Status: {status}")
    else:
        print("⚠️ Arquivo de teste não encontrado")
    
    # Cleanup
    processor.cleanup_old_jobs(max_age_hours=0.001)
    
    print("\n✅ Processador assíncrono funcionando!")