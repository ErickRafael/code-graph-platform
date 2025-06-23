"""Graph modeling and loading utilities.

Will be implemented in Phase 3.
"""

from typing import List, Dict, Any
import json
import os
from pathlib import Path
from neo4j import GraphDatabase, Driver

# ---------------------------------------------------------------------------
# Helpers for Neo4j connection
# ---------------------------------------------------------------------------


def _get_neo4j_driver() -> Driver:
    """Create a Neo4j driver from environment variables.

    Environment variables consumed:
    - NEO4J_URI (default ``bolt://localhost:7687``)
    - NEO4J_USER (default ``neo4j``)
    - NEO4J_PASSWORD (default ``neo4j``)
    """

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "neo4j")

    return GraphDatabase.driver(uri, auth=(user, password))


# ---------------------------------------------------------------------------
# Transformation phase (E  ->  intermediate graph representation)
# ---------------------------------------------------------------------------

Node = Dict[str, Any]
Relationship = Dict[str, Any]
GraphPayload = Dict[str, List[Dict[str, Any]]]


def _new_uid(prefix: str, counter: int) -> str:
    """Generate a deterministic UID with prefix and counter."""

    return f"{prefix}_{counter}"


def transform_to_graph(json_file: Path) -> GraphPayload:  # noqa: D401
    """Transform extracted CAD entities JSON into a graph payload.

    This is a *heuristic* implementation suitable for early prototyping. It
    treats:
    - One global Building node (uid: building_1)
    - One Floor node (uid: floor_1)
    - Closed LWPOLYLINEs as Space nodes
    - LINE entities as WallSegment nodes
    - CIRCLE/ARC entities as Features
    - TEXT/MTEXT entities as Annotations

    Relationships:
    Building-[:HAS_FLOOR]->Floor
    Floor-[:HAS_SPACE]->Space
    Floor-[:HAS_WALL]->WallSegment
    Floor-[:HAS_FEATURE]->Feature
    Floor-[:HAS_ANNOTATION]->Annotation

    Parameters
    ----------
    json_file : Path
        File produced by entity extraction step (.json).

    Returns
    -------
    Dict[str, List[dict]]
        ``{"nodes": [...], "relationships": [...]}``
    """

    # Try different encodings to handle potential binary data in JSON
    json_content = None
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            json_content = Path(json_file).read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    
    if json_content is None:
        raise ValueError(f"Could not read JSON file with any supported encoding: {json_file}")
    
    data = json.loads(json_content)
    
    # Handle different JSON formats
    if isinstance(data, dict) and 'OBJECTS' in data:
        # This is dwgread format - extract entities from OBJECTS
        entities = []
        for obj in data.get('OBJECTS', []):
            if isinstance(obj, dict):
                obj_type = obj.get('object', '').upper()
                # Map dwgread object types to our expected types
                if obj_type == 'LINE':
                    entities.append({
                        'type': 'LINE',
                        'start': obj.get('start', {}),
                        'end': obj.get('end', {}),
                        'layer': obj.get('layer', '0')
                    })
                elif obj_type == 'LWPOLYLINE':
                    entities.append({
                        'type': 'LWPOLYLINE',
                        'points': obj.get('points', []),
                        'is_closed': obj.get('flag', 0) & 1,  # Closed flag is bit 0
                        'layer': obj.get('layer', '0')
                    })
                elif obj_type == 'CIRCLE':
                    entities.append({
                        'type': 'CIRCLE',
                        'center': obj.get('center', {}),
                        'radius': obj.get('radius', 0),
                        'layer': obj.get('layer', '0')
                    })
                elif obj_type == 'ARC':
                    entities.append({
                        'type': 'ARC',
                        'center': obj.get('center', {}),
                        'radius': obj.get('radius', 0),
                        'start_angle': obj.get('start_angle', 0),
                        'end_angle': obj.get('end_angle', 0),
                        'layer': obj.get('layer', '0')
                    })
                elif obj_type in ['TEXT', 'MTEXT']:
                    entities.append({
                        'type': obj_type,
                        'text': obj.get('text_value', ''),
                        'insert': obj.get('ins_pt', obj.get('insertion_pt', {})),
                        'height': obj.get('height', 1.0),
                        'layer': obj.get('layer', '0')
                    })
    elif isinstance(data, list):
        # This is the expected format - array of entities
        entities = data
    else:
        raise ValueError(f"Unexpected JSON format: expected list or dict with OBJECTS, got {type(data)}")

    nodes: List[Node] = []
    relationships: List[Relationship] = []

    # Create the Building and Floor nodes first
    building_uid = "building_1"
    floor_uid = "floor_1"
    nodes.append({"label": "Building", "uid": building_uid, "name": f"DWG Building ({Path(json_file).stem})"})
    nodes.append({"label": "Floor", "uid": floor_uid, "name": "Floor 1", "level": 1})
    relationships.append(
        {
            "start_label": "Building",
            "start_uid": building_uid,
            "type": "HAS_FLOOR",
            "end_label": "Floor",
            "end_uid": floor_uid,
        }
    )

    # Counters for unique IDs
    space_counter = 1
    wall_counter = 1
    feature_counter = 1
    annotation_counter = 1

    # Add scale metadata if available
    scale_node_uid = None
    
    for entity in entities:
        etype = entity.get("type")
        
        if etype == "SCALE_INFO":
            # Create a Metadata node for scale information
            scale_node_uid = _new_uid("metadata", 1)
            scale_data = entity.get("scales", {})
            nodes.append({
                "label": "Metadata",
                "uid": scale_node_uid,
                "type": "SCALE_INFO",
                "dimscale": scale_data.get("DIMSCALE", 1.0),
                "ltscale": scale_data.get("LTSCALE", 1.0),
                "cmlscale": scale_data.get("CMLSCALE", 1.0),
                "celtscale": scale_data.get("CELTSCALE", 1.0)
            })
            relationships.append({
                "start_label": "Building",
                "start_uid": building_uid,
                "type": "HAS_METADATA",
                "end_label": "Metadata",
                "end_uid": scale_node_uid,
            })
            continue
        
        if etype == "LWPOLYLINE" and entity.get("is_closed"):
            # Closed polylines represent spaces
            space_uid = _new_uid("space", space_counter)
            space_counter += 1
            nodes.append(
                {
                    "label": "Space",
                    "uid": space_uid,
                    "raw_points": entity.get("points"),
                    "point_count": len(entity.get("points", [])),
                    "layer": str(entity.get("layer", "0"))
                }
            )
            relationships.append(
                {
                    "start_label": "Floor",
                    "start_uid": floor_uid,
                    "type": "HAS_SPACE",
                    "end_label": "Space",
                    "end_uid": space_uid,
                }
            )
            
        elif etype == "LINE":
            # Lines represent wall segments
            wall_uid = _new_uid("wall", wall_counter)
            wall_counter += 1
            nodes.append(
                {
                    "label": "WallSegment",
                    "uid": wall_uid,
                    "start": entity.get("start"),
                    "end": entity.get("end"),
                    "layer": str(entity.get("layer", "0"))
                }
            )
            relationships.append(
                {
                    "start_label": "Floor",
                    "start_uid": floor_uid,
                    "type": "HAS_WALL",
                    "end_label": "WallSegment",
                    "end_uid": wall_uid,
                }
            )
            
        elif etype in ["CIRCLE", "ARC"]:
            # Circles and arcs as architectural features
            feature_uid = _new_uid("feature", feature_counter)
            feature_counter += 1
            feature_data = {
                "label": "Feature",
                "uid": feature_uid,
                "type": etype,
                "layer": str(entity.get("layer", "0"))
            }
            
            if etype == "CIRCLE":
                feature_data.update({
                    "center": entity.get("center"),
                    "radius": entity.get("radius", 0)
                })
            elif etype == "ARC":
                feature_data.update({
                    "center": entity.get("center"),
                    "radius": entity.get("radius", 0),
                    "start_angle": entity.get("start_angle", 0),
                    "end_angle": entity.get("end_angle", 0)
                })
                
            nodes.append(feature_data)
            relationships.append(
                {
                    "start_label": "Floor",
                    "start_uid": floor_uid,
                    "type": "HAS_FEATURE",
                    "end_label": "Feature",
                    "end_uid": feature_uid,
                }
            )
            
        elif etype in ["TEXT", "MTEXT"]:
            # Text entities as annotations
            annotation_uid = _new_uid("annotation", annotation_counter)
            annotation_counter += 1
            nodes.append(
                {
                    "label": "Annotation",
                    "uid": annotation_uid,
                    "text": entity.get("text", ""),
                    "insert": entity.get("insert"),
                    "height": entity.get("height", 1.0),
                    "layer": str(entity.get("layer", "0"))
                }
            )
            relationships.append(
                {
                    "start_label": "Floor",
                    "start_uid": floor_uid,
                    "type": "HAS_ANNOTATION",
                    "end_label": "Annotation",
                    "end_uid": annotation_uid,
                }
            )

    return {"nodes": nodes, "relationships": relationships}


# ---------------------------------------------------------------------------
# Loading phase (graph payload  ->  Neo4j)
# ---------------------------------------------------------------------------


def _merge_node(tx, label: str, uid: str, props: Dict[str, Any]):
    """Merge a node, flattening nested objects for Neo4j compatibility."""
    
    # Flatten nested objects (like coordinates) for Neo4j
    flat_props = {}
    for key, value in props.items():
        if isinstance(value, dict) and all(k in value for k in ['x', 'y', 'z']):
            # Convert coordinate objects to separate properties
            flat_props[f"{key}_x"] = value['x']
            flat_props[f"{key}_y"] = value['y'] 
            flat_props[f"{key}_z"] = value['z']
        elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
            # Convert array of coordinate objects to JSON string
            import json
            flat_props[key] = json.dumps(value)
        else:
            # For non-dict, non-list values, store as-is
            flat_props[key] = value
    
    query = (
        f"MERGE (n:{label} {{uid: $uid}})\n"
        f"SET n += $props\n"
        f"RETURN elementId(n) as id"
    )
    tx.run(query, uid=uid, props=flat_props)


def _merge_relationship(tx, start_label: str, start_uid: str, rel_type: str, end_label: str, end_uid: str):
    query = (
        f"MATCH (a:{start_label} {{uid: $start_uid}})\n"
        f"MATCH (b:{end_label} {{uid: $end_uid}})\n"
        f"MERGE (a)-[r:{rel_type}]->(b)\n"
        f"RETURN elementId(r) as id"
    )
    tx.run(query, start_uid=start_uid, end_uid=end_uid)


def clear_neo4j_data() -> None:
    """Clear all existing CAD data from Neo4j before loading new data."""
    driver = _get_neo4j_driver()
    with driver.session() as session:
        # Delete all nodes and relationships
        session.run("MATCH (n) DETACH DELETE n")
    driver.close()
    print("Cleared all existing data from Neo4j")

def load_to_neo4j(graph_data: GraphPayload) -> None:  # noqa: D401
    """Load nodes and relationships into Neo4j using the official driver.

    The function first clears existing data, then loads new data to ensure
    only the latest uploaded file is in the database.
    """

    # Clear existing data first
    clear_neo4j_data()
    
    driver = _get_neo4j_driver()
    with driver.session() as session:
        # Batch-create/merge nodes
        for node in graph_data.get("nodes", []):
            label = node.pop("label")
            uid = node.pop("uid")
            props = node  # remaining fields
            session.write_transaction(_merge_node, label, uid, props)

        # Batch-create/merge relationships
        for rel in graph_data.get("relationships", []):
            session.write_transaction(
                _merge_relationship,
                rel["start_label"],
                rel["start_uid"],
                rel["type"],
                rel["end_label"],
                rel["end_uid"],
            )

    driver.close() 