"""
Output variables and meters measures for EnergyPlus models.

This module provides mixin class for managing output variables and meters,
including getting configured outputs, discovering available options, and adding new outputs.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class OutputsMeasures:
    """Mixin class for output variables and meters measures"""
    
    def get_output_variables(self, epjson_data: Dict[str, Any], discover_available: bool = False, run_days: int = 1) -> str:
        """
        Get output variables from the model - either configured variables or discover all available ones
        
        Args:
            epjson_data: The epJSON data dictionary
            discover_available: If True, runs simulation to discover all available variables. 
                            If False, returns currently configured variables (default)
            run_days: Number of days to run for discovery simulation (default: 1, only used if discover_available=True)
        
        Returns:
            JSON string with output variables information
        """
        ep = epjson_data
        
        try:
            if discover_available:
                logger.info("Discovering available output variables")
                result = self.output_var_manager.discover_available_variables(ep, run_days)
            else:
                logger.debug("Getting configured output variables")
                result = self.output_var_manager.get_configured_variables(ep)
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting output variables: {e}")
            raise RuntimeError(f"Error getting output variables: {str(e)}")


    def add_output_variables(self, epjson_data: Dict[str, Any], variables: List, 
                            validation_level: str = "moderate", 
                            allow_duplicates: bool = False) -> Dict[str, Any]:
        """
        Add output variables to an EnergyPlus epJSON data dictionary with validation
        
        Args:
            epjson_data: The epJSON data dictionary
            variables: List of variable specifications (dicts, strings, or lists)
            validation_level: "strict", "moderate", or "lenient" 
            allow_duplicates: Whether to allow duplicate variable specifications
        
        Returns:
            Modified epJSON data dictionary
        """
        try:
            logger.info(f"Adding output variables (validation: {validation_level})")
            
            ep = epjson_data
            
            # Auto-resolve variable specifications to standard format
            resolved_variables = self.output_var_manager.auto_resolve_variable_specs(variables)
            
            # Validate variable specifications
            validation_report = self.output_var_manager.validate_variable_specifications(
                ep, resolved_variables, validation_level
            )
            
            # Handle duplicates
            duplicate_report = self.output_var_manager.check_duplicate_variables(
                ep, 
                [v["specification"] for v in validation_report["valid_variables"]], 
                allow_duplicates
            )
            
            # Add variables to epJSON dict
            addition_result = self.output_var_manager.add_variables_to_idf(
                ep, duplicate_report["new_variables"], ep
            )
            
            # Compile comprehensive result
            result = {
                "success": addition_result["success"],
                "validation_level": validation_level,
                "allow_duplicates": allow_duplicates,
                "requested_variables": len(variables),
                "resolved_variables": len(resolved_variables),
                "added_variables": addition_result["added_count"],
                "skipped_duplicates": duplicate_report["duplicates_found"],
                "validation_summary": {
                    "total_valid": len(validation_report["valid_variables"]),
                    "total_invalid": len(validation_report["invalid_variables"]),
                    "warnings_count": len(validation_report["warnings"])
                },
                "added_specifications": addition_result.get("added_variables", []),
                "performance": validation_report.get("performance", {}),
                "timestamp": datetime.now().isoformat()
            }
            
            # Include detailed validation info for strict mode or if there were errors
            if validation_level == "strict" or validation_report["invalid_variables"]:
                result["validation_details"] = validation_report
            
            # Include duplicate details if any were found
            if duplicate_report["duplicates_found"] > 0:
                result["duplicate_details"] = duplicate_report
            
            # Add error details if addition failed
            if not addition_result["success"]:
                result["addition_error"] = addition_result.get("error", "Unknown error")
            
            logger.info(f"Successfully processed output variables: {addition_result['added_count']} added")
            return ep
            
        except Exception as e:
            logger.error(f"Error in add_output_variables: {e}")
            raise RuntimeError(f"Error adding output variables: {str(e)}")

    
    def add_output_meters(self, epjson_data: Dict[str, Any], meters: List, 
                         validation_level: str = "moderate", 
                         allow_duplicates: bool = False) -> Dict[str, Any]:
        """
        Add output meters to an EnergyPlus epJSON data dictionary with intelligent validation
        
        Args:
            epjson_data: The epJSON data dictionary
            meters: List of meter specifications. Can be:
                   - Simple strings: ["Electricity:Facility", "NaturalGas:Facility"] 
                   - [name, frequency] pairs: [["Electricity:Facility", "hourly"], ["NaturalGas:Facility", "daily"]]
                   - [name, frequency, type] triplets: [["Electricity:Facility", "hourly", "Output:Meter"]]
                   - Full specifications: [{"meter_name": "Electricity:Facility", "frequency": "hourly", "meter_type": "Output:Meter"}]
                   - Mixed formats in the same list
            validation_level: Validation strictness level:
                             - "strict": Full validation with model checking (recommended for beginners)
                             - "moderate": Basic validation with helpful warnings (default)
                             - "lenient": Minimal validation (for advanced users)
            allow_duplicates: Whether to allow duplicate output meter specifications (default: False)
        
        Returns:
            Modified epJSON data dictionary
            
        Examples:
            # Simple usage
            add_output_meters(epjson_data, ["Electricity:Facility", "NaturalGas:Facility"])
            
            # With custom frequencies  
            add_output_meters(epjson_data, [["Electricity:Facility", "daily"], ["NaturalGas:Facility", "hourly"]])
            
            # Full control with meter types
            add_output_meters(epjson_data, [
                {"meter_name": "Electricity:Facility", "frequency": "hourly", "meter_type": "Output:Meter"},
                {"meter_name": "NaturalGas:Facility", "frequency": "daily", "meter_type": "Output:Meter:Cumulative"}
            ], validation_level="strict")
        """
        try:
            logger.info(f"Adding output meters (validation: {validation_level})")
            
            ep = epjson_data
            
            # Auto-resolve meter specifications to standard format
            resolved_meters = self.output_meter_manager.auto_resolve_meter_specs(meters)
            
            # Validate meter specifications
            validation_report = self.output_meter_manager.validate_meter_specifications(
                ep, resolved_meters, validation_level
            )
            
            # Handle duplicates
            duplicate_report = self.output_meter_manager.check_duplicate_meters(
                ep, 
                [m["specification"] for m in validation_report["valid_meters"]], 
                allow_duplicates
            )
            
            # Add meters to epJSON dict
            addition_result = self.output_meter_manager.add_meters_to_epjson(
                ep, duplicate_report["new_meters"], ep
            )
            
            # Compile comprehensive result
            result = {
                "success": addition_result["success"],
                "validation_level": validation_level,
                "allow_duplicates": allow_duplicates,
                "requested_meters": len(meters),
                "resolved_meters": len(resolved_meters),
                "added_meters": addition_result["added_count"],
                "skipped_duplicates": duplicate_report["duplicates_found"],
                "validation_summary": {
                    "total_valid": len(validation_report["valid_meters"]),
                    "total_invalid": len(validation_report["invalid_meters"]),
                    "warnings_count": len(validation_report["warnings"])
                },
                "added_specifications": addition_result.get("added_meters", []),
                "performance": validation_report.get("performance", {}),
                "timestamp": datetime.now().isoformat()
            }
            
            # Include detailed validation info for strict mode or if there were errors
            if validation_level == "strict" or validation_report["invalid_meters"]:
                result["validation_details"] = validation_report
            
            # Include duplicate details if any were found
            if duplicate_report["duplicates_found"] > 0:
                result["duplicate_details"] = duplicate_report
            
            # Add error details if addition failed
            if not addition_result["success"]:
                result["addition_error"] = addition_result.get("error", "Unknown error")
            
            logger.info(f"Successfully processed output meters: {addition_result['added_count']} added")
            return ep
            
        except Exception as e:
            logger.error(f"Error in add_output_meters: {e}")
            raise RuntimeError(f"Error adding output meters: {str(e)}")

    def get_output_meters(self, epjson_data: Dict[str, Any], discover_available: bool = False, run_days: int = 1) -> str:
        """
        Get output meters from the model - either configured meters or discover all available ones
        
        Args:
            epjson_data: The epJSON data dictionary
            discover_available: If True, runs simulation to discover all available meters.
                              If False, returns currently configured meters in the epJSON (default: False)
            run_days: Number of days to run for discovery simulation (default: 1)
        
        Returns:
            JSON string with meter information. When discover_available=True, includes
            all possible meters with units, frequencies, and ready-to-use Output:Meter lines.
            When discover_available=False, shows only currently configured Output:Meter objects.
        """
        ep = epjson_data
        
        try:
            if discover_available:
                logger.info("Discovering available output meters")
                result = self.output_meter_manager.discover_available_meters(ep, run_days)
            else:
                logger.debug("Getting configured output meters")
                result = self.output_meter_manager.get_configured_meters(ep)
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting output meters: {e}")
            raise RuntimeError(f"Error getting output meters: {str(e)}")
