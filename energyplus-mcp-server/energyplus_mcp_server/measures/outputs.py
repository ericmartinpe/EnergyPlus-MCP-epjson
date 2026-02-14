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
    
    def get_output_variables(self, epjson_path: str, discover_available: bool = False, run_days: int = 1) -> str:
        """
        Get output variables from the model - either configured variables or discover all available ones
        
        Args:
            epjson_path: Path to the epJSON file
            discover_available: If True, runs simulation to discover all available variables. 
                            If False, returns currently configured variables (default)
            run_days: Number of days to run for discovery simulation (default: 1, only used if discover_available=True)
        
        Returns:
            JSON string with output variables information
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            if discover_available:
                logger.info(f"Discovering available output variables for: {resolved_path}")
                result = self.output_var_manager.discover_available_variables(resolved_path, run_days)
            else:
                logger.debug(f"Getting configured output variables for: {resolved_path}")
                result = self.output_var_manager.get_configured_variables(resolved_path)
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting output variables for {resolved_path}: {e}")
            raise RuntimeError(f"Error getting output variables: {str(e)}")


    def add_output_variables(self, epjson_path: str, variables: List, 
                            validation_level: str = "moderate", 
                            allow_duplicates: bool = False,
                            output_path: Optional[str] = None) -> str:
        """
        Add output variables to an EnergyPlus epJSON file with validation
        
        Args:
            epjson_path: Path to the input epJSON file
            variables: List of variable specifications (dicts, strings, or lists)
            validation_level: "strict", "moderate", or "lenient" 
            allow_duplicates: Whether to allow duplicate variable specifications
            output_path: Optional path for output file (auto-generated if None)
        
        Returns:
            JSON string with operation results
        """
        try:
            logger.info(f"Adding output variables to {epjson_path} (validation: {validation_level})")
            
            # Resolve epJSON path
            resolved_path = self._resolve_epjson_path(epjson_path)
            
            # Auto-resolve variable specifications to standard format
            resolved_variables = self.output_var_manager.auto_resolve_variable_specs(variables)
            
            # Validate variable specifications
            validation_report = self.output_var_manager.validate_variable_specifications(
                resolved_path, resolved_variables, validation_level
            )
            
            # Handle duplicates
            duplicate_report = self.output_var_manager.check_duplicate_variables(
                resolved_path, 
                [v["specification"] for v in validation_report["valid_variables"]], 
                allow_duplicates
            )
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                output_path = str(path_obj.parent / f"{path_obj.stem}_with_outputs{path_obj.suffix}")
            
            # Add variables to IDF
            addition_result = self.output_var_manager.add_variables_to_idf(
                resolved_path, duplicate_report["new_variables"], output_path
            )
            
            # Compile comprehensive result
            result = {
                "success": addition_result["success"],
                "input_file": resolved_path,
                "output_file": output_path,
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
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error in add_output_variables: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "input_file": epjson_path,
                "timestamp": datetime.now().isoformat()
            }, indent=2)

    
    def add_output_meters(self, epjson_path: str, meters: List, 
                         validation_level: str = "moderate", 
                         allow_duplicates: bool = False,
                         output_path: Optional[str] = None) -> str:
        """
        Add output meters to an EnergyPlus epJSON file with intelligent validation
        
        Args:
            epjson_path: Path to the input epJSON file
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
            output_path: Optional path for output file (if None, creates one with _with_meters suffix)
        
        Returns:
            JSON string with detailed results including validation report, added meters, and performance metrics
            
        Examples:
            # Simple usage
            add_output_meters("model.epJSON", ["Electricity:Facility", "NaturalGas:Facility"])
            
            # With custom frequencies  
            add_output_meters("model.epJSON", [["Electricity:Facility", "daily"], ["NaturalGas:Facility", "hourly"]])
            
            # Full control with meter types
            add_output_meters("model.epJSON", [
                {"meter_name": "Electricity:Facility", "frequency": "hourly", "meter_type": "Output:Meter"},
                {"meter_name": "NaturalGas:Facility", "frequency": "daily", "meter_type": "Output:Meter:Cumulative"}
            ], validation_level="strict")
        """
        try:
            logger.info(f"Adding output meters to {epjson_path} (validation: {validation_level})")
            
            # Resolve epJSON path
            resolved_path = self._resolve_epjson_path(epjson_path)
            
            # Auto-resolve meter specifications to standard format
            resolved_meters = self.output_meter_manager.auto_resolve_meter_specs(meters)
            
            # Validate meter specifications
            validation_report = self.output_meter_manager.validate_meter_specifications(
                resolved_path, resolved_meters, validation_level
            )
            
            # Handle duplicates
            duplicate_report = self.output_meter_manager.check_duplicate_meters(
                resolved_path, 
                [m["specification"] for m in validation_report["valid_meters"]], 
                allow_duplicates
            )
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                output_path = str(path_obj.parent / f"{path_obj.stem}_with_meters{path_obj.suffix}")
            
            # Add meters to epJSON
            addition_result = self.output_meter_manager.add_meters_to_epjson(
                resolved_path, duplicate_report["new_meters"], output_path
            )
            
            # Compile comprehensive result
            result = {
                "success": addition_result["success"],
                "input_file": resolved_path,
                "output_file": output_path,
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
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error in add_output_meters: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "input_file": epjson_path,
                "timestamp": datetime.now().isoformat()
            }, indent=2)

    def get_output_meters(self, epjson_path: str, discover_available: bool = False, run_days: int = 1) -> str:
        """
        Get output meters from the model - either configured meters or discover all available ones
        
        Args:
            epjson_path: Path to the epJSON file
            discover_available: If True, runs simulation to discover all available meters.
                              If False, returns currently configured meters in the epJSON (default: False)
            run_days: Number of days to run for discovery simulation (default: 1)
        
        Returns:
            JSON string with meter information. When discover_available=True, includes
            all possible meters with units, frequencies, and ready-to-use Output:Meter lines.
            When discover_available=False, shows only currently configured Output:Meter objects.
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            if discover_available:
                logger.info(f"Discovering available output meters for: {resolved_path}")
                result = self.output_meter_manager.discover_available_meters(resolved_path, run_days)
            else:
                logger.debug(f"Getting configured output meters for: {resolved_path}")
                result = self.output_meter_manager.get_configured_meters(resolved_path)
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting output meters for {resolved_path}: {e}")
            raise RuntimeError(f"Error getting output meters: {str(e)}")
