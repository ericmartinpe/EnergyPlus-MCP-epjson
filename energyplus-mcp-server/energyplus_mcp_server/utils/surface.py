"""
Surface utility functions for EnergyPlus models.
Provides common surface filtering and extraction operations.
"""

import logging
from typing import Dict, List, Any, Set, Optional

logger = logging.getLogger(__name__)


def get_exterior_surface_names(
    epjson_data: Dict[str, Any], 
    surface_type: Optional[str] = None
) -> Set[str]:
    """
    Get names of all exterior building surfaces
    
    Args:
        epjson_data: The epJSON model dictionary
        surface_type: Optional filter by surface type ("Wall", "Roof", "Floor")
        
    Returns:
        Set of exterior surface names
    """
    exterior_surfaces = set()
    building_surfaces = epjson_data.get("BuildingSurface:Detailed", {})
    
    for surf_name, surf_data in building_surfaces.items():
        outside_boundary = surf_data.get("outside_boundary_condition", "").lower()
        
        if outside_boundary == "outdoors":
            if surface_type:
                surf_type = surf_data.get("surface_type", "").lower()
                if surf_type == surface_type.lower():
                    exterior_surfaces.add(surf_name)
            else:
                exterior_surfaces.add(surf_name)
    
    logger.debug(f"Found {len(exterior_surfaces)} exterior surfaces"
                 f"{f' of type {surface_type}' if surface_type else ''}")
    return exterior_surfaces


def get_exterior_surfaces_with_details(
    epjson_data: Dict[str, Any],
    surface_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get detailed information about exterior surfaces
    
    Args:
        epjson_data: The epJSON model dictionary
        surface_type: Optional filter by surface type ("Wall", "Roof", "Floor")
        
    Returns:
        List of dicts with surface name, type, construction, zone, etc.
    """
    surfaces = []
    building_surfaces = epjson_data.get("BuildingSurface:Detailed", {})
    
    for surf_name, surf_data in building_surfaces.items():
        surf_type = surf_data.get("surface_type", "").lower()
        outside_boundary = surf_data.get("outside_boundary_condition", "").lower()
        
        # Filter by type if specified
        if surface_type and surf_type != surface_type.lower():
            continue
            
        if outside_boundary == "outdoors":
            surfaces.append({
                "name": surf_name,
                "type": surf_type,
                "construction": surf_data.get("construction_name", ""),
                "zone": surf_data.get("zone_name", ""),
                "sun_exposure": surf_data.get("sun_exposure", ""),
                "wind_exposure": surf_data.get("wind_exposure", ""),
                "data": surf_data  # Include full data for further processing
            })
    
    logger.debug(f"Found {len(surfaces)} exterior surfaces with details")
    return surfaces


def get_fenestration_on_surfaces(
    epjson_data: Dict[str, Any],
    surface_names: Set[str],
    fenestration_type: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Get fenestration (windows/doors) on specific building surfaces
    
    Args:
        epjson_data: The epJSON model dictionary
        surface_names: Set of building surface names to check
        fenestration_type: Optional list of types to filter (e.g., ["window", "glassdoor"])
        
    Returns:
        List of dicts with fenestration name and data
    """
    if fenestration_type is None:
        fenestration_type = ["window", "glassdoor"]
    
    fenestration_list = []
    fenestration_surfaces = epjson_data.get("FenestrationSurface:Detailed", {})
    
    for fene_name, fene_data in fenestration_surfaces.items():
        surf_type = fene_data.get("surface_type", "").lower()
        building_surface_name = fene_data.get("building_surface_name", "")
        
        if surf_type in fenestration_type and building_surface_name in surface_names:
            fenestration_list.append({
                "name": fene_name,
                "type": surf_type,
                "parent_surface": building_surface_name,
                "construction": fene_data.get("construction_name", ""),
                "data": fene_data
            })
    
    logger.debug(f"Found {len(fenestration_list)} fenestration objects")
    return fenestration_list


def get_exterior_windows(
    epjson_data: Dict[str, Any],
    include_doors: bool = False
) -> List[Dict[str, Any]]:
    """
    Convenience function to get all exterior windows (and optionally glass doors)
    
    Args:
        epjson_data: The epJSON model dictionary
        include_doors: Whether to include glass doors
        
    Returns:
        List of window/door objects with metadata
    """
    exterior_surfaces = get_exterior_surface_names(epjson_data)
    
    fenestration_types = ["window"]
    if include_doors:
        fenestration_types.append("glassdoor")
    
    return get_fenestration_on_surfaces(
        epjson_data,
        exterior_surfaces,
        fenestration_types
    )


def get_construction_exterior_layers(
    epjson_data: Dict[str, Any],
    construction_names: Set[str]
) -> Dict[str, str]:
    """
    Get the exterior (outside) layer material names for given constructions
    
    Args:
        epjson_data: The epJSON model dictionary
        construction_names: Set of construction names to analyze
        
    Returns:
        Dict mapping construction name to exterior layer material name
    """
    exterior_layers = {}
    constructions = epjson_data.get("Construction", {})
    
    for const_name in construction_names:
        if const_name in constructions:
            const_data = constructions[const_name]
            # The outside layer is the first layer
            outside_layer = const_data.get("outside_layer", "")
            if outside_layer:
                exterior_layers[const_name] = outside_layer
    
    return exterior_layers
