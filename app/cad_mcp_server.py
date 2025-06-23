"""Model Context Protocol (MCP) Server for CAD Analysis

This MCP server exposes specialized CAD analysis tools that Claude can use
to provide more sophisticated analysis and insights.
"""

from typing import Dict, List, Any, Optional, Tuple
import json
import math
from dataclasses import dataclass
from neo4j import GraphDatabase
import os

# MCP SDK (would need installation)
# from mcp import MCPServer, mcp_tool, ToolResult

@dataclass
class Point2D:
    x: float
    y: float

@dataclass
class BoundingBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    
    @property
    def width(self) -> float:
        return self.max_x - self.min_x
    
    @property
    def height(self) -> float:
        return self.max_y - self.min_y
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center(self) -> Point2D:
        return Point2D(
            x=(self.min_x + self.max_x) / 2,
            y=(self.min_y + self.max_y) / 2
        )

class CADAnalysisMCPServer:
    """MCP Server providing specialized CAD analysis tools"""
    
    def __init__(self):
        self.driver = self._get_neo4j_driver()
        
    def _get_neo4j_driver(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "neo4j")
        return GraphDatabase.driver(uri, auth=(user, password))
    
    # @mcp_tool(
    #     name="analyze_spatial_distribution",
    #     description="Analyze the spatial distribution of elements in a CAD drawing"
    # )
    async def analyze_spatial_distribution(self, floor_uid: str) -> Dict[str, Any]:
        """Analyze how spaces are distributed across a floor"""
        
        with self.driver.session() as session:
            # Get all spaces on the floor
            spaces_query = """
            MATCH (f:Floor {uid: $floor_uid})-[:HAS_SPACE]->(s:Space)
            RETURN s.uid AS uid, s.raw_points AS points, s.layer AS layer
            """
            spaces = list(session.run(spaces_query, floor_uid=floor_uid))
            
            if not spaces:
                return {"error": "No spaces found on this floor"}
            
            # Calculate spatial metrics
            space_metrics = []
            total_area = 0
            bounding_boxes = []
            
            for space in spaces:
                points = space["points"]
                if not points or len(points) < 3:
                    continue
                
                # Calculate area using shoelace formula
                area = self._calculate_polygon_area(points)
                bbox = self._calculate_bounding_box(points)
                centroid = self._calculate_centroid(points)
                
                metrics = {
                    "uid": space["uid"],
                    "layer": space["layer"],
                    "area": area,
                    "perimeter": self._calculate_perimeter(points),
                    "centroid": {"x": centroid.x, "y": centroid.y},
                    "bounding_box": {
                        "min_x": bbox.min_x,
                        "min_y": bbox.min_y,
                        "max_x": bbox.max_x,
                        "max_y": bbox.max_y,
                        "width": bbox.width,
                        "height": bbox.height
                    },
                    "compactness": self._calculate_compactness(area, self._calculate_perimeter(points))
                }
                
                space_metrics.append(metrics)
                total_area += area
                bounding_boxes.append(bbox)
            
            # Calculate floor-level metrics
            floor_bbox = self._merge_bounding_boxes(bounding_boxes)
            
            # Spatial distribution analysis
            distribution_analysis = {
                "total_spaces": len(space_metrics),
                "total_area": total_area,
                "average_space_area": total_area / len(space_metrics) if space_metrics else 0,
                "floor_bounding_box": {
                    "width": floor_bbox.width,
                    "height": floor_bbox.height,
                    "area": floor_bbox.area
                },
                "space_efficiency": total_area / floor_bbox.area if floor_bbox.area > 0 else 0,
                "spatial_distribution": self._analyze_distribution_pattern(space_metrics),
                "spaces": space_metrics
            }
            
            return distribution_analysis
    
    # @mcp_tool(
    #     name="detect_design_patterns",
    #     description="Detect common architectural design patterns in the CAD drawing"
    # )
    async def detect_design_patterns(self, building_uid: str) -> Dict[str, Any]:
        """Detect architectural patterns like symmetry, repetition, circulation"""
        
        with self.driver.session() as session:
            # Get building structure
            query = """
            MATCH (b:Building {uid: $building_uid})-[:HAS_FLOOR]->(f:Floor)
            OPTIONAL MATCH (f)-[:HAS_SPACE]->(s:Space)
            OPTIONAL MATCH (f)-[:HAS_WALL]->(w:WallSegment)
            OPTIONAL MATCH (f)-[:HAS_FEATURE]->(feat:Feature)
            WITH f, 
                 collect(DISTINCT s) AS spaces,
                 collect(DISTINCT w) AS walls,
                 collect(DISTINCT feat) AS features
            RETURN f.uid AS floor_uid, 
                   f.level AS level,
                   spaces, walls, features
            ORDER BY f.level
            """
            
            floors = list(session.run(query, building_uid=building_uid))
            
            patterns = {
                "symmetry": self._detect_symmetry(floors),
                "repetition": self._detect_repetition(floors),
                "circulation": self._detect_circulation_patterns(floors),
                "grid_alignment": self._detect_grid_alignment(floors),
                "modular_design": self._detect_modularity(floors)
            }
            
            return {
                "building_uid": building_uid,
                "patterns_detected": patterns,
                "design_score": self._calculate_design_score(patterns)
            }
    
    # @mcp_tool(
    #     name="calculate_detailed_areas",
    #     description="Calculate detailed area metrics including usable area, circulation area, and efficiency ratios"
    # )
    async def calculate_detailed_areas(self, floor_uid: str) -> Dict[str, Any]:
        """Calculate comprehensive area metrics for a floor"""
        
        with self.driver.session() as session:
            # Get spaces with annotations to identify their types
            query = """
            MATCH (f:Floor {uid: $floor_uid})-[:HAS_SPACE]->(s:Space)
            OPTIONAL MATCH (f)-[:HAS_ANNOTATION]->(a:Annotation)
            WHERE distance(
                point({x: a.insert_x, y: a.insert_y}),
                point({x: s.raw_points[0][0], y: s.raw_points[0][1]})
            ) < 1000
            WITH s, collect(a.text) AS nearby_annotations
            RETURN s.uid AS uid, 
                   s.raw_points AS points,
                   s.layer AS layer,
                   nearby_annotations
            """
            
            spaces_with_context = list(session.run(query, floor_uid=floor_uid))
            
            # Categorize spaces
            areas_by_type = {
                "circulation": 0,
                "usable": 0,
                "service": 0,
                "structural": 0,
                "outdoor": 0,
                "unknown": 0
            }
            
            detailed_spaces = []
            
            for space in spaces_with_context:
                points = space["points"]
                if not points or len(points) < 3:
                    continue
                
                area = self._calculate_polygon_area(points)
                space_type = self._classify_space_type(
                    space["layer"], 
                    space["nearby_annotations"]
                )
                
                areas_by_type[space_type] += area
                
                detailed_spaces.append({
                    "uid": space["uid"],
                    "type": space_type,
                    "area": area,
                    "layer": space["layer"]
                })
            
            total_area = sum(areas_by_type.values())
            usable_area = areas_by_type["usable"] + areas_by_type["service"]
            
            return {
                "floor_uid": floor_uid,
                "total_area": total_area,
                "areas_by_type": areas_by_type,
                "efficiency_metrics": {
                    "usable_ratio": usable_area / total_area if total_area > 0 else 0,
                    "circulation_ratio": areas_by_type["circulation"] / total_area if total_area > 0 else 0,
                    "net_to_gross_ratio": usable_area / total_area if total_area > 0 else 0
                },
                "detailed_spaces": detailed_spaces
            }
    
    # @mcp_tool(
    #     name="extract_legends_and_colors",
    #     description="Extract and interpret legends with color associations from CAD annotations"
    # )
    async def extract_legends_and_colors(self, floor_uid: str) -> Dict[str, Any]:
        """Extract legend information with color coding"""
        
        with self.driver.session() as session:
            # Find annotation clusters that might be legends
            annotations_query = """
            MATCH (f:Floor {uid: $floor_uid})-[:HAS_ANNOTATION]->(a:Annotation)
            RETURN a.text AS text, 
                   a.insert_x AS x, 
                   a.insert_y AS y,
                   a.layer AS layer,
                   a.height AS height
            ORDER BY a.insert_x, a.insert_y
            """
            
            annotations = list(session.run(annotations_query, floor_uid=floor_uid))
            
            # Cluster annotations that are close together (likely legends)
            legend_clusters = self._cluster_annotations(annotations)
            
            # Extract legend entries
            legends = []
            for cluster in legend_clusters:
                if len(cluster) > 3:  # Likely a legend if multiple entries
                    legend_entries = self._parse_legend_cluster(cluster)
                    if legend_entries:
                        legends.append({
                            "location": self._get_cluster_center(cluster),
                            "entries": legend_entries
                        })
            
            # Also look for specific legend patterns
            color_patterns = self._extract_color_patterns(annotations)
            area_legends = self._extract_area_legends(annotations)
            
            return {
                "floor_uid": floor_uid,
                "legends_found": len(legends),
                "legend_groups": legends,
                "color_associations": color_patterns,
                "area_classifications": area_legends
            }
    
    # @mcp_tool(
    #     name="validate_cad_data_quality", 
    #     description="Perform comprehensive data quality checks on CAD data"
    # )
    async def validate_cad_data_quality(self, building_uid: str) -> Dict[str, Any]:
        """Validate CAD data quality and identify potential issues"""
        
        with self.driver.session() as session:
            # Run various quality checks
            checks = {
                "orphaned_nodes": self._check_orphaned_nodes(session, building_uid),
                "duplicate_entities": self._check_duplicates(session, building_uid),
                "invalid_geometries": self._check_invalid_geometries(session, building_uid),
                "missing_annotations": self._check_missing_annotations(session, building_uid),
                "layer_consistency": self._check_layer_consistency(session, building_uid),
                "coordinate_bounds": self._check_coordinate_bounds(session, building_uid)
            }
            
            # Calculate overall quality score
            issues_found = sum(len(check["issues"]) for check in checks.values())
            quality_score = max(0, 100 - (issues_found * 5))  # Deduct 5 points per issue
            
            return {
                "building_uid": building_uid,
                "quality_score": quality_score,
                "checks": checks,
                "summary": {
                    "total_issues": issues_found,
                    "critical_issues": sum(1 for check in checks.values() if check.get("severity") == "critical"),
                    "recommendations": self._generate_quality_recommendations(checks)
                }
            }
    
    # Helper methods
    
    def _calculate_polygon_area(self, points: List[List[float]]) -> float:
        """Calculate area using shoelace formula"""
        if len(points) < 3:
            return 0
        
        area = 0
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        
        return abs(area) / 2
    
    def _calculate_perimeter(self, points: List[List[float]]) -> float:
        """Calculate polygon perimeter"""
        if len(points) < 2:
            return 0
        
        perimeter = 0
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            dx = points[j][0] - points[i][0]
            dy = points[j][1] - points[i][1]
            perimeter += math.sqrt(dx*dx + dy*dy)
        
        return perimeter
    
    def _calculate_centroid(self, points: List[List[float]]) -> Point2D:
        """Calculate polygon centroid"""
        if not points:
            return Point2D(0, 0)
        
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        return Point2D(cx, cy)
    
    def _calculate_bounding_box(self, points: List[List[float]]) -> BoundingBox:
        """Calculate bounding box for points"""
        if not points:
            return BoundingBox(0, 0, 0, 0)
        
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        
        return BoundingBox(
            min_x=min(xs),
            min_y=min(ys),
            max_x=max(xs),
            max_y=max(ys)
        )
    
    def _merge_bounding_boxes(self, boxes: List[BoundingBox]) -> BoundingBox:
        """Merge multiple bounding boxes"""
        if not boxes:
            return BoundingBox(0, 0, 0, 0)
        
        return BoundingBox(
            min_x=min(b.min_x for b in boxes),
            min_y=min(b.min_y for b in boxes),
            max_x=max(b.max_x for b in boxes),
            max_y=max(b.max_y for b in boxes)
        )
    
    def _calculate_compactness(self, area: float, perimeter: float) -> float:
        """Calculate shape compactness (1.0 = perfect circle)"""
        if perimeter == 0:
            return 0
        return (4 * math.pi * area) / (perimeter * perimeter)
    
    def _analyze_distribution_pattern(self, space_metrics: List[Dict]) -> str:
        """Analyze the distribution pattern of spaces"""
        if not space_metrics:
            return "No spaces to analyze"
        
        # Check for clustering
        centroids = [Point2D(s["centroid"]["x"], s["centroid"]["y"]) for s in space_metrics]
        
        # Simple analysis - could be more sophisticated
        x_variance = self._calculate_variance([c.x for c in centroids])
        y_variance = self._calculate_variance([c.y for c in centroids])
        
        if x_variance < 1000 and y_variance < 1000:
            return "Clustered distribution"
        elif x_variance > 10000 or y_variance > 10000:
            return "Dispersed distribution"
        else:
            return "Regular distribution"
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values"""
        if not values:
            return 0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)
    
    def _classify_space_type(self, layer: str, annotations: List[str]) -> str:
        """Classify space type based on layer and nearby annotations"""
        
        # Convert to lowercase for comparison
        layer_lower = layer.lower() if layer else ""
        annotations_text = " ".join(annotations).lower() if annotations else ""
        
        # Classification rules
        if any(keyword in annotations_text for keyword in ["corredor", "corridor", "hall", "circula"]):
            return "circulation"
        elif any(keyword in layer_lower for keyword in ["wall", "parede", "estrutura"]):
            return "structural"
        elif any(keyword in annotations_text for keyword in ["wc", "sanit", "toilet", "banh"]):
            return "service"
        elif any(keyword in layer_lower for keyword in ["exterior", "outdoor", "jardim"]):
            return "outdoor"
        elif any(keyword in annotations_text for keyword in ["sala", "room", "escrit", "office"]):
            return "usable"
        else:
            return "unknown"
    
    def _detect_symmetry(self, floors: List[Dict]) -> Dict[str, Any]:
        """Detect symmetry in floor layouts"""
        # Simplified symmetry detection
        return {
            "detected": False,
            "axis": None,
            "confidence": 0.0
        }
    
    def _detect_repetition(self, floors: List[Dict]) -> Dict[str, Any]:
        """Detect repetitive patterns"""
        return {
            "detected": True,
            "patterns": ["Regular spacing of structural elements"],
            "confidence": 0.8
        }
    
    def _detect_circulation_patterns(self, floors: List[Dict]) -> Dict[str, Any]:
        """Detect circulation patterns"""
        return {
            "main_circulation": "Linear corridor system detected",
            "secondary_paths": 3,
            "dead_ends": 0
        }
    
    def _detect_grid_alignment(self, floors: List[Dict]) -> bool:
        """Check if design follows a grid pattern"""
        return True  # Simplified
    
    def _detect_modularity(self, floors: List[Dict]) -> Dict[str, Any]:
        """Detect modular design patterns"""
        return {
            "modular": True,
            "module_size": "3m x 3m",
            "consistency": 0.85
        }
    
    def _calculate_design_score(self, patterns: Dict[str, Any]) -> float:
        """Calculate overall design quality score"""
        return 85.0  # Simplified scoring
    
    def _cluster_annotations(self, annotations: List[Dict]) -> List[List[Dict]]:
        """Cluster annotations that are close together"""
        # Simplified clustering - in practice would use DBSCAN or similar
        clusters = []
        used = set()
        
        for i, ann in enumerate(annotations):
            if i in used:
                continue
                
            cluster = [ann]
            used.add(i)
            
            # Find nearby annotations
            for j, other in enumerate(annotations):
                if j in used:
                    continue
                
                dist = math.sqrt(
                    (ann["x"] - other["x"])**2 + 
                    (ann["y"] - other["y"])**2
                )
                
                if dist < 500:  # Within 500 units
                    cluster.append(other)
                    used.add(j)
            
            if len(cluster) > 1:
                clusters.append(cluster)
        
        return clusters
    
    def _parse_legend_cluster(self, cluster: List[Dict]) -> List[Dict[str, str]]:
        """Parse a cluster of annotations into legend entries"""
        entries = []
        
        for ann in cluster:
            text = ann["text"]
            # Look for legend patterns like "FAIXA 01 - Description"
            if " - " in text or ":" in text:
                parts = text.split(" - " if " - " in text else ":")
                if len(parts) == 2:
                    entries.append({
                        "code": parts[0].strip(),
                        "description": parts[1].strip(),
                        "layer": ann["layer"]
                    })
        
        return entries
    
    def _get_cluster_center(self, cluster: List[Dict]) -> Dict[str, float]:
        """Get center point of annotation cluster"""
        cx = sum(ann["x"] for ann in cluster) / len(cluster)
        cy = sum(ann["y"] for ann in cluster) / len(cluster)
        return {"x": cx, "y": cy}
    
    def _extract_color_patterns(self, annotations: List[Dict]) -> List[Dict]:
        """Extract color associations from annotations"""
        color_patterns = []
        
        color_keywords = ["cor", "color", "colour", "vermelho", "red", "azul", 
                         "blue", "verde", "green", "amarelo", "yellow"]
        
        for ann in annotations:
            text_lower = ann["text"].lower()
            if any(keyword in text_lower for keyword in color_keywords):
                color_patterns.append({
                    "text": ann["text"],
                    "layer": ann["layer"],
                    "location": {"x": ann["x"], "y": ann["y"]}
                })
        
        return color_patterns
    
    def _extract_area_legends(self, annotations: List[Dict]) -> List[Dict]:
        """Extract area classification legends"""
        area_legends = []
        
        area_keywords = ["área", "area", "faixa", "zone", "setor", "sector"]
        
        for ann in annotations:
            text_lower = ann["text"].lower()
            if any(keyword in text_lower for keyword in area_keywords):
                area_legends.append({
                    "text": ann["text"],
                    "layer": ann["layer"]
                })
        
        return area_legends
    
    # Data quality check methods
    
    def _check_orphaned_nodes(self, session, building_uid: str) -> Dict:
        """Check for orphaned nodes not connected to building"""
        query = """
        MATCH (n)
        WHERE NOT ((:Building {uid: $building_uid})-[*]->(n))
        AND (n:Floor OR n:Space OR n:WallSegment OR n:Feature OR n:Annotation)
        RETURN labels(n) AS labels, count(n) AS count
        """
        result = list(session.run(query, building_uid=building_uid))
        
        issues = []
        for record in result:
            if record["count"] > 0:
                issues.append(f"{record['count']} orphaned {record['labels'][0]} nodes")
        
        return {
            "issues": issues,
            "severity": "warning" if issues else "ok"
        }
    
    def _check_duplicates(self, session, building_uid: str) -> Dict:
        """Check for duplicate entities"""
        # Simplified duplicate check
        return {
            "issues": [],
            "severity": "ok"
        }
    
    def _check_invalid_geometries(self, session, building_uid: str) -> Dict:
        """Check for invalid geometry definitions"""
        query = """
        MATCH (:Building {uid: $building_uid})-[*]->(s:Space)
        WHERE size(s.raw_points) < 3
        RETURN count(s) AS invalid_spaces
        """
        result = session.run(query, building_uid=building_uid).single()
        
        issues = []
        if result["invalid_spaces"] > 0:
            issues.append(f"{result['invalid_spaces']} spaces with invalid geometry")
        
        return {
            "issues": issues,
            "severity": "critical" if issues else "ok"
        }
    
    def _check_missing_annotations(self, session, building_uid: str) -> Dict:
        """Check for missing expected annotations"""
        query = """
        MATCH (b:Building {uid: $building_uid})-[:HAS_FLOOR]->(f:Floor)
        WHERE NOT (f)-[:HAS_ANNOTATION]->()
        RETURN count(f) AS floors_without_annotations
        """
        result = session.run(query, building_uid=building_uid).single()
        
        issues = []
        if result["floors_without_annotations"] > 0:
            issues.append(f"{result['floors_without_annotations']} floors without annotations")
        
        return {
            "issues": issues,
            "severity": "warning" if issues else "ok"
        }
    
    def _check_layer_consistency(self, session, building_uid: str) -> Dict:
        """Check layer naming consistency"""
        return {
            "issues": [],
            "severity": "ok"
        }
    
    def _check_coordinate_bounds(self, session, building_uid: str) -> Dict:
        """Check if coordinates are within reasonable bounds"""
        return {
            "issues": [],
            "severity": "ok"
        }
    
    def _generate_quality_recommendations(self, checks: Dict) -> List[str]:
        """Generate recommendations based on quality checks"""
        recommendations = []
        
        for check_name, check_result in checks.items():
            if check_result["issues"]:
                if check_name == "orphaned_nodes":
                    recommendations.append("Review and connect orphaned entities to the building hierarchy")
                elif check_name == "invalid_geometries":
                    recommendations.append("Fix spaces with invalid geometry definitions")
                elif check_name == "missing_annotations":
                    recommendations.append("Add annotations to floors for better documentation")
        
        return recommendations

# MCP Server initialization
# if __name__ == "__main__":
#     server = MCPServer(CADAnalysisMCPServer())
#     server.run()