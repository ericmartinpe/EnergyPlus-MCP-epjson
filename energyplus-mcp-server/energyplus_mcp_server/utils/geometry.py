"""
Geometry calculation utilities for EnergyPlus surfaces.
Handles surface area calculations and orientation determination.
"""

import logging
import math
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)


def extract_vertices(surface_data: Dict[str, Any]) -> List[Tuple[float, float, float]]:
    """
    Extract vertex coordinates from surface data, handling both epJSON formats
    
    Args:
        surface_data: Surface data dictionary containing vertices
        
    Returns:
        List of (x, y, z) coordinate tuples
    """
    vertices = []
    
    # Handle two formats: array format and flat format
    vertex_array = surface_data.get("vertices", [])
    
    if vertex_array:
        # Modern array format
        for vertex in vertex_array:
            x = vertex.get("vertex_x_coordinate", 0.0)
            y = vertex.get("vertex_y_coordinate", 0.0)
            z = vertex.get("vertex_z_coordinate", 0.0)
            vertices.append((x, y, z))
    else:
        # Legacy flat format (vertex_1_x_coordinate, etc.)
        num_vertices = surface_data.get("number_of_vertices", 0)
        for i in range(1, num_vertices + 1):
            x = surface_data.get(f"vertex_{i}_x_coordinate", 0.0)
            y = surface_data.get(f"vertex_{i}_y_coordinate", 0.0)
            z = surface_data.get(f"vertex_{i}_z_coordinate", 0.0)
            vertices.append((x, y, z))
    
    return vertices


def calculate_surface_area(surface_data: Dict[str, Any]) -> float:
    """
    Calculate surface area from vertices using the Shoelace formula in 3D
    
    Args:
        surface_data: Surface data dictionary containing vertices
    
    Returns:
        Area in square meters
    """
    try:
        coords = extract_vertices(surface_data)
        
        if not coords or len(coords) < 3:
            logger.warning("Insufficient vertices to calculate area")
            return 0.0
        
        # Calculate two edge vectors
        v1 = (coords[1][0] - coords[0][0], 
              coords[1][1] - coords[0][1], 
              coords[1][2] - coords[0][2])
        v2 = (coords[2][0] - coords[0][0], 
              coords[2][1] - coords[0][1], 
              coords[2][2] - coords[0][2])
        
        # Cross product to get normal vector
        normal = (
            v1[1] * v2[2] - v1[2] * v2[1],
            v1[2] * v2[0] - v1[0] * v2[2],
            v1[0] * v2[1] - v1[1] * v2[0]
        )
        
        # Calculate area using cross products of consecutive edges
        total_area = 0.0
        n = len(coords)
        
        for i in range(n):
            j = (i + 1) % n
            vi = coords[i]
            vj = coords[j]
            
            # Cross product
            cross = (
                vi[1] * vj[2] - vi[2] * vj[1],
                vi[2] * vj[0] - vi[0] * vj[2],
                vi[0] * vj[1] - vi[1] * vj[0]
            )
            
            # Dot product with normal
            total_area += (cross[0] * normal[0] + 
                          cross[1] * normal[1] + 
                          cross[2] * normal[2])
        
        # Magnitude of normal vector
        normal_mag = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
        
        if normal_mag == 0:
            return 0.0
        
        # Final area calculation
        area = abs(total_area) / (2.0 * normal_mag)
        return area
        
    except Exception as e:
        logger.warning(f"Error calculating surface area: {e}")
        return 0.0


def get_surface_orientation(
    surface_data: Dict[str, Any],
    north_axis: float = 0.0
) -> str:
    """
    Determine the cardinal orientation of a surface based on its outward normal vector
    
    Orientation ranges (accounting for building rotation):
    - North: 315° to 45° (wraps around 0°)
    - East: 45° to 135°
    - South: 135° to 225°
    - West: 225° to 315°
    
    Args:
        surface_data: Surface data dictionary containing vertices
        north_axis: Building north axis rotation in degrees (from Building object)
    
    Returns:
        Orientation as string: "North", "South", "East", "West", or "Other"
    """
    try:
        coords = extract_vertices(surface_data)
        
        if not coords or len(coords) < 3:
            return "Other"
        
        # Calculate two edge vectors
        v1 = (coords[1][0] - coords[0][0], 
              coords[1][1] - coords[0][1], 
              coords[1][2] - coords[0][2])
        v2 = (coords[2][0] - coords[0][0], 
              coords[2][1] - coords[0][1], 
              coords[2][2] - coords[0][2])
        
        # Cross product to get outward normal vector
        normal = (
            v1[1] * v2[2] - v1[2] * v2[1],
            v1[2] * v2[0] - v1[0] * v2[2],
            v1[0] * v2[1] - v1[1] * v2[0]
        )
        
        # Calculate magnitude
        magnitude = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
        if magnitude == 0:
            return "Other"
        
        # Check if mostly horizontal (vertical wall)
        abs_z = abs(normal[2])
        if abs_z / magnitude >= 0.5:
            # Mostly roof or floor
            return "Other"
        
        # Calculate azimuth angle from normal vector
        # EnergyPlus: X=East, Y=North, Z=Up
        # Azimuth: 0°=North, 90°=East, 180°=South, 270°=West
        azimuth_rad = math.atan2(normal[0], normal[1])
        azimuth_deg = math.degrees(azimuth_rad)
        
        # Normalize to 0-360
        if azimuth_deg < 0:
            azimuth_deg += 360
        
        # Apply building rotation
        azimuth_actual = (azimuth_deg + north_axis) % 360
        
        # Categorize into orientation ranges
        if azimuth_actual >= 315 or azimuth_actual < 45:
            return "North"
        elif 45 <= azimuth_actual < 135:
            return "East"
        elif 135 <= azimuth_actual < 225:
            return "South"
        elif 225 <= azimuth_actual < 315:
            return "West"
        else:
            return "Other"
        
    except Exception as e:
        logger.warning(f"Error determining surface orientation: {e}")
        return "Other"


def get_building_north_axis(epjson_data: Dict[str, Any]) -> float:
    """
    Extract building north axis rotation from epJSON data
    
    Args:
        epjson_data: The epJSON model dictionary
        
    Returns:
        North axis rotation in degrees (default 0.0)
    """
    building = epjson_data.get("Building", {})
    if building:
        building_name = list(building.keys())[0]
        return building[building_name].get("north_axis", 0.0)
    return 0.0


def scale_vertices_from_centroid(
    vertices: List[Tuple[float, float, float]],
    scale_factor: float
) -> List[Tuple[float, float, float]]:
    """
    Scale vertices from their centroid (for window resizing)
    
    Args:
        vertices: List of (x, y, z) coordinate tuples
        scale_factor: Linear scaling factor (e.g., 1.1 for 10% larger)
        
    Returns:
        List of scaled (x, y, z) coordinate tuples
    """
    if not vertices:
        return vertices
    
    # Calculate centroid
    n = len(vertices)
    centroid_x = sum(v[0] for v in vertices) / n
    centroid_y = sum(v[1] for v in vertices) / n
    centroid_z = sum(v[2] for v in vertices) / n
    
    # Scale each vertex from centroid
    scaled_vertices = []
    for x, y, z in vertices:
        new_x = centroid_x + (x - centroid_x) * scale_factor
        new_y = centroid_y + (y - centroid_y) * scale_factor
        new_z = centroid_z + (z - centroid_z) * scale_factor
        scaled_vertices.append((
            round(new_x, 6),
            round(new_y, 6),
            round(new_z, 6)
        ))
    
    return scaled_vertices


def update_surface_vertices(
    surface_data: Dict[str, Any],
    new_vertices: List[Tuple[float, float, float]]
) -> None:
    """
    Update surface vertices in place, handling both epJSON formats
    
    Args:
        surface_data: Surface data dictionary to modify
        new_vertices: List of new (x, y, z) coordinate tuples
    """
    # Check which format is being used
    if "vertices" in surface_data and isinstance(surface_data["vertices"], list):
        # Modern array format
        for i, (x, y, z) in enumerate(new_vertices):
            if i < len(surface_data["vertices"]):
                surface_data["vertices"][i]["vertex_x_coordinate"] = x
                surface_data["vertices"][i]["vertex_y_coordinate"] = y
                surface_data["vertices"][i]["vertex_z_coordinate"] = z
    else:
        # Legacy flat format
        for i, (x, y, z) in enumerate(new_vertices, start=1):
            surface_data[f"vertex_{i}_x_coordinate"] = x
            surface_data[f"vertex_{i}_y_coordinate"] = y
            surface_data[f"vertex_{i}_z_coordinate"] = z


def calculate_perimeter(surface_data: Dict[str, Any]) -> float:
    """
    Calculate the perimeter of a surface (e.g., window, wall) from its vertices
    
    Args:
        surface_data: Surface data dictionary containing vertices
        
    Returns:
        Perimeter in meters
    """
    try:
        vertices = extract_vertices(surface_data)
        
        if not vertices or len(vertices) < 2:
            logger.warning("Insufficient vertices to calculate perimeter")
            return 0.0
        
        perimeter = 0.0
        n = len(vertices)
        
        # Calculate distance between consecutive vertices
        for i in range(n):
            j = (i + 1) % n  # Wrap around to first vertex
            v1 = vertices[i]
            v2 = vertices[j]
            
            # Euclidean distance in 3D
            dx = v2[0] - v1[0]
            dy = v2[1] - v1[1]
            dz = v2[2] - v1[2]
            distance = math.sqrt(dx**2 + dy**2 + dz**2)
            
            perimeter += distance
        
        return perimeter
        
    except Exception as e:
        logger.warning(f"Error calculating perimeter: {e}")
        return 0.0


def calculate_wall_roof_intersection_length(epjson_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate the length of wall-roof intersections in the building
    
    This function identifies where exterior walls meet exterior roofs and calculates
    the total length of these intersections. Useful for analyzing roof-wall junctions,
    parapets, and thermal bridging.
    
    Args:
        epjson_data: The epJSON model dictionary
        
    Returns:
        Dictionary containing:
            - total_length: Total length of all wall-roof intersections (meters)
            - intersections: List of individual intersection segments with details
    """
    try:
        building_surfaces = epjson_data.get("BuildingSurface:Detailed", {})
        
        # Identify exterior walls and roofs
        walls = {}
        roofs = {}
        
        for surf_name, surf_data in building_surfaces.items():
            surface_type = surf_data.get("surface_type", "").lower()
            outside_boundary = surf_data.get("outside_boundary_condition", "").lower()
            
            if outside_boundary == "outdoors":
                vertices = extract_vertices(surf_data)
                if surface_type == "wall":
                    walls[surf_name] = {
                        "data": surf_data,
                        "vertices": vertices
                    }
                elif surface_type == "roof":
                    roofs[surf_name] = {
                        "data": surf_data,
                        "vertices": vertices
                    }
        
        # Find shared edges between walls and roofs
        intersections = []
        total_length = 0.0
        tolerance = 0.01  # 1 cm tolerance for matching vertices
        
        for wall_name, wall_info in walls.items():
            wall_vertices = wall_info["vertices"]
            
            for roof_name, roof_info in roofs.items():
                roof_vertices = roof_info["vertices"]
                
                # Check each edge of the wall against each edge of the roof
                for i in range(len(wall_vertices)):
                    j = (i + 1) % len(wall_vertices)
                    wall_edge = (wall_vertices[i], wall_vertices[j])
                    
                    for k in range(len(roof_vertices)):
                        l = (k + 1) % len(roof_vertices)
                        roof_edge = (roof_vertices[k], roof_vertices[l])
                        
                        # Check if edges share two vertices (same edge)
                        # Edge can be in same or opposite direction
                        match1 = (_vertices_match(wall_edge[0], roof_edge[0], tolerance) and
                                 _vertices_match(wall_edge[1], roof_edge[1], tolerance))
                        match2 = (_vertices_match(wall_edge[0], roof_edge[1], tolerance) and
                                 _vertices_match(wall_edge[1], roof_edge[0], tolerance))
                        
                        if match1 or match2:
                            # Calculate edge length
                            dx = wall_edge[1][0] - wall_edge[0][0]
                            dy = wall_edge[1][1] - wall_edge[0][1]
                            dz = wall_edge[1][2] - wall_edge[0][2]
                            length = math.sqrt(dx**2 + dy**2 + dz**2)
                            
                            intersections.append({
                                "wall_name": wall_name,
                                "roof_name": roof_name,
                                "length_m": round(length, 4),
                                "start_vertex": {
                                    "x": round(wall_edge[0][0], 3),
                                    "y": round(wall_edge[0][1], 3),
                                    "z": round(wall_edge[0][2], 3)
                                },
                                "end_vertex": {
                                    "x": round(wall_edge[1][0], 3),
                                    "y": round(wall_edge[1][1], 3),
                                    "z": round(wall_edge[1][2], 3)
                                }
                            })
                            total_length += length
        
        result = {
            "total_length_m": round(total_length, 4),
            "total_length_ft": round(total_length * 3.28084, 4),
            "num_intersections": len(intersections),
            "intersections": intersections
        }
        
        logger.info(f"Found {len(intersections)} wall-roof intersections, total length: {total_length:.2f} m")
        return result
        
    except Exception as e:
        logger.error(f"Error calculating wall-roof intersections: {e}")
        raise RuntimeError(f"Error calculating wall-roof intersections: {str(e)}")


def _vertices_match(v1: Tuple[float, float, float], v2: Tuple[float, float, float], 
                   tolerance: float = 0.01) -> bool:
    """
    Helper function to check if two vertices match within a tolerance
    
    Args:
        v1: First vertex (x, y, z)
        v2: Second vertex (x, y, z)
        tolerance: Distance tolerance in meters
        
    Returns:
        True if vertices match within tolerance
    """
    dx = v1[0] - v2[0]
    dy = v1[1] - v2[1]
    dz = v1[2] - v2[2]
    distance = math.sqrt(dx**2 + dy**2 + dz**2)
    return distance <= tolerance
