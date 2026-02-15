"""
HVAC utility functions for EnergyPlus models.
Provides helpers for component iteration and node tracing.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def iter_numbered_components(
    obj_data: Dict[str, Any],
    name_field_pattern: str = "component_{}_name",
    type_field_pattern: str = "component_{}_object_type",
    max_count: int = 50
) -> List[Dict[str, str]]:
    """
    Iterate through numbered component fields in an EnergyPlus object
    
    Common in AirLoopHVAC:SupplyPath, AirLoopHVAC:ReturnPath, etc.
    
    Args:
        obj_data: Object data dictionary
        name_field_pattern: Pattern for name field (use {} for number)
        type_field_pattern: Pattern for type field (use {} for number)
        max_count: Maximum number to check
        
    Returns:
        List of dicts with 'name' and 'type' keys
    """
    components = []
    
    for i in range(1, max_count + 1):
        # Handle special case where first component might not have number
        if i == 1:
            name_field = name_field_pattern.replace("_{}", "_1").replace("{}", "1")
            type_field = type_field_pattern.replace("_{}", "_1").replace("{}", "1")
            
            # Also try without the number for the first component
            alt_name_field = name_field_pattern.replace("_{}", "").replace("{}", "")
            alt_type_field = type_field_pattern.replace("_{}", "").replace("{}", "")
            
            comp_name = obj_data.get(name_field) or obj_data.get(alt_name_field)
            comp_type = obj_data.get(type_field) or obj_data.get(alt_type_field)
        else:
            name_field = name_field_pattern.format(i)
            type_field = type_field_pattern.format(i)
            comp_name = obj_data.get(name_field)
            comp_type = obj_data.get(type_field)
        
        if not comp_name or not comp_type:
            break
        
        components.append({
            "name": comp_name,
            "type": comp_type
        })
    
    return components


def iter_numbered_nodes(
    obj_data: Dict[str, Any],
    node_field_pattern: str = "outlet_{}_node_name",
    max_count: int = 50
) -> List[str]:
    """
    Iterate through numbered node fields in an EnergyPlus object
    
    Common in AirLoopHVAC:ZoneSplitter, AirLoopHVAC:ZoneMixer, etc.
    
    Args:
        obj_data: Object data dictionary
        node_field_pattern: Pattern for node field (use {} for number)
        max_count: Maximum number to check
        
    Returns:
        List of node names
    """
    nodes = []
    
    for i in range(1, max_count + 1):
        # Handle special case where first node might not have number
        if i == 1:
            node_field = node_field_pattern.replace("_{}", "_1").replace("{}", "1")
            # Also try without the number for the first node
            alt_node_field = node_field_pattern.replace("_{}", "").replace("{}", "")
            node_name = obj_data.get(node_field) or obj_data.get(alt_node_field)
        else:
            node_field = node_field_pattern.format(i)
            node_name = obj_data.get(node_field)
        
        if not node_name:
            break
        
        nodes.append(node_name)
    
    return nodes
