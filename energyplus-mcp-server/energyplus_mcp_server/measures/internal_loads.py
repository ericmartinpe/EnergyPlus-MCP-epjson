"""
Internal loads measures for EnergyPlus models.

This module provides mixin class for inspecting and modifying internal load objects
in EnergyPlus models, including People, Lights, and ElectricEquipment.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class InternalLoadsMeasures:
    """Mixin class for internal loads-related measures"""
    
    def inspect_people(self, epjson_path: str) -> str:
        """
        Inspect and list all People objects in the EnergyPlus model
        
        Args:
            epjson_path: Path to the epJSON file
        
        Returns:
            JSON string with detailed People objects information
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Inspecting People objects for: {resolved_path}")
            result = self.people_manager.get_people_objects(resolved_path)
            
            if result["success"]:
                logger.info(f"Found {result['total_people_objects']} People objects")
                return json.dumps(result, indent=2)
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error inspecting People objects for {resolved_path}: {e}")
            raise RuntimeError(f"Error inspecting People objects: {str(e)}")
    
    
    def modify_people(self, epjson_path: str, modifications: List[Dict[str, Any]], 
                     output_path: Optional[str] = None) -> str:
        """
        Modify People objects in the EnergyPlus model
        
        Args:
            epjson_path: Path to the input epJSON file
            modifications: List of modification specifications. Each item should have:
                          - "target": "all", "zone:ZoneName", or "name:PeopleName"
                          - "field_updates": Dictionary of field names and new values
            output_path: Optional path for output file (if None, creates one with _modified suffix)
        
        Returns:
            JSON string with modification results
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Modifying People objects for: {resolved_path}")
            
            # Validate modifications first
            validation = self.people_manager.validate_people_modifications(modifications)
            if not validation["valid"]:
                return json.dumps({
                    "success": False,
                    "validation_errors": validation["errors"],
                    "input_file": resolved_path
                }, indent=2)
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
            
            # Apply modifications
            result = self.people_manager.modify_people_objects(
                resolved_path, modifications, output_path
            )
            
            if result["success"]:
                logger.info(f"Successfully modified People objects and saved to: {output_path}")
                return json.dumps(result, indent=2)
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error modifying People objects for {resolved_path}: {e}")
            raise RuntimeError(f"Error modifying People objects: {str(e)}")

    
    def inspect_lights(self, epjson_path: str) -> str:
        """
        Inspect and list all Lights objects in the EnergyPlus model
        
        Args:
            epjson_path: Path to the epJSON file
        
        Returns:
            JSON string with detailed Lights objects information
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Inspecting Lights objects for: {resolved_path}")
            result = self.lights_manager.get_lights_objects(resolved_path)
            
            if result["success"]:
                logger.info(f"Found {result['total_lights_objects']} Lights objects")
                return json.dumps(result, indent=2)
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error inspecting Lights objects for {resolved_path}: {e}")
            raise RuntimeError(f"Error inspecting Lights objects: {str(e)}")
    
    
    def modify_lights(self, epjson_path: str, modifications: List[Dict[str, Any]], 
                     output_path: Optional[str] = None) -> str:
        """
        Modify Lights objects in the EnergyPlus model
        
        Args:
            epjson_path: Path to the input epJSON file
            modifications: List of modification specifications. Each item should have:
                          - "target": "all", "zone:ZoneName", or "name:LightsName"
                          - "field_updates": Dictionary of field names and new values
            output_path: Optional path for output file (if None, creates one with _modified suffix)
        
        Returns:
            JSON string with modification results
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Modifying Lights objects for: {resolved_path}")
            
            # Validate modifications first
            validation = self.lights_manager.validate_lights_modifications(modifications)
            if not validation["valid"]:
                return json.dumps({
                    "success": False,
                    "validation_errors": validation["errors"],
                    "input_file": resolved_path
                }, indent=2)
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
            
            # Apply modifications
            result = self.lights_manager.modify_lights_objects(
                resolved_path, modifications, output_path
            )
            
            if result["success"]:
                logger.info(f"Successfully modified Lights objects and saved to: {output_path}")
                return json.dumps(result, indent=2)
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error modifying Lights objects for {resolved_path}: {e}")
            raise RuntimeError(f"Error modifying Lights objects: {str(e)}")

    
    def inspect_electric_equipment(self, epjson_path: str) -> str:
        """
        Inspect and list all ElectricEquipment objects in the EnergyPlus model
        
        Args:
            epjson_path: Path to the epJSON file
        
        Returns:
            JSON string with detailed ElectricEquipment objects information
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Inspecting ElectricEquipment objects for: {resolved_path}")
            result = self.electric_equipment_manager.get_electric_equipment_objects(resolved_path)
            
            if result["success"]:
                logger.info(f"Found {result['total_electric_equipment_objects']} ElectricEquipment objects")
                return json.dumps(result, indent=2)
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error inspecting ElectricEquipment objects for {resolved_path}: {e}")
            raise RuntimeError(f"Error inspecting ElectricEquipment objects: {str(e)}")
    
    
    def modify_electric_equipment(self, epjson_path: str, modifications: List[Dict[str, Any]], 
                                 output_path: Optional[str] = None) -> str:
        """
        Modify ElectricEquipment objects in the EnergyPlus model
        
        Args:
            epjson_path: Path to the input epJSON file
            modifications: List of modification specifications. Each item should have:
                          - "target": "all", "zone:ZoneName", or "name:ElectricEquipmentName"
                          - "field_updates": Dictionary of field names and new values
            output_path: Optional path for output file (if None, creates one with _modified suffix)
        
        Returns:
            JSON string with modification results
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Modifying ElectricEquipment objects for: {resolved_path}")
            
            # Validate modifications first
            validation = self.electric_equipment_manager.validate_electric_equipment_modifications(modifications)
            if not validation["valid"]:
                return json.dumps({
                    "success": False,
                    "validation_errors": validation["errors"],
                    "input_file": resolved_path
                }, indent=2)
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
            
            # Apply modifications
            result = self.electric_equipment_manager.modify_electric_equipment_objects(
                resolved_path, modifications, output_path
            )
            
            if result["success"]:
                logger.info(f"Successfully modified ElectricEquipment objects and saved to: {output_path}")
                return json.dumps(result, indent=2)
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error modifying ElectricEquipment objects for {resolved_path}: {e}")
            raise RuntimeError(f"Error modifying ElectricEquipment objects: {str(e)}")
