#!/usr/bin/env python3
"""
LibreDWG Data Transformer - Centralized transformation module
Converts LibreDWG JSON output to Neo4j-compatible format

Solves:
- Coordinate arrays [x,y,z] → dict {"x": x, "y": y, "z": z}
- Decimal types → float/int
- Encoding normalization → UTF-8
- Nested structures → flat properties
"""

import json
from typing import Dict, Any, List, Union, Optional
from decimal import Decimal
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransformationConfig:
    """Configuration for transformation behavior"""
    flatten_coordinates: bool = True
    convert_decimals: bool = True
    normalize_encoding: bool = True
    max_coordinate_precision: int = 6
    strip_null_values: bool = False
    preserve_original_types: bool = False


class LibreDWGTransformer:
    """
    Centralized transformer for LibreDWG JSON data to Neo4j format.
    
    This class handles all data type conversions and transformations
    required to make LibreDWG output compatible with Neo4j storage.
    """
    
    def __init__(self, config: Optional[TransformationConfig] = None):
        self.config = config or TransformationConfig()
        self.transformation_stats = {
            "coordinates_transformed": 0,
            "decimals_converted": 0,
            "arrays_flattened": 0,
            "nulls_removed": 0,
            "maps_flattened": 0,
            "complex_dicts_flattened": 0,
            "errors": []
        }
    
    def transform(self, libredwg_data: Union[Dict, List, str]) -> Dict[str, Any]:
        """
        Main transformation entry point.
        
        Args:
            libredwg_data: Raw LibreDWG JSON data (dict, list, or JSON string)
            
        Returns:
            Transformed data ready for Neo4j
        """
        # Handle JSON string input
        if isinstance(libredwg_data, str):
            libredwg_data = self._parse_json_safely(libredwg_data)
        
        # Reset stats for this transformation
        self.transformation_stats = {
            "coordinates_transformed": 0,
            "decimals_converted": 0,
            "arrays_flattened": 0,
            "nulls_removed": 0,
            "maps_flattened": 0,
            "complex_dicts_flattened": 0,
            "errors": []
        }
        
        # Transform the data
        if isinstance(libredwg_data, dict):
            # Standard LibreDWG format with HEADER and OBJECTS
            if "HEADER" in libredwg_data and "OBJECTS" in libredwg_data:
                return self._transform_libredwg_format(libredwg_data)
            else:
                # Generic dict transformation
                return self._transform_value(libredwg_data)
        elif isinstance(libredwg_data, list):
            # List of entities
            return {
                "entities": [self._transform_value(item) for item in libredwg_data],
                "transformation_stats": self.transformation_stats
            }
        else:
            raise ValueError(f"Unexpected data type: {type(libredwg_data)}")
    
    def _parse_json_safely(self, json_str: str) -> Any:
        """Parse JSON with multiple encoding attempts"""
        # Try different encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'utf-8-sig']:
            try:
                if isinstance(json_str, bytes):
                    json_str = json_str.decode(encoding)
                return json.loads(json_str)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        
        raise ValueError("Could not parse JSON with any supported encoding")
    
    def _transform_libredwg_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform standard LibreDWG JSON format"""
        transformed = {
            "header": self._transform_header(data.get("HEADER", {})),
            "entities": self._transform_objects(data.get("OBJECTS", [])),
            "transformation_stats": self.transformation_stats
        }
        
        return transformed
    
    def _transform_header(self, header: Dict[str, Any]) -> Dict[str, Any]:
        """Transform HEADER section"""
        return self._transform_value(header)
    
    def _transform_objects(self, objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform OBJECTS section"""
        transformed_objects = []
        
        for obj in objects:
            try:
                transformed_obj = self._transform_entity(obj)
                transformed_objects.append(transformed_obj)
            except Exception as e:
                self.transformation_stats["errors"].append({
                    "object": obj.get("object", "UNKNOWN"),
                    "error": str(e)
                })
                logger.error(f"Error transforming entity: {e}")
        
        return transformed_objects
    
    def _transform_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a single entity with special handling for CAD types"""
        entity_type = entity.get("object", entity.get("type", "UNKNOWN"))
        
        # Start with base transformation
        transformed = {}
        
        for key, value in entity.items():
            # Special handling for coordinate fields
            if key in ["start", "end", "center", "insertion_pt", "ins_pt", "points"]:
                transformed_value = self._transform_coordinates(value, key)
            else:
                transformed_value = self._transform_value(value)
            
            # Handle flattening of coordinate dicts
            if (self.config.flatten_coordinates and 
                isinstance(transformed_value, dict) and 
                all(k in transformed_value for k in ["x", "y"])):
                # Flatten coordinates to entity level
                for coord, coord_value in transformed_value.items():
                    transformed[f"{key}_{coord}"] = coord_value
            else:
                transformed[key] = transformed_value
        
        return transformed
    
    def _transform_coordinates(self, coords: Any, field_name: str) -> Any:
        """Transform coordinate data"""
        if coords is None:
            return None
        
        # Handle array format [x, y] or [x, y, z]
        if isinstance(coords, list):
            if len(coords) >= 2 and all(isinstance(c, (int, float, Decimal)) for c in coords[:3]):
                self.transformation_stats["coordinates_transformed"] += 1
                result = {
                    "x": self._convert_numeric(coords[0]),
                    "y": self._convert_numeric(coords[1])
                }
                if len(coords) >= 3:
                    result["z"] = self._convert_numeric(coords[2])
                else:
                    result["z"] = 0.0
                return result
            # Handle array of coordinates (e.g., polyline points)
            elif all(isinstance(c, list) for c in coords):
                return [self._transform_coordinates(c, f"{field_name}[{i}]") 
                        for i, c in enumerate(coords)]
        
        # Already in dict format or other type
        return self._transform_value(coords)
    
    def _transform_value(self, value: Any) -> Any:
        """Transform any value recursively"""
        if value is None:
            return None if not self.config.strip_null_values else None
        
        # Handle Vec3 objects (from ezdxf library)
        if hasattr(value, '__class__') and value.__class__.__name__ == 'Vec3':
            # Convert Vec3 to coordinate dict
            self.transformation_stats['coordinates_transformed'] += 1
            return {
                'x': float(value.x) if hasattr(value, 'x') else 0.0,
                'y': float(value.y) if hasattr(value, 'y') else 0.0,
                'z': float(value.z) if hasattr(value, 'z') else 0.0
            }
        
        # Handle Map{} objects (LibreDWG complex structures) - CRITICAL FIX
        if hasattr(value, '__class__') and 'Map' in str(type(value)):
            return self._flatten_map_object(value)
        
        # Handle Decimal
        if isinstance(value, Decimal):
            self.transformation_stats["decimals_converted"] += 1
            return self._convert_numeric(value)
        
        # Handle dict
        if isinstance(value, dict):
            # Check for problematic nested structures before transformation
            if self._is_complex_nested_dict(value):
                return self._flatten_complex_dict(value)
            
            transformed = {}
            for k, v in value.items():
                transformed_v = self._transform_value(v)
                if transformed_v is not None or not self.config.strip_null_values:
                    transformed[k] = transformed_v
            return transformed
        
        # Handle list
        if isinstance(value, list):
            return [self._transform_value(item) for item in value]
        
        # Handle numeric types
        if isinstance(value, (int, float)):
            return self._convert_numeric(value)
        
        # Handle strings (ensure UTF-8)
        if isinstance(value, (str, bytes)):
            return self._normalize_string(value)
        
        # Pass through other types
        return value
    
    def _convert_numeric(self, value: Union[int, float, Decimal]) -> Union[int, float]:
        """Convert numeric value to Neo4j-compatible type"""
        if isinstance(value, Decimal):
            # Convert Decimal to float
            float_val = float(value)
            # Check if it's actually an integer
            if float_val.is_integer() and abs(float_val) < 2**53:
                return int(float_val)
            return round(float_val, self.config.max_coordinate_precision)
        elif isinstance(value, float):
            # Round floats to specified precision
            return round(value, self.config.max_coordinate_precision)
        else:
            return value
    
    def _normalize_string(self, value: Union[str, bytes]) -> str:
        """Normalize string encoding to UTF-8"""
        if isinstance(value, bytes):
            # Try to decode bytes
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    return value.decode(encoding)
                except UnicodeDecodeError:
                    continue
            # Fallback to lossy decode
            return value.decode('utf-8', errors='replace')
        return value
    
    def _flatten_map_object(self, map_obj: Any) -> Union[str, Dict[str, Any]]:
        """
        Flatten LibreDWG Map{} objects to Neo4j-compatible format.
        Based on official LibreDWG documentation and Neo4j property restrictions.
        """
        self.transformation_stats["maps_flattened"] += 1
        
        try:
            # If it has key-value access, try to extract as dict
            if hasattr(map_obj, 'items') or hasattr(map_obj, '__iter__'):
                flattened = {}
                
                # Handle iterator-based access
                if hasattr(map_obj, '__iter__'):
                    try:
                        for i, item in enumerate(map_obj):
                            key = f"item_{i}"
                            value = self._transform_value(item)
                            if value is not None:
                                flattened[key] = value
                    except (TypeError, AttributeError):
                        pass
                
                # Handle dict-like access
                if hasattr(map_obj, 'items'):
                    try:
                        for key, value in map_obj.items():
                            safe_key = str(key).replace('.', '_').replace(' ', '_')
                            flattened[safe_key] = self._transform_value(value)
                    except (TypeError, AttributeError):
                        pass
                
                return flattened if flattened else str(map_obj)
            
            # Fallback to string representation
            return str(map_obj)
            
        except Exception as e:
            logger.warning(f"Error flattening Map object: {e}")
            return str(map_obj)
    
    def _is_complex_nested_dict(self, value: Dict[str, Any]) -> bool:
        """
        Check if dict contains complex nested structures that need flattening.
        Enhanced to catch ANY nested dict/list combinations that could cause Map{} errors.
        """
        # Check for known problematic patterns from DWG analysis
        problematic_keys = ['items', 'color', 'rgb', 'index']
        
        for key in problematic_keys:
            if key in value:
                nested_value = value[key]
                # If it's a dict with multiple nested levels or complex objects
                if isinstance(nested_value, dict) and len(nested_value) > 0:
                    return True
                # If it's a list with dict elements
                if isinstance(nested_value, list) and len(nested_value) > 0:
                    if any(isinstance(item, dict) for item in nested_value):
                        return True
        
        # Additional check: Only specific nested dict patterns need flattening
        # Don't flatten node dictionaries that are already processed by graph_loader
        if 'label' in value and 'uid' in value:
            # This is likely a processed node, don't flatten unless it has specific problematic patterns
            return False
            
        for key, nested_value in value.items():
            if isinstance(nested_value, dict) and len(nested_value) > 1:
                # Only flatten dicts with multiple properties that could cause Map{} issues
                return True
            if isinstance(nested_value, list) and any(isinstance(item, dict) for item in nested_value):
                return True
        
        return False
    
    def _flatten_complex_dict(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten complex nested dictionaries to prevent Map{} serialization errors.
        Follows Neo4j property naming conventions.
        """
        self.transformation_stats["complex_dicts_flattened"] += 1
        flattened = {}
        
        for key, nested_value in value.items():
            if isinstance(nested_value, dict):
                # Flatten dict: color: {index: 7, rgb: 16777215} → color_index: 7, color_rgb: 16777215
                for nested_key, nested_val in nested_value.items():
                    safe_key = f"{key}_{nested_key}".replace('.', '_').replace(' ', '_')
                    flattened[safe_key] = self._transform_value(nested_val)
            elif isinstance(nested_value, list) and len(nested_value) > 0:
                # Flatten list of dicts: items: [{type: "text"}, {type: "line"}] → items_0_type: "text", items_1_type: "line"
                if all(isinstance(item, dict) for item in nested_value):
                    for i, item_dict in enumerate(nested_value):
                        # Recursively flatten each dict in the list
                        if self._is_complex_nested_dict(item_dict):
                            sub_flattened = self._flatten_complex_dict(item_dict)
                            for sub_key, sub_val in sub_flattened.items():
                                safe_key = f"{key}_{i}_{sub_key}".replace('.', '_').replace(' ', '_')
                                flattened[safe_key] = sub_val
                        else:
                            for item_key, item_val in item_dict.items():
                                safe_key = f"{key}_{i}_{item_key}".replace('.', '_').replace(' ', '_')
                                flattened[safe_key] = self._transform_value(item_val)
                else:
                    # Simple list: keep as array
                    flattened[key] = [self._transform_value(item) for item in nested_value]
            else:
                # Simple value: transform and keep
                flattened[key] = self._transform_value(nested_value)
        
        return flattened
    
    def get_transformation_report(self) -> Dict[str, Any]:
        """Get detailed transformation statistics"""
        return {
            "statistics": self.transformation_stats,
            "config": {
                "flatten_coordinates": self.config.flatten_coordinates,
                "convert_decimals": self.config.convert_decimals,
                "normalize_encoding": self.config.normalize_encoding,
                "max_coordinate_precision": self.config.max_coordinate_precision
            }
        }


# Convenience functions
def transform_libredwg_json(json_data: Union[Dict, List, str], 
                           config: Optional[TransformationConfig] = None) -> Dict[str, Any]:
    """
    Transform LibreDWG JSON data for Neo4j compatibility.
    
    Args:
        json_data: Raw JSON from LibreDWG
        config: Optional transformation configuration
        
    Returns:
        Transformed data ready for Neo4j
    """
    transformer = LibreDWGTransformer(config)
    return transformer.transform(json_data)


def transform_coordinates_only(coords: Any) -> Dict[str, float]:
    """
    Transform just coordinate data.
    
    Args:
        coords: Coordinate data in any format
        
    Returns:
        Dict with x, y, z keys
    """
    transformer = LibreDWGTransformer()
    return transformer._transform_coordinates(coords, "coord")


if __name__ == "__main__":
    # Test transformation
    test_data = {
        "HEADER": {
            "filename": "test.dwg",
            "DIMSCALE": Decimal("1.0")
        },
        "OBJECTS": [
            {
                "object": "LINE",
                "start": [100.5, 200.5, 0],
                "end": [300.5, 400.5, 0],
                "layer": "0"
            },
            {
                "object": "TEXT", 
                "insertion_pt": [150, 250, 0],
                "text_value": "Test Text",
                "height": Decimal("2.5")
            }
        ]
    }
    
    transformer = LibreDWGTransformer()
    result = transformer.transform(test_data)
    
    print("Transformed data:")
    print(json.dumps(result, indent=2))
    print("\nTransformation report:")
    print(json.dumps(transformer.get_transformation_report(), indent=2)) 