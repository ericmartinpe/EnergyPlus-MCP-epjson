"""
Surface calculation measures for EnergyPlus models.

This module provides mixin class for calculating surface areas and properties,
including exterior wall areas and general surface area calculations.
"""

import json
import logging
from typing import Dict, Any

from ..utils.geometry import (
    calculate_surface_area,
    get_surface_orientation,
    get_building_north_axis,
    extract_vertices,
    scale_vertices_from_centroid,
    update_surface_vertices
)
from ..utils.surface import get_exterior_surface_names

logger = logging.getLogger(__name__)


class SurfaceMeasures:
    """Mixin class for surface calculation measures"""
    
    def calculate_exterior_wall_area(self, epjson_data: Dict[str, Any]) -> str:
        """
        Calculate total above-ground exterior wall area
        
        Args:
            epjson_data: Loaded epJSON data as a dictionary
        
        Returns:
            JSON string with total area and detailed wall information
        """
        try:
            logger.info("Calculating exterior wall area")
            ep = epjson_data
            
            wall_details = []
            total_area = 0.0
            
            # Get BuildingSurface:Detailed objects
            building_surfaces = ep.get("BuildingSurface:Detailed", {})
            
            for surf_name, surf_data in building_surfaces.items():
                surface_type = surf_data.get("surface_type", "").lower()
                outside_boundary = surf_data.get("outside_boundary_condition", "").lower()
                
                # Check if it's an exterior wall (above-grade)
                if surface_type == "wall" and outside_boundary == "outdoors":
                    # Calculate area from vertices using utility function
                    area = calculate_surface_area(surf_data)
                    
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
            logger.error(f"Error calculating exterior wall area: {e}")
            raise RuntimeError(f"Error calculating exterior wall area: {str(e)}")
    
    def calculate_exterior_window_area(self, epjson_data: Dict[str, Any]) -> str:
        """
        Calculate total exterior window area
        
        Args:
            epjson_data: Loaded epJSON data as a dictionary
        
        Returns:
            JSON string with total area and detailed window information
        """
        try:
            logger.info("Calculating exterior window area")
            ep = epjson_data
            
            # Use utility function to identify exterior building surfaces
            exterior_surf_names = get_exterior_surface_names(ep)
            
            window_details = []
            total_area = 0.0
            
            # Get FenestrationSurface:Detailed objects (windows)
            fenestration_surfaces = ep.get("FenestrationSurface:Detailed", {})
            
            for window_name, window_data in fenestration_surfaces.items():
                surface_type = window_data.get("surface_type", "").lower()
                building_surface_name = window_data.get("building_surface_name", "")
                
                # Check if it's a window or glass door on an exterior surface
                if surface_type in ["window", "glassdoor"] and building_surface_name in exterior_surf_names:
                    # Calculate area from vertices using utility function
                    area = calculate_surface_area(window_data)
                    
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
            logger.error(f"Error calculating exterior window area: {e}")
            raise RuntimeError(f"Error calculating exterior window area: {str(e)}")
    
    def calculate_window_to_wall_ratio(self, epjson_data: Dict[str, Any]) -> str:
        """
        Calculate window-to-wall ratio (WWR) by orientation and total building WWR
        
        Args:
            epjson_data: Loaded epJSON data as a dictionary
        
        Returns:
            JSON string with WWR by orientation and total building WWR
        """
        try:
            logger.info("Calculating window-to-wall ratio")
            ep = epjson_data
            
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
                    area = calculate_surface_area(surf_data)
                    orientation = get_surface_orientation(surf_data, get_building_north_axis(ep))
                    
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
                
                # Include both windows and glass doors in WWR calculation
                if surface_type in ["window", "glassdoor"] and building_surface_name in wall_details:
                    area = calculate_surface_area(window_data)
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
            logger.error(f"Error calculating window-to-wall ratio: {e}")
            raise RuntimeError(f"Error calculating window-to-wall ratio: {str(e)}")
    
    def adjust_windows_for_target_wwr(self, epjson_data: Dict[str, Any], target_wwr: float, 
                                      by_orientation: bool = False,
                                      orientation_targets: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Adjust window sizes to achieve a target window-to-wall ratio (WWR)
        
        Args:
            epjson_data: Loaded epJSON data as a dictionary (will be modified in place)
            target_wwr: Target window-to-wall ratio as a percentage (e.g., 30 for 30%) or fraction (0.30 for 30%)
            by_orientation: If True, apply target_wwr to each orientation independently
            orientation_targets: Optional dict mapping orientation to target WWR (e.g., {"North": 30, "South": 40})
        
        Returns:
            Modified epJSON dict (same as input but with adjusted windows)
        """
        try:
            # Normalize target_wwr: if > 1, assume it's a percentage and convert to fraction
            if target_wwr > 1.0:
                target_wwr = target_wwr / 100.0
                logger.info(f"Adjusting windows for target WWR: {target_wwr * 100:.1f}%")
            else:
                logger.info(f"Adjusting windows for target WWR: {target_wwr * 100:.1f}%")
            
            # Normalize orientation_targets if provided
            if orientation_targets:
                orientation_targets = {
                    k: (v / 100.0 if v > 1.0 else v) 
                    for k, v in orientation_targets.items()
                }
            
            ep = epjson_data
            
            # Get current WWR data
            current_wwr_result = self.calculate_window_to_wall_ratio(ep)
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
                    orientation = get_surface_orientation(surf_data, get_building_north_axis(ep))
                    wall_area = calculate_surface_area(surf_data)
                    wall_details[surf_name] = {
                        "orientation": orientation,
                        "area": wall_area
                    }
            
            # Get fenestration surfaces and calculate scaling factors
            fenestration_surfaces = ep.get("FenestrationSurface:Detailed", {})
            windows_modified = 0
            modifications = []
            
            # Determine scaling factor for each window based on strategy
            if orientation_targets:
                # Use specific targets for each orientation
                # Account for glass doors in each orientation
                scaling_factors = {}
                for orientation, target in orientation_targets.items():
                    current_data = current_wwr_data['wwr_by_orientation'].get(orientation, {})
                    wall_area = current_data.get('wall_area_m2', 0)
                    total_fenestration = current_data.get('window_area_m2', 0)
                    
                    # Calculate window vs door area for this orientation
                    window_area = 0.0
                    door_area = 0.0
                    for window_name, window_data in fenestration_surfaces.items():
                        surface_type = window_data.get("surface_type", "").lower()
                        building_surface_name = window_data.get("building_surface_name", "")
                        if building_surface_name in wall_details:
                            if wall_details[building_surface_name]["orientation"] == orientation:
                                area = calculate_surface_area(window_data)
                                if surface_type == "window":
                                    window_area += area
                                elif surface_type == "glassdoor":
                                    door_area += area
                    
                    # Calculate target areas for this orientation
                    target_total = wall_area * target
                    target_windows = target_total - door_area
                    
                    if window_area > 0 and target_windows > 0:
                        scaling_factors[orientation] = (target_windows / window_area) ** 0.5
                    else:
                        scaling_factors[orientation] = 0
                        
            elif by_orientation:
                # Apply same target to each orientation independently
                # Need to account for glass doors in each orientation
                scaling_factors = {}
                for orientation in ["North", "South", "East", "West", "Other"]:
                    current_data = current_wwr_data['wwr_by_orientation'].get(orientation, {})
                    wall_area = current_data.get('wall_area_m2', 0)
                    total_fenestration = current_data.get('window_area_m2', 0)
                    
                    # Calculate window vs door area for this orientation
                    window_area = 0.0
                    door_area = 0.0
                    for window_name, window_data in fenestration_surfaces.items():
                        surface_type = window_data.get("surface_type", "").lower()
                        building_surface_name = window_data.get("building_surface_name", "")
                        if building_surface_name in wall_details:
                            if wall_details[building_surface_name]["orientation"] == orientation:
                                area = calculate_surface_area(window_data)
                                if surface_type == "window":
                                    window_area += area
                                elif surface_type == "glassdoor":
                                    door_area += area
                    
                    # Calculate target areas for this orientation
                    target_total = wall_area * target_wwr
                    target_windows = target_total - door_area
                    
                    if window_area > 0 and target_windows > 0:
                        scaling_factors[orientation] = (target_windows / window_area) ** 0.5
                    else:
                        scaling_factors[orientation] = 0
            else:
                # Global scaling based on total building WWR
                # Need to account for glass doors which are included in WWR but not scaled
                total_wall_area = current_wwr_data['total_building_wwr']['total_wall_area_m2']
                total_fenestration_area = current_wwr_data['total_building_wwr']['total_window_area_m2']
                
                # Calculate current window area (excluding glass doors)
                current_window_area = 0.0
                current_door_area = 0.0
                for window_name, window_data in fenestration_surfaces.items():
                    surface_type = window_data.get("surface_type", "").lower()
                    building_surface_name = window_data.get("building_surface_name", "")
                    if building_surface_name in wall_details:
                        area = calculate_surface_area(window_data)
                        if surface_type == "window":
                            current_window_area += area
                        elif surface_type == "glassdoor":
                            current_door_area += area
                
                # Calculate target areas
                target_total_fenestration = total_wall_area * target_wwr
                target_window_area = target_total_fenestration - current_door_area
                
                # Calculate scaling factor for windows only
                if current_window_area > 0 and target_window_area > 0:
                    global_scaling_factor = (target_window_area / current_window_area) ** 0.5
                else:
                    global_scaling_factor = 0
                    
                scaling_factors = {orientation: global_scaling_factor 
                                 for orientation in ["North", "South", "East", "West", "Other"]}
            
            # Apply scaling to each window (not glass doors - they stay fixed)
            for window_name, window_data in fenestration_surfaces.items():
                surface_type = window_data.get("surface_type", "").lower()
                building_surface_name = window_data.get("building_surface_name", "")
                
                # Only scale windows, not glass doors (glass doors are included in WWR calc but not adjusted)
                if surface_type == "window" and building_surface_name in wall_details:
                    orientation = wall_details[building_surface_name]["orientation"]
                    wall_area = wall_details[building_surface_name]["area"]
                    current_window_area = calculate_surface_area(window_data)
                    
                    # Get initial scaling factor
                    scaling_factor = scaling_factors.get(orientation, 1.0)
                    
                    if scaling_factor == 0:
                        logger.warning(f"Skipping {window_name}: scaling factor is 0")
                        continue
                    
                    # Check if scaled window would exceed wall area (use 95% as safe maximum)
                    # Area scales with square of linear scaling factor
                    proposed_window_area = current_window_area * (scaling_factor ** 2)
                    max_window_area = wall_area * 0.95  # 95% maximum to leave room for frame/edge clearance
                    
                    if proposed_window_area > max_window_area:
                        # Cap the scaling factor to stay within safe limits
                        max_scaling_factor = (max_window_area / current_window_area) ** 0.5
                        logger.warning(
                            f"Window {window_name} on wall {building_surface_name}: "
                            f"scaling factor {scaling_factor:.3f} would create window larger than wall. "
                            f"Capping at {max_scaling_factor:.3f} (95% of wall area)"
                        )
                        scaling_factor = max_scaling_factor
                    
                    # Use geometry utilities to scale vertices from centroid
                    current_vertices = extract_vertices(window_data)
                    
                    if not current_vertices or len(current_vertices) < 3:
                        logger.warning(f"Skipping {window_name}: insufficient vertices")
                        continue
                    
                    # Scale vertices from centroid
                    scaled_vertices = scale_vertices_from_centroid(current_vertices, scaling_factor)
                    
                    # Update window data with scaled vertices
                    update_surface_vertices(window_data, scaled_vertices)
                    
                    windows_modified += 1
                    modifications.append({
                        "window": window_name,
                        "orientation": orientation,
                        "scaling_factor": round(scaling_factor, 4)
                    })
            
            logger.info(f"Modified {windows_modified} windows")
            
            # Return the modified epJSON dict
            return ep
            
        except Exception as e:
            logger.error(f"Error adjusting windows for target WWR: {e}")
            raise RuntimeError(f"Error adjusting windows: {str(e)}")
