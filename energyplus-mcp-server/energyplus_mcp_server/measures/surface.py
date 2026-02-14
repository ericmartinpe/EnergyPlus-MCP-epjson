"""
Surface calculation measures for EnergyPlus models.

This module provides mixin class for calculating surface areas and properties,
including exterior wall areas and general surface area calculations.
"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SurfaceMeasures:
    """Mixin class for surface calculation measures"""
    
    def calculate_exterior_wall_area(self, epjson_path: str) -> str:
        """
        Calculate total above-ground exterior wall area
        
        Args:
            epjson_path: Path to the input epJSON or IDF file
        
        Returns:
            JSON string with total area and detailed wall information
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Calculating exterior wall area for: {resolved_path}")
            ep = self.load_json(resolved_path)
            
            wall_details = []
            total_area = 0.0
            
            # Get BuildingSurface:Detailed objects
            building_surfaces = ep.get("BuildingSurface:Detailed", {})
            
            for surf_name, surf_data in building_surfaces.items():
                surface_type = surf_data.get("surface_type", "").lower()
                outside_boundary = surf_data.get("outside_boundary_condition", "").lower()
                
                # Check if it's an exterior wall (above-grade)
                if surface_type == "wall" and outside_boundary == "outdoors":
                    # Calculate area from vertices using Shoelace formula
                    area = self._calculate_surface_area(surf_data)
                    
                    wall_info = {
                        "name": surf_name,
                        "area_m2": round(area, 4),
                        "area_ft2": round(area * 10.7639, 4),  # Convert m² to ft²
                        "construction": surf_data.get("construction_name", "Unknown"),
                        "zone": surf_data.get("zone_name", "Unknown"),
                        "sun_exposure": surf_data.get("sun_exposure", "Unknown"),
                        "wind_exposure": surf_data.get("wind_exposure", "Unknown")
                    }
                    
                    wall_details.append(wall_info)
                    total_area += area
            
            result = {
                "success": True,
                "file_path": resolved_path,
                "total_exterior_wall_area": {
                    "m2": round(total_area, 4),
                    "ft2": round(total_area * 10.7639, 4)
                },
                "total_walls": len(wall_details),
                "walls": wall_details
            }
            
            logger.info(f"Total exterior wall area: {total_area:.2f} m² ({total_area * 10.7639:.2f} ft²)")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error calculating exterior wall area for {resolved_path}: {e}")
            raise RuntimeError(f"Error calculating exterior wall area: {str(e)}")
    
    def _calculate_surface_area(self, surface_data: Dict[str, Any]) -> float:
        """
        Calculate surface area from vertices using the Shoelace formula
        
        Args:
            surface_data: Surface data dictionary containing vertices
        
        Returns:
            Area in square meters
        """
        try:
            # Handle two formats: array format and flat format
            vertices = surface_data.get("vertices", [])
            
            # If no vertices array, try flat format (vertex_1_x_coordinate, etc.)
            if not vertices:
                num_vertices = surface_data.get("number_of_vertices", 0)
                if num_vertices >= 3:
                    vertices = []
                    for i in range(1, num_vertices + 1):
                        vertex = {
                            "vertex_x_coordinate": surface_data.get(f"vertex_{i}_x_coordinate", 0.0),
                            "vertex_y_coordinate": surface_data.get(f"vertex_{i}_y_coordinate", 0.0),
                            "vertex_z_coordinate": surface_data.get(f"vertex_{i}_z_coordinate", 0.0)
                        }
                        vertices.append(vertex)
            
            if not vertices or len(vertices) < 3:
                logger.warning(f"Insufficient vertices to calculate area")
                return 0.0
            
            # Extract coordinates
            coords = []
            for vertex in vertices:
                x = vertex.get("vertex_x_coordinate", 0.0)
                y = vertex.get("vertex_y_coordinate", 0.0)
                z = vertex.get("vertex_z_coordinate", 0.0)
                coords.append((x, y, z))
            
            # Use Shoelace formula for polygon area in 3D space
            # First, find the normal vector to determine the plane
            if len(coords) < 3:
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
                # Vector from origin to current point
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
    
    def calculate_exterior_window_area(self, epjson_path: str) -> str:
        """
        Calculate total exterior window area
        
        Args:
            epjson_path: Path to the input epJSON or IDF file
        
        Returns:
            JSON string with total area and detailed window information
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Calculating exterior window area for: {resolved_path}")
            ep = self.load_json(resolved_path)
            
            # First, identify exterior building surfaces
            building_surfaces = ep.get("BuildingSurface:Detailed", {})
            exterior_surf_names = set()
            for surf_name, surf_data in building_surfaces.items():
                if surf_data.get("outside_boundary_condition", "").lower() == "outdoors":
                    exterior_surf_names.add(surf_name)
            
            window_details = []
            total_area = 0.0
            
            # Get FenestrationSurface:Detailed objects (windows)
            fenestration_surfaces = ep.get("FenestrationSurface:Detailed", {})
            
            for window_name, window_data in fenestration_surfaces.items():
                surface_type = window_data.get("surface_type", "").lower()
                building_surface_name = window_data.get("building_surface_name", "")
                
                # Check if it's a window on an exterior surface
                if surface_type == "window" and building_surface_name in exterior_surf_names:
                    # Calculate area from vertices
                    area = self._calculate_surface_area(window_data)
                    
                    window_info = {
                        "name": window_name,
                        "area_m2": round(area, 4),
                        "area_ft2": round(area * 10.7639, 4),  # Convert m² to ft²
                        "construction": window_data.get("construction_name", "Unknown"),
                        "building_surface": building_surface_name
                    }
                    
                    window_details.append(window_info)
                    total_area += area
            
            result = {
                "success": True,
                "file_path": resolved_path,
                "total_exterior_window_area": {
                    "m2": round(total_area, 4),
                    "ft2": round(total_area * 10.7639, 4)
                },
                "total_windows": len(window_details),
                "windows": window_details
            }
            
            logger.info(f"Total exterior window area: {total_area:.2f} m² ({total_area * 10.7639:.2f} ft²)")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error calculating exterior window area for {resolved_path}: {e}")
            raise RuntimeError(f"Error calculating exterior window area: {str(e)}")
    
    def calculate_window_to_wall_ratio(self, epjson_path: str) -> str:
        """
        Calculate window-to-wall ratio (WWR) by orientation and total building WWR
        
        Args:
            epjson_path: Path to the input epJSON or IDF file
        
        Returns:
            JSON string with WWR by orientation and total building WWR
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Calculating window-to-wall ratio for: {resolved_path}")
            ep = self.load_json(resolved_path)
            
            # Initialize dictionaries for wall and window areas by orientation
            wall_area_by_orientation = {
                "North": 0.0,
                "South": 0.0,
                "East": 0.0,
                "West": 0.0,
                "Other": 0.0
            }
            
            window_area_by_orientation = {
                "North": 0.0,
                "South": 0.0,
                "East": 0.0,
                "West": 0.0,
                "Other": 0.0
            }
            
            # Calculate wall areas by orientation
            building_surfaces = ep.get("BuildingSurface:Detailed", {})
            wall_details = {}
            
            for surf_name, surf_data in building_surfaces.items():
                surface_type = surf_data.get("surface_type", "").lower()
                outside_boundary = surf_data.get("outside_boundary_condition", "").lower()
                
                if surface_type == "wall" and outside_boundary == "outdoors":
                    area = self._calculate_surface_area(surf_data)
                    orientation = self._get_surface_orientation(surf_data)
                    
                    wall_area_by_orientation[orientation] += area
                    wall_details[surf_name] = {
                        "area": area,
                        "orientation": orientation
                    }
            
            # Get windows and their areas by orientation
            fenestration_surfaces = ep.get("FenestrationSurface:Detailed", {})
            window_details = {}
            
            for window_name, window_data in fenestration_surfaces.items():
                surface_type = window_data.get("surface_type", "").lower()
                building_surface_name = window_data.get("building_surface_name", "")
                
                if surface_type == "window" and building_surface_name in wall_details:
                    area = self._calculate_surface_area(window_data)
                    orientation = wall_details[building_surface_name]["orientation"]
                    
                    window_area_by_orientation[orientation] += area
                    window_details[window_name] = {
                        "area": area,
                        "orientation": orientation,
                        "parent_wall": building_surface_name
                    }
            
            # Calculate WWR by orientation
            wwr_by_orientation = {}
            for orientation in wall_area_by_orientation.keys():
                wall_area = wall_area_by_orientation[orientation]
                window_area = window_area_by_orientation[orientation]
                
                if wall_area > 0:
                    wwr = (window_area / wall_area) * 100
                else:
                    wwr = 0.0
                
                wwr_by_orientation[orientation] = {
                    "wall_area_m2": round(wall_area, 4),
                    "window_area_m2": round(window_area, 4),
                    "wwr_percent": round(wwr, 2)
                }
            
            # Calculate total building WWR
            total_wall_area = sum(wall_area_by_orientation.values())
            total_window_area = sum(window_area_by_orientation.values())
            
            if total_wall_area > 0:
                total_wwr = (total_window_area / total_wall_area) * 100
            else:
                total_wwr = 0.0
            
            result = {
                "success": True,
                "file_path": resolved_path,
                "total_building_wwr": {
                    "total_wall_area_m2": round(total_wall_area, 4),
                    "total_window_area_m2": round(total_window_area, 4),
                    "wwr_percent": round(total_wwr, 2)
                },
                "wwr_by_orientation": wwr_by_orientation,
                "summary": {
                    "total_walls": len(wall_details),
                    "total_windows": len(window_details)
                }
            }
            
            logger.info(f"Total building WWR: {total_wwr:.2f}%")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error calculating window-to-wall ratio for {resolved_path}: {e}")
            raise RuntimeError(f"Error calculating window-to-wall ratio: {str(e)}")
    
    def _get_surface_orientation(self, surface_data: Dict[str, Any]) -> str:
        """
        Determine the cardinal orientation of a surface based on its outward normal vector
        
        Args:
            surface_data: Surface data dictionary containing vertices
        
        Returns:
            Orientation as string: "North", "South", "East", "West", or "Other"
        """
        try:
            vertices = surface_data.get("vertices", [])
            
            if not vertices or len(vertices) < 3:
                return "Other"
            
            # Extract coordinates for first three vertices
            coords = []
            for i in range(min(3, len(vertices))):
                vertex = vertices[i]
                x = vertex.get("vertex_x_coordinate", 0.0)
                y = vertex.get("vertex_y_coordinate", 0.0)
                z = vertex.get("vertex_z_coordinate", 0.0)
                coords.append((x, y, z))
            
            # Calculate two edge vectors
            v1 = (coords[1][0] - coords[0][0], 
                  coords[1][1] - coords[0][1], 
                  coords[1][2] - coords[0][2])
            v2 = (coords[2][0] - coords[0][0], 
                  coords[2][1] - coords[0][1], 
                  coords[2][2] - coords[0][2])
            
            # Cross product to get outward normal vector
            # Assuming vertices are in counter-clockwise order when viewed from outside
            normal = (
                v1[1] * v2[2] - v1[2] * v2[1],
                v1[2] * v2[0] - v1[0] * v2[2],
                v1[0] * v2[1] - v1[1] * v2[0]
            )
            
            # Normalize
            magnitude = (normal[0]**2 + normal[1]**2 + normal[2]**2)**0.5
            if magnitude == 0:
                return "Other"
            
            normal = (normal[0]/magnitude, normal[1]/magnitude, normal[2]/magnitude)
            
            # Determine orientation based on the dominant horizontal component
            # EnergyPlus coordinate system: X=East, Y=North, Z=Up
            abs_x = abs(normal[0])
            abs_y = abs(normal[1])
            abs_z = abs(normal[2])
            
            # If mostly horizontal (vertical wall)
            if abs_z < 0.5:  # Not mostly pointing up or down
                if abs_x > abs_y:
                    # Predominantly East-West facing
                    if normal[0] > 0:
                        return "East"
                    else:
                        return "West"
                else:
                    # Predominantly North-South facing
                    if normal[1] > 0:
                        return "North"
                    else:
                        return "South"
            else:
                # Mostly roof or floor - not a typical wall orientation
                return "Other"
            
        except Exception as e:
            logger.warning(f"Error determining surface orientation: {e}")
            return "Other"
    
    def adjust_windows_for_target_wwr(self, epjson_path: str, target_wwr: float, 
                                      output_path: str = None, 
                                      by_orientation: bool = False,
                                      orientation_targets: Dict[str, float] = None) -> str:
        """
        Adjust window sizes to achieve a target window-to-wall ratio (WWR)
        
        Args:
            epjson_path: Path to the input epJSON or IDF file
            target_wwr: Target window-to-wall ratio as a percentage (e.g., 30 for 30%)
            output_path: Optional path to save the modified file. If None, overwrites the input file
            by_orientation: If True, apply target_wwr to each orientation independently
            orientation_targets: Optional dict mapping orientation to target WWR (e.g., {"North": 30, "South": 40})
        
        Returns:
            JSON string with adjustment results and new WWR values
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Adjusting windows for target WWR: {target_wwr}% in {resolved_path}")
            
            # Load the epJSON file
            ep = self.load_json(resolved_path)
            
            # Get current WWR data
            current_wwr_result = self.calculate_window_to_wall_ratio(epjson_path)
            current_wwr_data = json.loads(current_wwr_result)
            
            # Identify exterior building surfaces
            building_surfaces = ep.get("BuildingSurface:Detailed", {})
            exterior_surf_names = set()
            wall_details = {}
            
            for surf_name, surf_data in building_surfaces.items():
                surface_type = surf_data.get("surface_type", "").lower()
                outside_boundary = surf_data.get("outside_boundary_condition", "").lower()
                
                if surface_type == "wall" and outside_boundary == "outdoors":
                    exterior_surf_names.add(surf_name)
                    orientation = self._get_surface_orientation(surf_data)
                    wall_details[surf_name] = {
                        "orientation": orientation
                    }
            
            # Get fenestration surfaces and calculate scaling factors
            fenestration_surfaces = ep.get("FenestrationSurface:Detailed", {})
            windows_modified = 0
            modifications = []
            
            # Determine scaling factor for each window based on strategy
            if orientation_targets:
                # Use specific targets for each orientation
                scaling_factors = {}
                for orientation, target in orientation_targets.items():
                    current_data = current_wwr_data['wwr_by_orientation'].get(orientation, {})
                    current = current_data.get('wwr_percent', 0)
                    if current > 0:
                        scaling_factors[orientation] = (target / current) ** 0.5
                    else:
                        scaling_factors[orientation] = 0
                        
            elif by_orientation:
                # Apply same target to each orientation independently
                scaling_factors = {}
                for orientation in ["North", "South", "East", "West", "Other"]:
                    current_data = current_wwr_data['wwr_by_orientation'].get(orientation, {})
                    current = current_data.get('wwr_percent', 0)
                    if current > 0:
                        scaling_factors[orientation] = (target_wwr / current) ** 0.5
                    else:
                        scaling_factors[orientation] = 0
            else:
                # Global scaling based on total building WWR
                current_total_wwr = current_wwr_data['total_building_wwr']['wwr_percent']
                if current_total_wwr > 0:
                    global_scaling_factor = (target_wwr / current_total_wwr) ** 0.5
                else:
                    global_scaling_factor = 0
                scaling_factors = {orientation: global_scaling_factor 
                                 for orientation in ["North", "South", "East", "West", "Other"]}
            
            # Apply scaling to each window
            for window_name, window_data in fenestration_surfaces.items():
                surface_type = window_data.get("surface_type", "").lower()
                building_surface_name = window_data.get("building_surface_name", "")
                
                if surface_type == "window" and building_surface_name in wall_details:
                    orientation = wall_details[building_surface_name]["orientation"]
                    scaling_factor = scaling_factors.get(orientation, 1.0)
                    
                    if scaling_factor == 0:
                        logger.warning(f"Skipping {window_name}: scaling factor is 0")
                        continue
                    
                    # Get current window vertices and calculate centroid
                    num_vertices = window_data.get("number_of_vertices", 0)
                    if num_vertices < 3:
                        logger.warning(f"Skipping {window_name}: insufficient vertices")
                        continue
                    
                    # Calculate centroid
                    centroid_x = 0
                    centroid_y = 0
                    centroid_z = 0
                    
                    for i in range(1, num_vertices + 1):
                        centroid_x += window_data.get(f"vertex_{i}_x_coordinate", 0.0)
                        centroid_y += window_data.get(f"vertex_{i}_y_coordinate", 0.0)
                        centroid_z += window_data.get(f"vertex_{i}_z_coordinate", 0.0)
                    
                    centroid_x /= num_vertices
                    centroid_y /= num_vertices
                    centroid_z /= num_vertices
                    
                    # Scale each vertex from the centroid
                    for i in range(1, num_vertices + 1):
                        x = window_data.get(f"vertex_{i}_x_coordinate", 0.0)
                        y = window_data.get(f"vertex_{i}_y_coordinate", 0.0)
                        z = window_data.get(f"vertex_{i}_z_coordinate", 0.0)
                        
                        # Scale from centroid
                        new_x = centroid_x + (x - centroid_x) * scaling_factor
                        new_y = centroid_y + (y - centroid_y) * scaling_factor
                        new_z = centroid_z + (z - centroid_z) * scaling_factor
                        
                        window_data[f"vertex_{i}_x_coordinate"] = round(new_x, 6)
                        window_data[f"vertex_{i}_y_coordinate"] = round(new_y, 6)
                        window_data[f"vertex_{i}_z_coordinate"] = round(new_z, 6)
                    
                    windows_modified += 1
                    modifications.append({
                        "window": window_name,
                        "orientation": orientation,
                        "scaling_factor": round(scaling_factor, 4)
                    })
            
            # Save the modified file
            if output_path is None:
                output_path = resolved_path
            else:
                output_path = self._resolve_epjson_path(output_path)
            
            with open(output_path, 'w') as f:
                json.dump(ep, f, indent=2)
            
            logger.info(f"Modified {windows_modified} windows, saved to {output_path}")
            
            # Calculate new WWR
            new_wwr_result = self.calculate_window_to_wall_ratio(output_path)
            new_wwr_data = json.loads(new_wwr_result)
            
            result = {
                "success": True,
                "input_file": resolved_path,
                "output_file": output_path,
                "windows_modified": windows_modified,
                "target_wwr": target_wwr,
                "previous_wwr": current_wwr_data['total_building_wwr'],
                "new_wwr": new_wwr_data['total_building_wwr'],
                "previous_wwr_by_orientation": current_wwr_data['wwr_by_orientation'],
                "new_wwr_by_orientation": new_wwr_data['wwr_by_orientation'],
                "modifications": modifications
            }
            
            logger.info(f"New total building WWR: {new_wwr_data['total_building_wwr']['wwr_percent']:.2f}%")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error adjusting windows for target WWR: {e}")
            raise RuntimeError(f"Error adjusting windows: {str(e)}")
