"""
Building envelope measures for EnergyPlus models.

This module provides mixin class for modifying building envelope components,
including exterior walls, windows, and infiltration rates.
"""

import os
import json
import logging
import string
import random
from typing import Dict, List, Any, Optional
from pathlib import Path

from ..utils.construction import set_construction_ufactor

# Define DATA_PATH for internal use
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'data')

logger = logging.getLogger(__name__)


class EnvelopeMeasures:
    """Mixin class for building envelope measures"""
    
    def find_exterior_walls(self, epjson_data: Dict[str, Any]) -> dict:
        """
        Creates a dictionary of exterior walls in the model
        
        Args:
            epjson_data: The epJSON model dictionary
        
        Returns:
            Dictionary of all exterior walls in the model - wall names are keys, constructions are values.
        """
        try:
            ep = epjson_data

            ext_walls = {}
            # Get BuildingSurface:Detailed objects
            building_surfaces = ep.get("BuildingSurface:Detailed", {})
            for surf_name, surf_data in building_surfaces.items():
                surface_type = surf_data.get("surface_type", "").lower()
                outside_boundary = surf_data.get("outside_boundary_condition", "").lower()
                
                if surface_type == "wall" and outside_boundary == "outdoors":
                    ext_walls[surf_name] = surf_data.get("construction_name", "")
            
            return ext_walls
            
        except Exception as e:
            logger.error(f"Error finding exterior walls: {e}")
            raise RuntimeError(f"Error finding exterior walls: {str(e)}")

    def set_exterior_wall_construction(self, ep: Dict[str, Any], wall_type: str, code_version: str, 
                                      climate_zone: str, wall_list: Optional[List[str]] = None, 
                                      use_type: str = "non_residential") -> Dict[str, Any]:
        """
        Set exterior wall construction material layers for a wall type with code-compliant U-factor.
        
        NOTE: This is a low-level method that operates on an already-loaded epJSON dictionary.
        For MCP tool calls, use the wrapper function which automatically handles IDF conversion.
        
        This method:
        1. Loads construction definitions and material properties from data files
        2. Creates/adds all required materials to the epJSON model
        3. Creates the construction with proper layer sequence
        4. Adjusts insulation R-value to meet code-required U-factor
        5. Optionally assigns construction to specified walls

        Args:
            ep: epJSON model dictionary (modified in-place)
            wall_type: Type of wall construction. Options: ["MassWall", "MetalBuildingWall", 
                      "SteelFramedWall", "WoodFramedWall", "BelowGradeWall"]
            code_version: Energy code version (e.g., "90.1-2019")
            climate_zone: ASHRAE climate zone (e.g., "5A")
            wall_list: Optional list of wall names to assign this construction
            use_type: Space use type. Options: ["non_residential", "residential", "semiheated"]
                     (default: "non_residential")
        
        Returns:
            The modified epJSON dictionary (same as input, modified in-place)
            
        Raises:
            KeyError: If wall_type, code_version, or climate_zone not found in data files
            RuntimeError: If required data files cannot be loaded            
        """
        # Constants for default insulation material properties
        DEFAULT_INSULATION_PROPERTIES = {
            "roughness": "MediumSmooth",
            "solar_absorptance": 0.7,
            "thermal_absorptance": 0.9,
            "thermal_resistance": 2.368,  # Placeholder - will be adjusted to meet U-factor
            "visible_absorptance": 0.7
        }
        
        # Validate inputs
        VALID_WALL_TYPES = ["MassWall", "MetalBuildingWall", "SteelFramedWall", "WoodFramedWall", "BelowGradeWall"]
        VALID_USE_TYPES = ["non_residential", "residential", "semiheated"]
        
        if wall_type not in VALID_WALL_TYPES:
            raise ValueError(f"Invalid wall_type '{wall_type}'. Must be one of: {VALID_WALL_TYPES}")
        if use_type not in VALID_USE_TYPES:
            raise ValueError(f"Invalid use_type '{use_type}'. Must be one of: {VALID_USE_TYPES}")
        
        # Determine prefix for U-factor lookup
        prefix = "nonres" if "non_" in use_type else "res"
        
        # Load configuration and data files
        try:
            construction_map = self.load_json(os.path.join(DATA_PATH, "construction_map.json"))
            constructions = self.load_json(os.path.join(DATA_PATH, "constructions.json"))
            materials_dict = self.load_json(os.path.join(DATA_PATH, "materials.json"))
            opaque_wall_values = self.load_json(os.path.join(DATA_PATH, "opaque_wall_values.json"))
        except FileNotFoundError as e:
            raise RuntimeError(f"Required data file not found: {e}")
        
        # Get construction metadata
        try:
            construction_name = construction_map["exterior_wall"][use_type]["construction_name"]
            insulation_layer_name = construction_map["exterior_wall"][use_type]["insulation_layer_name"]
            construction_material_dict = constructions["exterior_wall"][use_type][wall_type]
            ext_wall_ufactor = opaque_wall_values[code_version][wall_type][climate_zone][prefix]
        except KeyError as e:
            raise KeyError(f"Configuration not found in data files: {e}. Check wall_type, code_version, climate_zone, and use_type.")
        
        # Initialize material and construction containers if needed
        if "Material" not in ep:
            ep["Material"] = {}
        if "Material:NoMass" not in ep:
            ep["Material:NoMass"] = {}
        if "Construction" not in ep:
            ep["Construction"] = {}
        
        # Add materials to epJSON model
        for layer_name, material_name in construction_material_dict.items():
            if material_name == insulation_layer_name:
                # Create insulation material on-the-fly (R-value will be adjusted later)
                # Using Material:NoMass since we'll specify thermal resistance directly
                ep["Material:NoMass"][material_name] = DEFAULT_INSULATION_PROPERTIES.copy()
                logger.debug(f"Created insulation material '{material_name}' with placeholder R-value")
            else:
                # Add material from materials library
                if material_name not in materials_dict:
                    logger.warning(f"Material '{material_name}' not found in materials.json, skipping")
                    continue
                
                # Add to appropriate material type (Material or Material:NoMass)
                # Determine type based on material properties
                material_data = materials_dict[material_name]
                if "thermal_resistance" in material_data:
                    ep["Material:NoMass"][material_name] = material_data
                else:
                    ep["Material"][material_name] = material_data
                
                logger.debug(f"Added material '{material_name}' from library")
        
        # Create construction with material layers
        ep["Construction"][construction_name] = construction_material_dict
        logger.debug(f"Created construction '{construction_name}' with {len(construction_material_dict)} layers")
        
        # Adjust insulation R-value to meet code-required U-factor
        ep = set_construction_ufactor(ep, ext_wall_ufactor, construction_name)
        logger.info(f"Adjusted '{construction_name}' to meet U-factor: {ext_wall_ufactor} Btu/h·ft²·°F")
        
        # Assign construction to specified walls
        if wall_list:
            if "BuildingSurface:Detailed" not in ep:
                logger.warning("No BuildingSurface:Detailed objects found in model, cannot assign construction")
            else:
                assigned_count = 0
                for wall_name in wall_list:
                    if wall_name in ep["BuildingSurface:Detailed"]:
                        ep["BuildingSurface:Detailed"][wall_name]["construction_name"] = construction_name
                        assigned_count += 1
                    else:
                        logger.warning(f"Wall '{wall_name}' not found in BuildingSurface:Detailed")
                logger.info(f"Assigned construction to {assigned_count}/{len(wall_list)} walls")
        
        return ep

    def add_coating_outside(self, epjson_data: Dict[str, Any], location: str, solar_abs: float = 0.4, 
                            thermal_abs: float = 0.9) -> Dict[str, Any]:
        """
        Add exterior coating to all exterior surfaces of the specified location (wall or roof)
        
        Args:
            epjson_data: The epJSON model dictionary
            location: Surface location - either "wall" or "roof"
            solar_abs: Solar Absorptance of the exterior coating (default: 0.4)
            thermal_abs: Thermal Absorptance of the exterior coating (default: 0.9)
        
        Returns:
            The modified epJSON dictionary
        """
        modifications_made = []

        try:
            ep = epjson_data
            
            # Validate location parameter
            location_lower = location.lower()
            if location_lower not in ["wall", "roof"]:
                raise ValueError(f"Location must be 'wall' or 'roof', got '{location}'")
            
            # Collect all surfaces of the specified type
            all_surfs = []
            
            # Get BuildingSurface:Detailed objects
            building_surfaces = ep.get("BuildingSurface:Detailed", {})
            for surf_name, surf_data in building_surfaces.items():
                surface_type = surf_data.get("surface_type", "").lower()
                outside_boundary = surf_data.get("outside_boundary_condition", "").lower()
                
                if surface_type == location_lower and outside_boundary == "outdoors":
                    all_surfs.append({
                        "name": surf_name,
                        "construction_name": surf_data.get("construction_name", "")
                    })
            
            logger.debug(f"Found {len(all_surfs)} exterior {location} surfaces")
            
            # Get unique construction names from surfaces
            construction_names = set(surf["construction_name"] for surf in all_surfs if surf["construction_name"])
            
            # Get exterior layer names from constructions
            constructions = ep.get("Construction", {})
            ext_layer_names = set()
            for const_name in construction_names:
                if const_name in constructions:
                    const_data = constructions[const_name]
                    # The outside layer is the first layer
                    outside_layer = const_data.get("outside_layer", "")
                    if outside_layer:
                        ext_layer_names.add(outside_layer)
            
            logger.debug(f"Construction names: {construction_names}")
            logger.debug(f"Exterior layer names: {ext_layer_names}")
            
            # Modify material properties for exterior layers
            materials = ep.get("Material", {})
            materials_no_mass = ep.get("Material:NoMass", {})
            
            for layer_name in ext_layer_names:
                # Check in regular materials
                if layer_name in materials:
                    material = materials[layer_name]
                    old_solar = material.get("solar_absorptance", "Not set")
                    old_thermal = material.get("thermal_absorptance", "Not set")
                    
                    material["solar_absorptance"] = solar_abs
                    material["thermal_absorptance"] = thermal_abs
                    
                    modifications_made.append({
                        "layer": layer_name,
                        "field": "solar_absorptance",
                        "old_value": old_solar,
                        "new_value": solar_abs
                    })
                    modifications_made.append({
                        "layer": layer_name,
                        "field": "thermal_absorptance",
                        "old_value": old_thermal,
                        "new_value": thermal_abs
                    })
                    logger.debug(f"Modified material '{layer_name}'")
                
                # Check in no-mass materials
                elif layer_name in materials_no_mass:
                    material = materials_no_mass[layer_name]
                    old_solar = material.get("solar_absorptance", "Not set")
                    old_thermal = material.get("thermal_absorptance", "Not set")
                    
                    material["solar_absorptance"] = solar_abs
                    material["thermal_absorptance"] = thermal_abs
                    
                    modifications_made.append({
                        "layer": layer_name,
                        "field": "solar_absorptance",
                        "old_value": old_solar,
                        "new_value": solar_abs
                    })
                    modifications_made.append({
                        "layer": layer_name,
                        "field": "thermal_absorptance",
                        "old_value": old_thermal,
                        "new_value": thermal_abs
                    })
                    logger.debug(f"Modified no-mass material '{layer_name}'")

            logger.info(f"Successfully modified exterior coating for {len(ext_layer_names)} materials")
            return ep
            
        except Exception as e:
            logger.error(f"Error modifying exterior coating: {e}")
            raise RuntimeError(f"Error modifying exterior coating: {str(e)}")

    def add_window_film_outside(self, epjson_data: Dict[str, Any], u_value: float = 4.94, shgc: float = 0.45, 
                                visible_transmittance: float = 0.66) -> Dict[str, Any]:
        """
        Add window film to exterior windows using WindowMaterial:SimpleGlazingSystem
        
        Args:
            epjson_data: The epJSON model dictionary
            u_value: U-factor of the window film (default: 4.94 W/m²-K from CBES)
            shgc: Solar Heat Gain Coefficient (default: 0.45 from CBES)
            visible_transmittance: Visible transmittance (default: 0.66 from CBES)
        
        Returns:
            The modified epJSON dictionary
        """
        modifications_made = []

        try:
            ep = epjson_data
            
            # Find all exterior window surfaces
            # First, identify exterior building surfaces
            building_surfaces = ep.get("BuildingSurface:Detailed", {})
            exterior_surf_names = set()
            for surf_name, surf_data in building_surfaces.items():
                if surf_data.get("outside_boundary_condition", "").lower() == "outdoors":
                    exterior_surf_names.add(surf_name)
            
            logger.debug(f"Found {len(exterior_surf_names)} exterior building surfaces")
            
            # Find windows on exterior surfaces
            ext_window_surfs = []
            fenestration_surfaces = ep.get("FenestrationSurface:Detailed", {})
            for window_name, window_data in fenestration_surfaces.items():
                if window_data.get("surface_type", "").lower() == "window":
                    building_surface_name = window_data.get("building_surface_name", "")
                    if building_surface_name in exterior_surf_names:
                        ext_window_surfs.append({
                            "name": window_name,
                            "data": window_data
                        })
            
            logger.debug(f"Found {len(ext_window_surfs)} exterior window surfaces")
            
            if not ext_window_surfs:
                logger.warning("No exterior windows found in the model")
                return ep
            
            # Create unique window film material name
            random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            window_film_name = f'outside_window_film_{random_suffix}'
            
            # Add WindowMaterial:SimpleGlazingSystem for the window film
            if "WindowMaterial:SimpleGlazingSystem" not in ep:
                ep["WindowMaterial:SimpleGlazingSystem"] = {}
            
            ep["WindowMaterial:SimpleGlazingSystem"][window_film_name] = {
                "u_factor": u_value,
                "solar_heat_gain_coefficient": shgc,
                "visible_transmittance": visible_transmittance
            }
            logger.debug(f"Created window film material: {window_film_name}")
            
            # Create construction using the window film
            window_film_construction_name = f'cons_{window_film_name}'
            if "Construction" not in ep:
                ep["Construction"] = {}
            
            ep["Construction"][window_film_construction_name] = {
                "outside_layer": window_film_name
            }
            logger.debug(f"Created window film construction: {window_film_construction_name}")
            
            # Apply the window film construction to all exterior windows
            for window_info in ext_window_surfs:
                window_name = window_info["name"]
                window_data = window_info["data"]
                
                old_construction = window_data.get("construction_name", "Not set")
                window_data["construction_name"] = window_film_construction_name
                
                modifications_made.append({
                    "surface": window_name,
                    "field": "construction_name",
                    "old_value": old_construction,
                    "new_value": window_film_construction_name
                })
                logger.debug(f"Updated construction of window '{window_name}': {old_construction} -> {window_film_construction_name}")
            
            logger.info(f"Successfully added window film to {len(ext_window_surfs)} windows")
            return ep
            
        except Exception as e:
            logger.error(f"Error modifying window film properties: {e}")
            raise RuntimeError(f"Error modifying window film properties: {str(e)}")

    def change_infiltration_by_mult(self, epjson_data: Dict[str, Any], mult: float = 0.9) -> Dict[str, Any]:
        """
        Modify infiltration rates in the epJSON file by a multiplier

        Args:
            epjson_data: The epJSON model dictionary
            mult: Multiplier for infiltration rates (default: 0.9)
        
        Returns:
            The modified epJSON dictionary
        """
        modifications_made = []

        try:
            ep = epjson_data
            
            object_type = "ZoneInfiltration:DesignFlowRate"
            infiltration_objs = ep.get(object_type, {})
            
            if not infiltration_objs:
                logger.warning(f"No {object_type} objects found in the epJSON file")
                return ep

            for infil_name, infiltration_obj in infiltration_objs.items():
                design_flow_method = infiltration_obj.get("design_flow_rate_calculation_method", "")
                
                # Map calculation method to corresponding field name (epJSON format - lowercase with underscores)
                flow_field = None
                if design_flow_method.lower() == "flow/exteriorarea":
                    flow_field = "flow_rate_per_exterior_surface_area"
                elif design_flow_method.lower() == "flow/area":
                    flow_field = "flow_rate_per_floor_area"
                elif design_flow_method.lower() == "flow/zone":
                    flow_field = "design_flow_rate"
                elif design_flow_method.lower() == "flow/exteriorwallarea":
                    flow_field = "flow_rate_per_exterior_surface_area"
                elif design_flow_method.lower() == "airchanges/hour":
                    flow_field = "air_changes_per_hour"
                else:
                    logger.warning(f"Unknown design flow method '{design_flow_method}' for infiltration object '{infil_name}'")
                    continue

                try:
                    old_value = infiltration_obj.get(flow_field)
                    if old_value is not None:
                        new_value = old_value * mult
                        infiltration_obj[flow_field] = new_value
                        
                        modifications_made.append({
                            "object_name": infil_name,
                            "field": flow_field,
                            "old_value": old_value,
                            "new_value": new_value
                        })
                        logger.debug(f"Updated {infil_name} {flow_field}: {old_value} -> {new_value}")
                    else:
                        logger.warning(f"Field '{flow_field}' not found in infiltration object '{infil_name}'")
                except Exception as e:
                    logger.error(f"Error setting {flow_field} to {new_value} for '{infil_name}': {e}")

            logger.info(f"Successfully modified {len(modifications_made)} infiltration objects")
            return ep
            
        except Exception as e:
            logger.error(f"Error modifying infiltration rate: {e}")
            raise RuntimeError(f"Error modifying infiltration rate: {str(e)}")
