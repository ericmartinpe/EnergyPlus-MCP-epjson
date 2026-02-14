"""
File Operations Measures for EnergyPlus MCP Server.

This module contains all file operation related methods including:
- Loading and saving epJSON files
- IDF to epJSON conversion
- File listing and discovery
- File copying and validation
- Configuration management
"""

import os
import json
import logging
import subprocess
import shutil
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class FileOperationsMeasures:
    """Mixin class containing file operation methods for EnergyPlusManager"""
    
    def load_json(self, file_path: str) -> Dict[str, Any]:
        """Load epJSON file and return its content"""
        with open(file_path, "r") as f:
            return json.load(f)

    def save_json(self, data: Dict[str, Any], file_path: str):
        """Save data to epJSON file"""
        # Ensure the output directory exists
        output_dir = os.path.dirname(file_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)

    def convert_idf_to_epjson(self, idf_path: str, output_path: Optional[str] = None) -> str:
        """
        Convert an IDF file to epJSON format using EnergyPlus
        
        Args:
            idf_path: Path to the IDF file
            output_path: Optional path for output epJSON file. If None, creates one in same directory with .epJSON extension
        
        Returns:
            JSON string with conversion results
        """
        from ..utils.path_utils import resolve_path
        
        try:
            # Resolve the IDF path
            resolved_idf_path = resolve_path(self.config, idf_path, file_types=['.idf'], description="IDF file")
            logger.info(f"Converting IDF to epJSON: {resolved_idf_path}")
            
            # Determine output path
            if output_path is None:
                idf_path_obj = Path(resolved_idf_path)
                output_path = str(idf_path_obj.parent / f"{idf_path_obj.stem}.epJSON")
            
            # Check if output already exists and is newer than source
            if os.path.exists(output_path):
                idf_mtime = os.path.getmtime(resolved_idf_path)
                epjson_mtime = os.path.getmtime(output_path)
                if epjson_mtime > idf_mtime:
                    logger.info(f"epJSON file already exists and is up-to-date: {output_path}")
                    return json.dumps({
                        "success": True,
                        "input_file": resolved_idf_path,
                        "output_file": output_path,
                        "message": "epJSON already exists and is up-to-date",
                        "converted": False
                    }, indent=2)
            
            # Run EnergyPlus conversion
            energyplus_exe = self.config.energyplus.executable_path
            if not os.path.exists(energyplus_exe):
                raise RuntimeError(f"EnergyPlus executable not found: {energyplus_exe}")
            
            # EnergyPlus --convert-only command
            output_dir = os.path.dirname(output_path)
            cmd = [
                energyplus_exe,
                '--convert-only',
                '--output-directory', output_dir,
                resolved_idf_path
            ]
            
            logger.debug(f"Running conversion command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            # Check if conversion succeeded
            # EnergyPlus creates the epJSON with the same basename as the IDF
            converted_file = os.path.join(output_dir, f"{Path(resolved_idf_path).stem}.epJSON")
            
            if os.path.exists(converted_file):
                # Move to desired output path if different
                if converted_file != output_path:
                    shutil.move(converted_file, output_path)
                
                logger.info(f"Successfully converted IDF to epJSON: {output_path}")
                return json.dumps({
                    "success": True,
                    "input_file": resolved_idf_path,
                    "output_file": output_path,
                    "message": "Successfully converted IDF to epJSON",
                    "converted": True,
                    "file_size_bytes": os.path.getsize(output_path)
                }, indent=2)
            else:
                raise RuntimeError(f"Conversion failed. Output file not created. EnergyPlus output: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error converting IDF to epJSON: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
                "input_file": idf_path
            }, indent=2)

    def _resolve_epjson_path(self, epjson_path: str) -> str:
        """
        Resolve epJSON path (handle relative paths, sample files, example files, etc.)
        Automatically converts IDF files to epJSON if needed.
        """
        from ..utils.path_utils import resolve_path
        
        # Check if the path points to an IDF file
        if epjson_path.lower().endswith('.idf'):
            try:
                # Try to resolve the IDF path first
                resolved_idf = resolve_path(self.config, epjson_path, file_types=['.idf'], description="IDF file")
                logger.info(f"IDF file detected: {resolved_idf}. Auto-converting to epJSON...")
                
                # Convert to epJSON in the same directory
                idf_path_obj = Path(resolved_idf)
                epjson_output_path = str(idf_path_obj.parent / f"{idf_path_obj.stem}.epJSON")
                
                # Perform conversion
                conversion_result = json.loads(self.convert_idf_to_epjson(resolved_idf, epjson_output_path))
                
                if conversion_result.get("success"):
                    logger.info(f"Auto-conversion successful: {epjson_output_path}")
                    return epjson_output_path
                else:
                    raise RuntimeError(f"Auto-conversion failed: {conversion_result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.warning(f"Could not auto-convert IDF file: {e}")
                # Fall through to try resolving as epJSON
        
        # Standard epJSON resolution
        return resolve_path(self.config, epjson_path, file_types=['.epJSON', '.json'], description="epJSON file")
        
    def load_epjson(self, epjson_path: str) -> Dict[str, Any]:
        """Load an epJSON file and return basic information"""
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Loading epJSON file: {resolved_path}")
            ep = self.load_json(resolved_path)
            
            # Get basic counts
            building_count = len(ep.get("Building", {}))
            zone_count = len(ep.get("Zone", {}))
            surface_count = len(ep.get("BuildingSurface:Detailed", {}))
            material_count = len(ep.get("Material", {})) + len(ep.get("Material:NoMass", {}))
            construction_count = len(ep.get("Construction", {}))
            
            result = {
                "file_path": resolved_path,
                "original_path": epjson_path,
                "building_count": building_count,
                "zone_count": zone_count,
                "surface_count": surface_count,
                "material_count": material_count,
                "construction_count": construction_count,
                "loaded_successfully": True,
                "file_size_bytes": os.path.getsize(resolved_path)
            }
            
            logger.info(f"epJSON loaded successfully: {zone_count} zones, {surface_count} surfaces")
            return result
            
        except Exception as e:
            logger.error(f"Error loading epJSON file {resolved_path}: {e}")
            raise RuntimeError(f"Error loading epJSON file: {str(e)}")
    
    def list_available_files(self, include_example_files: bool = False, include_weather_data: bool = False) -> str:
        """List available files in specified directories
        
        Args:
            include_example_files: Whether to include EnergyPlus example files directory
            include_weather_data: Whether to include EnergyPlus weather data directory
            
        Returns:
            JSON string with available files organized by source and type
        """
        try:
            sample_path = Path(self.config.paths.sample_files_path)
            logger.debug(f"Listing files in sample_files: {sample_path}")
            
            files = {
                "sample_files": {
                    "path": str(sample_path),
                    "available": sample_path.exists(),
                    "IDF files": [],
                    "epJSON files": [],
                    "Weather files": [],
                    "Other files": []
                }
            }
            
            # Always process sample files directory
            if sample_path.exists():
                for file_path in sample_path.iterdir():
                    if file_path.is_file():
                        file_info = {
                            "name": file_path.name,
                            "size_bytes": file_path.stat().st_size,
                            "modified": file_path.stat().st_mtime,
                            "source": "sample_files"
                        }
                        
                        if file_path.suffix.lower() == '.idf':
                            files["sample_files"]["IDF files"].append(file_info)
                        elif file_path.suffix.lower() == '.epjson':
                            files["sample_files"]["epJSON files"].append(file_info)
                        elif file_path.suffix.lower() == '.epw':
                            files["sample_files"]["Weather files"].append(file_info)
                        else:
                            files["sample_files"]["Other files"].append(file_info)
            
            # Conditionally process example files directory
            if include_example_files:
                example_path = Path(self.config.energyplus.example_files_path)
                logger.debug(f"Listing files in example_files: {example_path}")
                
                files["example_files"] = {
                    "path": str(example_path),
                    "available": example_path.exists(),
                    "IDF files": [],
                    "epJSON files": [],
                    "Weather files": [],
                    "Other files": []
                }
                
                if example_path.exists():
                    for file_path in example_path.iterdir():
                        if file_path.is_file():
                            file_info = {
                                "name": file_path.name,
                                "size_bytes": file_path.stat().st_size,
                                "modified": file_path.stat().st_mtime,
                                "source": "example_files"
                            }
                            
                            if file_path.suffix.lower() == '.idf':
                                files["example_files"]["IDF files"].append(file_info)
                            elif file_path.suffix.lower() == '.epjson':
                                files["example_files"]["epJSON files"].append(file_info)
                            elif file_path.suffix.lower() == '.epw':
                                files["example_files"]["Weather files"].append(file_info)
                            else:
                                files["example_files"]["Other files"].append(file_info)
            
            # Conditionally process weather data directory
            if include_weather_data:
                weather_path = Path(self.config.energyplus.weather_data_path)
                logger.debug(f"Listing files in weather_data: {weather_path}")
                
                files["weather_data"] = {
                    "path": str(weather_path),
                    "available": weather_path.exists(),
                    "IDF files": [],
                    "epJSON files": [],
                    "Weather files": [],
                    "Other files": []
                }
                
                if weather_path.exists():
                    for file_path in weather_path.iterdir():
                        if file_path.is_file():
                            file_info = {
                                "name": file_path.name,
                                "size_bytes": file_path.stat().st_size,
                                "modified": file_path.stat().st_mtime,
                                "source": "weather_data"
                            }
                            
                            if file_path.suffix.lower() == '.idf':
                                files["weather_data"]["IDF files"].append(file_info)
                            elif file_path.suffix.lower() == '.epjson':
                                files["weather_data"]["epJSON files"].append(file_info)
                            elif file_path.suffix.lower() == '.epw':
                                files["weather_data"]["Weather files"].append(file_info)
                            else:
                                files["weather_data"]["Other files"].append(file_info)
            
            # Sort files by name in each category for each source
            for source_key in files.keys():
                for category in ["IDF files", "epJSON files", "Weather files", "Other files"]:
                    files[source_key][category].sort(key=lambda x: x["name"])
            
            # Log summary
            total_counts = {}
            for source_key in files.keys():
                total_idf = len(files[source_key]["IDF files"])
                total_epsjon = len(files[source_key]["epJSON files"])
                total_weather = len(files[source_key]["Weather files"])
                total_counts[source_key] = {"IDF": total_idf, "epJSON": total_epsjon, "Weather": total_weather}
                logger.debug(f"Found {total_idf} IDF files, {total_epsjon} epJSON files, {total_weather} weather files in {source_key}")
            
            return json.dumps(files, indent=2)
            
        except Exception as e:
            logger.error(f"Error listing available files: {e}")
            raise RuntimeError(f"Error listing available files: {str(e)}")
    
    def list_epjson_files(self) -> str:
        """List all available epJSON files from sample_files directory
        
        Returns:
            JSON string with available epJSON files
        """
        try:
            sample_path = Path(self.config.paths.sample_files_path)
            epjson_files = []
            
            if sample_path.exists():
                for file_path in sample_path.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in ['.epjson', '.json']:
                        epjson_files.append({
                            "name": file_path.name,
                            "path": str(file_path),
                            "size_bytes": file_path.stat().st_size,
                            "modified": file_path.stat().st_mtime
                        })
            
            epjson_files.sort(key=lambda x: x["name"])
            
            result = {
                "directory": str(sample_path),
                "total_files": len(epjson_files),
                "files": epjson_files
            }
            
            logger.info(f"Found {len(epjson_files)} epJSON files in {sample_path}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error listing epJSON files: {e}")
            raise RuntimeError(f"Error listing epJSON files: {str(e)}")
    
    def list_weather_files(self) -> str:
        """List all available weather files from sample_files directory
        
        Returns:
            JSON string with available weather files
        """
        try:
            sample_path = Path(self.config.paths.sample_files_path)
            weather_files = []
            
            if sample_path.exists():
                for file_path in sample_path.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() == '.epw':
                        weather_files.append({
                            "name": file_path.name,
                            "path": str(file_path),
                            "size_bytes": file_path.stat().st_size,
                            "modified": file_path.stat().st_mtime
                        })
            
            weather_files.sort(key=lambda x: x["name"])
            
            result = {
                "directory": str(sample_path),
                "total_files": len(weather_files),
                "files": weather_files
            }
            
            logger.info(f"Found {len(weather_files)} weather files in {sample_path}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error listing weather files: {e}")
            raise RuntimeError(f"Error listing weather files: {str(e)}")
    
    def copy_file(self, source_path: str, target_path: str, overwrite: bool = False, file_types: List[str] = None) -> str:
        """
        Copy a file from source to target location with fuzzy path resolution
        
        Args:
            source_path: Source file path (can be fuzzy - relative, filename only, etc.)
            target_path: Target path for the copy (can be fuzzy - relative, filename only, etc.)
            overwrite: Whether to overwrite existing target file (default: False)
            file_types: List of acceptable file extensions (e.g., ['.idf', '.epw']). If None, accepts any file type.
        
        Returns:
            JSON string with copy operation results
        """
        try:
            logger.info(f"Copying file from '{source_path}' to '{target_path}'")
            
            # Import here to avoid circular imports
            from ..utils.path_utils import resolve_path
            
            # Determine file description for error messages
            file_description = "file"
            if file_types:
                # Convert file_types to lowercase for case-insensitive comparison
                file_types_lower = [ft.lower() for ft in file_types]
                if '.idf' in file_types_lower:
                    file_description = "IDF file"
                if '.epjson' in file_types or '.epJSON' in file_types or '.json' in file_types:
                    file_description = "JSON file"
                elif '.epw' in file_types:
                    file_description = "weather file"
                else:
                    file_description = f"file with extensions {file_types}"
            
            # Resolve source path (must exist)
            enable_fuzzy = file_types and '.epw' in file_types  # Enable fuzzy matching for weather files
            resolved_source_path = resolve_path(self.config, source_path, file_types, file_description, 
                                               must_exist=True, enable_fuzzy_weather_matching=enable_fuzzy)
            logger.debug(f"Resolved source path: {resolved_source_path}")
            
            # Resolve target path (for creation)
            resolved_target_path = resolve_path(self.config, target_path, must_exist=False, description="target file")
            logger.debug(f"Resolved target path: {resolved_target_path}")
            
            # Check if source file is readable
            if not os.access(resolved_source_path, os.R_OK):
                raise PermissionError(f"Cannot read source file: {resolved_source_path}")
            
            # Check if target already exists
            if os.path.exists(resolved_target_path) and not overwrite:
                raise FileExistsError(f"Target file already exists: {resolved_target_path}. Use overwrite=True to replace it.")
            
            # Create target directory if it doesn't exist
            target_dir = os.path.dirname(resolved_target_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
                logger.debug(f"Created target directory: {target_dir}")
            
            # Get source file info before copying
            source_stat = os.stat(resolved_source_path)
            source_size = source_stat.st_size
            source_mtime = source_stat.st_mtime
            
            # Perform the copy
            start_time = datetime.now()
            shutil.copy2(resolved_source_path, resolved_target_path)
            end_time = datetime.now()
            copy_duration = end_time - start_time
            
            # Verify the copy
            if not os.path.exists(resolved_target_path):
                raise RuntimeError("Copy operation failed - target file not found after copy")
            
            target_stat = os.stat(resolved_target_path)
            target_size = target_stat.st_size
            
            if source_size != target_size:
                raise RuntimeError(f"Copy verification failed - size mismatch: source={source_size}, target={target_size}")
            
            # Try to validate the copied file if it's an epJSON
            validation_passed = True
            validation_message = "File copied successfully"
            
            if file_types and ('.epJSON' in file_types or '.json' in file_types):
                try:
                    ep = self.load_json(resolved_target_path)
                    validation_message = "epJSON or JSON file loads successfully"
                except Exception as e:
                    validation_passed = False
                    validation_message = f"Warning: Copied epJSON file may be invalid: {str(e)}"
                    logger.warning(f"epJSON validation failed for copied file: {e}")
            
            result = {
                "success": True,
                "source": {
                    "original_path": source_path,
                    "resolved_path": resolved_source_path,
                    "size_bytes": source_size,
                    "modified_time": datetime.fromtimestamp(source_mtime).isoformat()
                },
                "target": {
                    "original_path": target_path,
                    "resolved_path": resolved_target_path,
                    "size_bytes": target_size,
                    "created_time": end_time.isoformat()
                },
                "operation": {
                    "copy_duration": str(copy_duration),
                    "overwrite_used": overwrite and os.path.exists(resolved_target_path),
                    "validation_passed": validation_passed,
                    "validation_message": validation_message
                },
                "timestamp": end_time.isoformat()
            }
            
            logger.info(f"Successfully copied file: {resolved_source_path} -> {resolved_target_path}")
            return json.dumps(result, indent=2)
            
        except FileNotFoundError as e:
            logger.warning(f"Source file not found: {source_path}")
            
            # Try to provide helpful suggestions
            try:
                from ..utils.path_utils import PathResolver
                resolver = PathResolver(self.config)
                suggestions = resolver.suggest_similar_paths(source_path, file_types)
                
                return json.dumps({
                    "success": False,
                    "error": "File not found",
                    "message": str(e),
                    "source_path": source_path,
                    "suggestions": suggestions[:5] if suggestions else [],
                    "timestamp": datetime.now().isoformat()
                }, indent=2)
            except Exception:
                return json.dumps({
                    "success": False,
                    "error": "File not found",
                    "message": str(e),
                    "source_path": source_path,
                    "timestamp": datetime.now().isoformat()
                }, indent=2)
        
        except FileExistsError as e:
            logger.warning(f"Target file already exists: {target_path}")
            return json.dumps({
                "success": False,
                "error": "File already exists",
                "message": str(e),
                "target_path": target_path,
                "suggestion": "Use overwrite=True to replace existing file",
                "timestamp": datetime.now().isoformat()
            }, indent=2)
        
        except PermissionError as e:
            logger.error(f"Permission error during copy: {e}")
            return json.dumps({
                "success": False,
                "error": "Permission denied",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }, indent=2)
        
        except Exception as e:
            logger.error(f"Error copying file from {source_path} to {target_path}: {e}")
            return json.dumps({
                "success": False,
                "error": "Copy operation failed",
                "message": str(e),
                "source_path": source_path,
                "target_path": target_path,
                "timestamp": datetime.now().isoformat()
            }, indent=2)

    def get_configuration_info(self) -> str:
        """Get current configuration information"""
        try:
            config_info = {
                "energyplus": {
                    "idd_path": self.config.energyplus.idd_path,
                    "installation_path": self.config.energyplus.installation_path,
                    "executable_path": self.config.energyplus.executable_path,
                    "version": self.config.energyplus.version,
                    "weather_data_path": self.config.energyplus.weather_data_path,
                    "default_weather_file": self.config.energyplus.default_weather_file,
                    "example_files_path": self.config.energyplus.example_files_path,
                    "idd_exists": os.path.exists(self.config.energyplus.idd_path) if self.config.energyplus.idd_path else False,
                    "executable_exists": os.path.exists(self.config.energyplus.executable_path) if self.config.energyplus.executable_path else False,
                    "weather_data_exists": os.path.exists(self.config.energyplus.weather_data_path) if self.config.energyplus.weather_data_path else False,
                    "default_weather_file_exists": os.path.exists(self.config.energyplus.default_weather_file) if self.config.energyplus.default_weather_file else False,
                    "example_files_exists": os.path.exists(self.config.energyplus.example_files_path) if self.config.energyplus.example_files_path else False
                },
                "paths": {
                    "workspace_root": self.config.paths.workspace_root,
                    "sample_files_path": self.config.paths.sample_files_path,
                    "temp_dir": self.config.paths.temp_dir,
                    "output_dir": self.config.paths.output_dir
                },
                "server": {
                    "name": self.config.server.name,
                    "version": self.config.server.version,
                    "log_level": self.config.server.log_level,
                    "simulation_timeout": self.config.server.simulation_timeout,
                    "tool_timeout": self.config.server.tool_timeout
                },
                "debug_mode": self.config.debug_mode
            }
            
            return json.dumps(config_info, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting configuration info: {e}")
            raise RuntimeError(f"Error getting configuration info: {str(e)}")
    
    def validate_epjson(self, epjson_path: str) -> str:
        """Validate an epJSON file and return any issues found"""
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.debug(f"Validating epJSON file: {resolved_path}")
            ep = self.load_json(resolved_path)
            
            validation_results = {
                "file_path": resolved_path,
                "is_valid": True,
                "warnings": [],
                "errors": [],
                "summary": {}
            }
            
            # Basic validation checks
            warnings = []
            errors = []
            
            # Check for required objects
            required_objects = ["Building", "Zone", "SimulationControl"]
            for obj_type in required_objects:
                objs = ep.get(obj_type, {})
                if not objs:
                    errors.append(f"Missing required object type: {obj_type}")
                elif len(objs) > 1 and obj_type in ["Building", "SimulationControl"]:
                    warnings.append(f"Multiple {obj_type} objects found (only one expected)")
            
            # Check for zones without surfaces
            zones = ep.get("Zone", {})
            surfaces = ep.get("BuildingSurface:Detailed", {})
            
            zone_names = set(zones.keys())
            surface_zones = {surf_data.get('zone_name', '') for surf_data in surfaces.values()}
            
            zones_without_surfaces = zone_names - surface_zones
            if zones_without_surfaces:
                warnings.append(f"Zones without surfaces: {list(zones_without_surfaces)}")
            
            # Check for materials referenced in constructions
            constructions = ep.get("Construction", {})
            materials = ep.get("Material", {})
            nomass_materials = ep.get("Material:NoMass", {})
            material_names = set(materials.keys()) | set(nomass_materials.keys())
            
            for const_name, const_data in constructions.items():
                # Check all layers in construction
                for i in range(1, 11):  # EnergyPlus supports up to 10 layers
                    layer_key = f"layer_{i}" if i > 1 else "outside_layer"
                    layer_name = const_data.get(layer_key, None)
                    if layer_name and layer_name not in material_names:
                        errors.append(f"Construction '{const_name}' references undefined material: {layer_name}")
            
            # Set validation status
            validation_results["warnings"] = warnings
            validation_results["errors"] = errors
            validation_results["is_valid"] = len(errors) == 0
            
            # Summary
            validation_results["summary"] = {
                "total_warnings": len(warnings),
                "total_errors": len(errors),
                "building_count": len(ep.get("Building", {})),
                "zone_count": len(zones),
                "surface_count": len(surfaces),
                "material_count": len(materials) + len(nomass_materials),
                "construction_count": len(constructions)
            }
            
            logger.debug(f"Validation completed: {len(errors)} errors, {len(warnings)} warnings")
            return json.dumps(validation_results, indent=2)
            
        except Exception as e:
            logger.error(f"Error validating IDF file {resolved_path}: {e}")
            raise RuntimeError(f"Error validating IDF file: {str(e)}")
