"""
Internal loads measures for EnergyPlus models.

This module provides mixin class for inspecting and modifying internal load objects
in EnergyPlus models, including People, Lights, and ElectricEquipment.
"""

import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class InternalLoadsMeasures:
    """Mixin class for internal loads-related measures"""
    
    def inspect_people(self, epjson_data: Dict[str, Any]) -> str:
        """
        Inspect and list all People objects in the EnergyPlus model
        
        Args:
            epjson_data: The epJSON data dictionary
        
        Returns:
            JSON string with detailed People objects information
        """
        try:
            logger.info("Inspecting People objects")
            result = self.people_manager.get_people_objects(epjson_data)
            
            if result["success"]:
                logger.info(f"Found {result['total_people_objects']} People objects")
                return json.dumps(result, indent=2)
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error inspecting People objects: {e}")
            raise RuntimeError(f"Error inspecting People objects: {str(e)}")
    
    
    def modify_people(self, epjson_data: Dict[str, Any], modifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Modify People objects in the EnergyPlus model
        
        Args:
            epjson_data: The epJSON data dictionary
            modifications: List of modification specifications. Each item should have:
                          - "target": "all", "zone:ZoneName", or "name:PeopleName"
                          - "field_updates": Dictionary of field names and new values
        
        Returns:
            Modified epJSON data dictionary
        """
        try:
            logger.info("Modifying People objects")
            
            # Validate modifications first
            validation = self.people_manager.validate_people_modifications(modifications)
            if not validation["valid"]:
                raise RuntimeError(f"Validation errors: {validation['errors']}")
            
            # Apply modifications
            result = self.people_manager.modify_people_objects(
                epjson_data, modifications
            )
            
            if result["success"]:
                logger.info("Successfully modified People objects")
                return result["epjson_data"]
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error modifying People objects: {e}")
            raise RuntimeError(f"Error modifying People objects: {str(e)}")

    
    def inspect_lights(self, epjson_data: Dict[str, Any]) -> str:
        """
        Inspect and list all Lights objects in the EnergyPlus model
        
        Args:
            epjson_data: The epJSON data dictionary
        
        Returns:
            JSON string with detailed Lights objects information
        """
        try:
            logger.info("Inspecting Lights objects")
            result = self.lights_manager.get_lights_objects(epjson_data)
            
            if result["success"]:
                logger.info(f"Found {result['total_lights_objects']} Lights objects")
                return json.dumps(result, indent=2)
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error inspecting Lights objects: {e}")
            raise RuntimeError(f"Error inspecting Lights objects: {str(e)}")
    
    
    def modify_lights(self, epjson_data: Dict[str, Any], modifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Modify Lights objects in the EnergyPlus model
        
        Args:
            epjson_data: The epJSON data dictionary
            modifications: List of modification specifications. Each item should have:
                          - "target": "all", "zone:ZoneName", or "name:LightsName"
                          - "field_updates": Dictionary of field names and new values
        
        Returns:
            Modified epJSON data dictionary
        """
        try:
            logger.info("Modifying Lights objects")
            
            # Validate modifications first
            validation = self.lights_manager.validate_lights_modifications(modifications)
            if not validation["valid"]:
                raise RuntimeError(f"Validation errors: {validation['errors']}")
            
            # Apply modifications
            result = self.lights_manager.modify_lights_objects(
                epjson_data, modifications
            )
            
            if result["success"]:
                logger.info("Successfully modified Lights objects")
                return result["epjson_data"]
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error modifying Lights objects: {e}")
            raise RuntimeError(f"Error modifying Lights objects: {str(e)}")

    
    def inspect_electric_equipment(self, epjson_data: Dict[str, Any]) -> str:
        """
        Inspect and list all ElectricEquipment objects in the EnergyPlus model
        
        Args:
            epjson_data: The epJSON data dictionary
        
        Returns:
            JSON string with detailed ElectricEquipment objects information
        """
        try:
            logger.info("Inspecting ElectricEquipment objects")
            result = self.electric_equipment_manager.get_electric_equipment_objects(epjson_data)
            
            if result["success"]:
                logger.info(f"Found {result['total_electric_equipment_objects']} ElectricEquipment objects")
                return json.dumps(result, indent=2)
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error inspecting ElectricEquipment objects: {e}")
            raise RuntimeError(f"Error inspecting ElectricEquipment objects: {str(e)}")
    
    
    def modify_electric_equipment(self, epjson_data: Dict[str, Any], modifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Modify ElectricEquipment objects in the EnergyPlus model
        
        Args:
            epjson_data: The epJSON data dictionary
            modifications: List of modification specifications. Each item should have:
                          - "target": "all", "zone:ZoneName", or "name:ElectricEquipmentName"
                          - "field_updates": Dictionary of field names and new values
        
        Returns:
            Modified epJSON data dictionary
        """
        try:
            logger.info("Modifying ElectricEquipment objects")
            
            # Validate modifications first
            validation = self.electric_equipment_manager.validate_electric_equipment_modifications(modifications)
            if not validation["valid"]:
                raise RuntimeError(f"Validation errors: {validation['errors']}")
            
            # Apply modifications
            result = self.electric_equipment_manager.modify_electric_equipment_objects(
                epjson_data, modifications
            )
            
            if result["success"]:
                logger.info("Successfully modified ElectricEquipment objects")
                return result["epjson_data"]
            else:
                raise RuntimeError(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error modifying ElectricEquipment objects: {e}")
            raise RuntimeError(f"Error modifying ElectricEquipment objects: {str(e)}")
