#!/usr/bin/env python3
"""
Sistema Inteligente de Análise de Projeto CAD
Analisa completamente o projeto carregado e fornece insights contextuais
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from neo4j import GraphDatabase
import openai

@dataclass
class ProjectInsight:
    """Estrutura para insights do projeto"""
    category: str
    title: str
    description: str
    confidence: float
    supporting_data: List[Dict[str, Any]]
    
@dataclass
class ProjectAnalysis:
    """Resultado completo da análise do projeto"""
    project_type: str
    main_purpose: str
    scale: str
    complexity_level: str
    key_elements: List[str]
    insights: List[ProjectInsight]
    statistics: Dict[str, Any]
    summary: str

class IntelligentProjectAnalyzer:
    """Motor de IA para análise inteligente de projetos CAD"""
    
    def __init__(self):
        self.neo4j_driver = self._get_neo4j_driver()
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
    def _get_neo4j_driver(self):
        """Conecta ao Neo4j"""
        uri = os.getenv("NEO4J_URI", "bolt://host.docker.internal:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password123")
        return GraphDatabase.driver(uri, auth=(user, password))
    
    def analyze_complete_project(self) -> ProjectAnalysis:
        """Análise completa e inteligente do projeto"""
        
        print("🧠 [IA] Iniciando análise completa do projeto...")
        
        # 1. Coleta de dados estruturados
        raw_data = self._collect_comprehensive_data()
        
        # 2. Análise com IA contextual
        ai_analysis = self._analyze_with_ai(raw_data)
        
        # 3. Geração de insights
        insights = self._generate_insights(raw_data, ai_analysis)
        
        # 4. Classificação e sumarização
        analysis = self._synthesize_analysis(raw_data, ai_analysis, insights)
        
        print("✅ [IA] Análise completa concluída")
        return analysis
    
    def _collect_comprehensive_data(self) -> Dict[str, Any]:
        """Coleta dados básicos do Neo4j para análise (versão simplificada para estabilidade)"""
        
        with self.neo4j_driver.session() as session:
            data = {}
            
            try:
                # Estatísticas gerais (query básica)
                data['statistics'] = session.run("""
                    MATCH (n) 
                    RETURN labels(n) as type, count(n) as count 
                    ORDER BY count DESC
                """).data()
            except Exception as e:
                print(f"[IA_ERROR] Statistics query failed: {e}")
                data['statistics'] = []
            
            try:
                # Informações do projeto (query simplificada)
                data['project_info'] = session.run("""
                    MATCH (a:Annotation) 
                    WHERE a.text CONTAINS 'ESCALA' OR a.text CONTAINS 'AEROPORTO' OR a.text CONTAINS 'PROJETO'
                    RETURN a.text as info, a.layer as layer
                    LIMIT 10
                """).data()
            except Exception as e:
                print(f"[IA_ERROR] Project info query failed: {e}")
                data['project_info'] = []
            
            try:
                # Elementos técnicos (queries básicas individuais)
                walls_result = session.run("MATCH (w:WallSegment) RETURN count(w) as count").single()
                features_result = session.run("MATCH (f:Feature) RETURN count(f) as count").single()
                blocks_result = session.run("MATCH (b:BlockReference) RETURN count(b) as count").single()
                annotations_result = session.run("MATCH (a:Annotation) RETURN count(a) as count").single()
                
                data['technical_elements'] = {
                    'walls': walls_result['count'] if walls_result else 0,
                    'features': features_result['count'] if features_result else 0,
                    'blocks': blocks_result['count'] if blocks_result else 0,
                    'annotations': annotations_result['count'] if annotations_result else 0
                }
            except Exception as e:
                print(f"[IA_ERROR] Technical elements query failed: {e}")
                data['technical_elements'] = {'walls': 0, 'features': 0, 'blocks': 0, 'annotations': 0}
            
            try:
                # Amostras de anotações (query básica)
                data['annotation_samples'] = session.run("""
                    MATCH (a:Annotation) 
                    WHERE a.text IS NOT NULL AND size(a.text) > 5
                    RETURN a.text as text, a.layer as layer
                    LIMIT 15
                """).data()
            except Exception as e:
                print(f"[IA_ERROR] Annotation samples query failed: {e}")
                data['annotation_samples'] = []
            
        return data
    
    def _analyze_with_ai(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Análise contextual (sempre usa fallback para estabilidade)"""
        
        # Por enquanto, sempre usa análise de fallback para garantir estabilidade
        print("🧠 [IA] Usando análise heurística (OpenAI desabilitado para estabilidade)")
        return self._fallback_analysis(raw_data)
    
    def _prepare_ai_context(self, raw_data: Dict[str, Any]) -> str:
        """Prepara contexto estruturado para a IA"""
        
        context_parts = []
        
        # Estatísticas
        stats = raw_data.get('statistics', [])
        context_parts.append("=== ESTATÍSTICAS DO PROJETO ===")
        for stat in stats:
            context_parts.append(f"- {stat['type']}: {stat['count']} elementos")
        
        # Informações do projeto
        project_info = raw_data.get('project_info', [])
        context_parts.append("\n=== INFORMAÇÕES IDENTIFICADAS ===")
        for info in project_info[:10]:
            context_parts.append(f"- {info['info']} (Layer: {info['layer']})")
        
        # Elementos técnicos
        tech = raw_data.get('technical_elements', {})
        context_parts.append(f"\n=== ELEMENTOS TÉCNICOS ===")
        context_parts.append(f"- Paredes: {tech.get('walls', 0)}")
        context_parts.append(f"- Features: {tech.get('features', 0)}")
        context_parts.append(f"- Blocos: {tech.get('blocks', 0)}")
        context_parts.append(f"- Anotações: {tech.get('annotations', 0)}")
        
        # Layers
        layers = raw_data.get('layer_analysis', [])
        context_parts.append(f"\n=== ORGANIZAÇÃO EM LAYERS ===")
        for layer in layers[:8]:
            context_parts.append(f"- Layer '{layer['layer']}': {layer['elements']} elementos")
        
        # Amostras de texto
        samples = raw_data.get('annotation_samples', [])
        context_parts.append(f"\n=== AMOSTRAS DE TEXTO ===")
        for sample in samples[:15]:
            if len(sample['text']) > 5:
                context_parts.append(f"- \"{sample['text']}\"")
        
        return "\n".join(context_parts)
    
    def _fallback_analysis(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Análise de fallback baseada em heurísticas"""
        
        # Análise heurística simples
        annotations = [item['text'].lower() for item in raw_data.get('annotation_samples', [])]
        project_info = [item['info'].lower() for item in raw_data.get('project_info', [])]
        
        analysis = {
            "project_type": "Desconhecido",
            "main_purpose": "Projeto técnico",
            "confidence": 0.6
        }
        
        # Detecção de tipo por palavras-chave
        text_content = " ".join(annotations + project_info)
        
        if any(term in text_content for term in ['aeroporto', 'airport', 'sbbi']):
            analysis["project_type"] = "Infraestrutura Aeroportuária"
            analysis["confidence"] = 0.9
            
        return analysis
    
    def _generate_insights(self, raw_data: Dict[str, Any], ai_analysis: Dict[str, Any]) -> List[ProjectInsight]:
        """Gera insights específicos baseados na análise"""
        
        insights = []
        
        # Insight sobre escala
        project_info = raw_data.get('project_info', [])
        for info in project_info:
            if '1:' in info['info']:
                insights.append(ProjectInsight(
                    category="Escala",
                    title="Escala do Projeto Identificada",
                    description=f"Projeto desenhado na escala {info['info']}",
                    confidence=0.95,
                    supporting_data=[info]
                ))
                break
        
        # Insight sobre complexidade
        total_elements = sum(item['count'] for item in raw_data.get('statistics', []))
        if total_elements > 1000:
            complexity = "Alta"
            conf = 0.9
        elif total_elements > 300:
            complexity = "Média"
            conf = 0.8
        else:
            complexity = "Baixa"
            conf = 0.7
            
        insights.append(ProjectInsight(
            category="Complexidade",
            title=f"Projeto de Complexidade {complexity}",
            description=f"Com {total_elements} elementos, este é um projeto de complexidade {complexity.lower()}",
            confidence=conf,
            supporting_data=raw_data.get('statistics', [])
        ))
        
        return insights
    
    def _synthesize_analysis(self, raw_data: Dict[str, Any], ai_analysis: Dict[str, Any], insights: List[ProjectInsight]) -> ProjectAnalysis:
        """Sintetiza toda a análise em resultado final"""
        
        # Extrai informações chave
        project_type = ai_analysis.get('project_type', 'Projeto Técnico')
        main_purpose = ai_analysis.get('main_purpose', 'Documentação técnica')
        
        # Busca escala
        scale = "Não identificada"
        for insight in insights:
            if insight.category == "Escala":
                scale = insight.description
                break
        
        # Determina complexidade
        complexity_level = "Média"
        for insight in insights:
            if insight.category == "Complexidade":
                complexity_level = insight.title.split()[-1]
                break
        
        # Elementos chave
        key_elements = []
        for stat in raw_data.get('statistics', []):
            if stat['count'] > 10:
                key_elements.append(f"{stat['count']} {stat['type'][0]}")
        
        # Estatísticas
        statistics = {
            'total_nodes': sum(item['count'] for item in raw_data.get('statistics', [])),
            'node_types': len(raw_data.get('statistics', [])),
            'layers_identified': len(raw_data.get('layer_analysis', [])),
            'annotations_count': raw_data.get('technical_elements', {}).get('annotations', 0)
        }
        
        # Summary inteligente
        summary = self._generate_intelligent_summary(project_type, main_purpose, scale, complexity_level, key_elements, statistics)
        
        return ProjectAnalysis(
            project_type=project_type,
            main_purpose=main_purpose,
            scale=scale,
            complexity_level=complexity_level,
            key_elements=key_elements,
            insights=insights,
            statistics=statistics,
            summary=summary
        )
    
    def _generate_intelligent_summary(self, project_type: str, main_purpose: str, scale: str, complexity: str, elements: List[str], stats: Dict[str, Any]) -> str:
        """Gera resumo inteligente do projeto"""
        
        summary_parts = []
        
        summary_parts.append(f"📋 **{project_type}** - {main_purpose}")
        
        if "1:" in scale:
            summary_parts.append(f"📏 {scale}")
        
        summary_parts.append(f"🔧 Complexidade: {complexity} ({stats['total_nodes']} elementos)")
        
        if elements:
            summary_parts.append(f"🏗️ Elementos principais: {', '.join(elements[:3])}")
        
        if stats['annotations_count'] > 100:
            summary_parts.append(f"📝 Rico em anotações ({stats['annotations_count']} textos)")
        
        return " • ".join(summary_parts)

    def close(self):
        """Fecha conexões"""
        if self.neo4j_driver:
            self.neo4j_driver.close()


# Função de conveniência para uso no query_interface
def analyze_project_intelligently() -> str:
    """Análise inteligente completa do projeto"""
    analyzer = IntelligentProjectAnalyzer()
    try:
        analysis = analyzer.analyze_complete_project()
        
        # Formato de resposta rica
        response_parts = []
        
        response_parts.append(f"# 🎯 {analysis.project_type}")
        response_parts.append(f"**Finalidade:** {analysis.main_purpose}")
        response_parts.append(f"**Escala:** {analysis.scale}")
        response_parts.append(f"**Complexidade:** {analysis.complexity_level}")
        response_parts.append("")
        
        response_parts.append("## 📊 Elementos Identificados")
        for element in analysis.key_elements:
            response_parts.append(f"• {element}")
        response_parts.append("")
        
        response_parts.append("## 🔍 Insights Principais")
        for insight in analysis.insights:
            response_parts.append(f"**{insight.title}** ({insight.confidence:.0%} confiança)")
            response_parts.append(f"• {insight.description}")
        response_parts.append("")
        
        response_parts.append("## 📈 Estatísticas")
        stats = analysis.statistics
        response_parts.append(f"• **Total de elementos:** {stats['total_nodes']}")
        response_parts.append(f"• **Tipos de elementos:** {stats['node_types']}")
        response_parts.append(f"• **Layers organizados:** {stats['layers_identified']}")
        response_parts.append("")
        
        response_parts.append("## 💡 Resumo Executivo")
        response_parts.append(analysis.summary)
        
        return "\n".join(response_parts)
        
    except Exception as e:
        return f"❌ Erro na análise inteligente: {e}"
    finally:
        analyzer.close()


if __name__ == "__main__":
    # Teste do sistema
    result = analyze_project_intelligently()
    print(result)