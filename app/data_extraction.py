"""Data extraction utilities for DWG and DXF files.

Functions to be implemented in Phase 2.
"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

import ezdxf


def _ensure_output_dir(output_dir: Path) -> None:
    """Create the output directory if it does not exist."""
    output_dir.mkdir(parents=True, exist_ok=True)


def extract_dwg(file_path: Path, output_dir: Path) -> Path:  # noqa: D401
    """Extract entities from a DWG file using **libredwg**'s ``dwgread`` CLI.

    Parameters
    ----------
    file_path : Path
        Absolute or relative path to the ``.dwg`` file to parse.
    output_dir : Path
        Directory where the resulting ``.json`` should be written.

    Returns
    -------
    Path
        Path to the generated JSON file containing structured DWG data.
    """
    if file_path.suffix.lower() != ".dwg":
        raise ValueError("extract_dwg expects a .dwg file")

    _ensure_output_dir(output_dir)
    output_file = output_dir / f"{file_path.stem}.json"

    # Build dwgread command. The -O JSON flag instructs libredwg to output JSON
    # documentation: https://www.gnu.org/software/libredwg/manual/index.html#dwgread
    cmd = [
        "dwgread",
        "-O",
        "JSON",
        "-o",
        str(output_file),
        str(file_path),
    ]

    try:
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        if completed.stdout:
            # libredwg sometimes prints progress info to stdout; store it for debugging
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "dwgread CLI not found. Ensure libredwg-tools is installed inside the container."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"dwgread failed: {exc.stderr}") from exc

    if not output_file.exists():
        raise RuntimeError("dwgread did not create the expected output file")

    return output_file


def _serialize_dxf_entity(entity) -> Dict[str, Any]:
    """Convert an ezdxf entity into a JSON-serialisable dictionary."""

    def _point(pt):  # helper to ensure JSON serialisable points
        return {"x": float(pt[0]), "y": float(pt[1]), "z": float(pt[2] if len(pt) > 2 else 0.0)}

    etype = entity.dxftype()
    base: Dict[str, Any] = {
        "type": etype,
        "layer": entity.dxf.layer,
    }

    if etype == "LINE":
        base.update(
            {
                "start": _point(entity.dxf.start),
                "end": _point(entity.dxf.end),
            }
        )
    elif etype == "LWPOLYLINE":
        points = [
            _point((p[0], p[1], 0.0))  # LWPOLYLINE points are (x, y, *rest)
            for p in entity.get_points()
        ]
        base.update({"points": points, "is_closed": bool(entity.closed)})
    elif etype == "CIRCLE":
        base.update({
            "center": _point(entity.dxf.center),
            "radius": float(entity.dxf.radius),
        })
    elif etype == "ARC":
        base.update({
            "center": _point(entity.dxf.center),
            "radius": float(entity.dxf.radius),
            "start_angle": float(entity.dxf.start_angle),
            "end_angle": float(entity.dxf.end_angle),
        })
    elif etype in {"TEXT", "MTEXT"}:
        text_content = entity.text if hasattr(entity, "text") else entity.plain_text()
        base.update(
            {
                "text": text_content,
                "insert": _point(entity.dxf.insert),
                "height": float(entity.dxf.height) if hasattr(entity.dxf, "height") else None,
            }
        )
    else:
        # For unhandled entity types, fallback to ezdxf's JSON exporter (string)
        base.update({"raw": entity.dxftype()})

    return base


def extract_dxf(file_path: Path, output_dir: Path) -> Path:  # noqa: D401
    """Extract entities from a DXF file using **ezdxf**.

    The function focuses on common geometric and annotation entities and stores the
    extracted data in a JSON file compatible with the DWG extraction output.

    Parameters
    ----------
    file_path : Path
        Path to the ``.dxf`` file.
    output_dir : Path
        Directory where the resulting JSON file should be saved.

    Returns
    -------
    Path
        Path to the generated JSON file.
    """
    if file_path.suffix.lower() != ".dxf":
        raise ValueError("extract_dxf expects a .dxf file")

    _ensure_output_dir(output_dir)
    doc = ezdxf.readfile(str(file_path))
    msp = doc.modelspace()

    entities_to_capture = {"LINE", "LWPOLYLINE", "TEXT", "MTEXT", "CIRCLE", "ARC"}
    captured: List[Dict[str, Any]] = []

    for entity in msp:
        if entity.dxftype() in entities_to_capture:
            captured.append(_serialize_dxf_entity(entity))

    output_file = output_dir / f"{file_path.stem}.json"
    with output_file.open("w", encoding="utf-8") as fp:
        json.dump(captured, fp, indent=2)

    return output_file


def extract_entities_from_dwg_json(dwg_json_path: Path, output_path: Path) -> None:
    """Extract geometric entities from dwgread JSON output.
    
    This function processes the complex dwgread JSON format and extracts
    only the geometric entities we care about.
    """
    with open(dwg_json_path, 'r', encoding='latin-1') as f:
        data = json.load(f)
    
    entities = []
    
    # Also extract scale information from HEADER
    scale_info = None
    if isinstance(data, dict) and 'HEADER' in data:
        header = data['HEADER']
        scale_info = {
            'DIMSCALE': header.get('DIMSCALE', 1.0),
            'LTSCALE': header.get('LTSCALE', 1.0),
            'CMLSCALE': header.get('CMLSCALE', 1.0),
            'CELTSCALE': header.get('CELTSCALE', 1.0)
        }
        # Add scale info as a special entity
        entities.append({
            'type': 'SCALE_INFO',
            'scales': scale_info,
            'layer': 'METADATA'
        })
    
    # Process OBJECTS array from dwgread output
    if isinstance(data, dict) and 'OBJECTS' in data:
        for obj in data.get('OBJECTS', []):
            if not isinstance(obj, dict):
                continue
                
            # Check both 'object' and 'entity' fields
            obj_type = (obj.get('object', '') or obj.get('entity', '')).upper()
            
            # Extract LINE entities
            if obj_type == 'LINE':
                # Convert array to dict if needed
                start = obj.get('start', obj.get('start_pt', [0, 0, 0]))
                end = obj.get('end', obj.get('end_pt', [0, 0, 0]))
                if isinstance(start, list) and len(start) >= 2:
                    start = {'x': start[0], 'y': start[1], 'z': start[2] if len(start) > 2 else 0}
                if isinstance(end, list) and len(end) >= 2:
                    end = {'x': end[0], 'y': end[1], 'z': end[2] if len(end) > 2 else 0}
                    
                entities.append({
                    'type': 'LINE',
                    'start': start,
                    'end': end,
                    'layer': str(obj.get('layer', '0'))
                })
            
            # Extract LWPOLYLINE entities
            elif obj_type == 'LWPOLYLINE':
                points = obj.get('points', obj.get('pts', []))
                # Convert points if needed
                if points and isinstance(points[0], (list, tuple)):
                    points = [{'x': p[0], 'y': p[1], 'z': p[2] if len(p) > 2 else 0} for p in points]
                    
                entities.append({
                    'type': 'LWPOLYLINE',
                    'points': points,
                    'is_closed': bool(obj.get('flag', obj.get('flags', 0)) & 1),
                    'layer': str(obj.get('layer', '0'))
                })
            
            # Extract CIRCLE entities
            elif obj_type == 'CIRCLE':
                center = obj.get('center', [0, 0, 0])
                if isinstance(center, list) and len(center) >= 2:
                    center = {'x': center[0], 'y': center[1], 'z': center[2] if len(center) > 2 else 0}
                    
                entities.append({
                    'type': 'CIRCLE',
                    'center': center,
                    'radius': obj.get('radius', 0),
                    'layer': str(obj.get('layer', '0'))
                })
            
            # Extract ARC entities
            elif obj_type == 'ARC' and 'center' in obj:
                entities.append({
                    'type': 'ARC',
                    'center': obj['center'],
                    'radius': obj.get('radius', 0),
                    'start_angle': obj.get('start_angle', 0),
                    'end_angle': obj.get('end_angle', 0),
                    'layer': obj.get('layer', '0')
                })
            
            # Extract TEXT/MTEXT entities
            elif obj_type in ['TEXT', 'MTEXT']:
                # TEXT entities use text_value field
                text = obj.get('text_value', obj.get('text', ''))
                # Get insertion point - different fields for TEXT vs MTEXT
                insert = obj.get('insertion_pt', obj.get('ins_pt', obj.get('insert', [0, 0, 0])))
                if isinstance(insert, list) and len(insert) >= 2:
                    insert = {'x': insert[0], 'y': insert[1], 'z': insert[2] if len(insert) > 2 else 0}
                
                # Only add if there's actual text
                if text and text.strip():
                    entities.append({
                        'type': obj_type,
                        'text': text,
                        'insert': insert,
                        'height': obj.get('height', 1.0),
                        'layer': str(obj.get('layer', '0'))
                    })
    
    # Write entities to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entities, f, indent=2)
    
    print(f"Extracted {len(entities)} entities to {output_path}")


def extract_cad_data(file_path: Path, output_dir: Optional[Path] = None) -> Path:
    """Main entry point for CAD data extraction.

    Detects the file type (DWG or DXF) and delegates to the corresponding
    extraction function. The resulting data is always written as JSON into
    *output_dir* (defaults to ``import/`` folder at repo root).

    Parameters
    ----------
    file_path : Path
        Path to the CAD file.
    output_dir : Path | None, optional
        Target directory for JSON output. Defaults to the project-level ``import``
        folder.

    Returns
    -------
    Path
        Path to the generated JSON file.
    """
    file_path = Path(file_path)
    if output_dir is None:
        # Default to repository-level ./import directory relative to this file (../import)
        output_dir = Path(__file__).resolve().parent.parent / "import"

    suffix = file_path.suffix.lower()
    if suffix == ".dwg":
        # First extract raw JSON using dwgread
        raw_json_path = extract_dwg(file_path, Path(output_dir))
        
        # Then extract entities to a cleaner format
        entities_path = output_dir / f"{file_path.stem}-entities.json"
        try:
            extract_entities_from_dwg_json(raw_json_path, entities_path)
            # Return entities file if successfully created
            if entities_path.exists():
                return entities_path
        except Exception as e:
            print(f"Failed to extract entities: {e}")
        
        # Fallback to raw JSON
        return raw_json_path
    elif suffix == ".dxf":
        return extract_dxf(file_path, Path(output_dir))
    else:
        raise ValueError("Unsupported CAD format: only .dwg and .dxf are supported") 