"""
EnergyPlus tools with configuration management and simulation control.
Provides comprehensive interface for EnergyPlus epJSON file operations,
simulation execution, and results analysis.
"""

import os
import json
import logging
import shutil
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import calendar
import string
import random

# Optional visualization dependencies
try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    FancyBboxPatch = None

# Optional post-processing dependencies
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    go = None

# Optional diagram generation (requires graphviz)
try:
    from .utils.diagrams import HVACDiagramGenerator
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False
    HVACDiagramGenerator = None

from .config import get_config, Config
from .utils.schedules import ScheduleValueParser
from .utils.output_variables import OutputVariableManager
from .utils.output_meters import OutputMeterManager
from .utils.people_utils import PeopleManager
from .utils.lights_utils import LightsManager
from .utils.electric_equipment_utils import ElectricEquipmentManager
from .utils.run_functions import run

logger = logging.getLogger(__name__)


class EnergyPlusManager:
    """
    Manager class for EnergyPlus epJSON operations with configuration management.
    
    Provides comprehensive interface for:
    - Loading and manipulating epJSON files
    - Running EnergyPlus simulations  
    - Inspecting and modifying building components
    - Analyzing simulation results
    - Managing output variables and meters
    - Visualizing HVAC systems
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the EnergyPlus manager with configuration"""
        self.config = config or get_config()
        
        # Initialize utilities
        self.diagram_generator = HVACDiagramGenerator() if GRAPHVIZ_AVAILABLE else None
        self.output_var_manager = OutputVariableManager(self.config)
        self.output_meter_manager = OutputMeterManager(self.config)
        self.people_manager = PeopleManager()
        self.lights_manager = LightsManager()
        self.electric_equipment_manager = ElectricEquipmentManager()

        logger.info("EnergyPlus Manager initialized for epJSON format")

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
        import subprocess
        from .utils.path_utils import resolve_path
        
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
        from .utils.path_utils import resolve_path
        
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
            from .utils.path_utils import resolve_path
            
            # Determine file description for error messages
            file_description = "file"
            if file_types:
                if '.idf' in file_types:
                    file_description = "IDF file"
                if '.epjson' in file_types.lower():
                    file_description = "epJSON file"
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
            import shutil
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
                from .utils.path_utils import PathResolver
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
    
    # ----------------------------- Model Inspection Methods ------------------------
    def get_model_basics(self, epjson_path: str) -> str:
        """Get basic model information from Building, Site:Location, and SimulationControl"""
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.debug(f"Getting model basics for: {resolved_path}")
            ep = self.load_json(resolved_path)
            basics = {}
            
            # Building information
            building_objs = ep.get("Building", {})
            if building_objs:
                # Get first (and typically only) building
                bldg_name = list(building_objs.keys())[0]
                bldg = building_objs[bldg_name]
                basics["Building"] = {
                    "Name": bldg_name,
                    "North Axis": bldg.get('north_axis', 'Unknown'),
                    "Terrain": bldg.get('terrain', 'Unknown'),
                    "Loads Convergence Tolerance": bldg.get('loads_convergence_tolerance_value', 'Unknown'),
                    "Temperature Convergence Tolerance": bldg.get('temperature_convergence_tolerance_value', 'Unknown'),
                    "Solar Distribution": bldg.get('solar_distribution', 'Unknown'),
                    "Max Warmup Days": bldg.get('maximum_number_of_warmup_days', 'Unknown'),
                    "Min Warmup Days": bldg.get('minimum_number_of_warmup_days', 'Unknown')
                }
            
            # Site:Location information
            site_objs = ep.get("Site:Location", {})
            if site_objs:
                site_name = list(site_objs.keys())[0]
                site = site_objs[site_name]
                basics["Site:Location"] = {
                    "Name": site_name,
                    "Latitude": site.get('latitude', 'Unknown'),
                    "Longitude": site.get('longitude', 'Unknown'),
                    "Time Zone": site.get('time_zone', 'Unknown'),
                    "Elevation": site.get('elevation', 'Unknown')
                }
            
            # SimulationControl information
            sim_objs = ep.get("SimulationControl", {})
            if sim_objs:
                sim_name = list(sim_objs.keys())[0]
                sim = sim_objs[sim_name]
                basics["SimulationControl"] = {
                    "Do Zone Sizing Calculation": sim.get('do_zone_sizing_calculation', 'Unknown'),
                    "Do System Sizing Calculation": sim.get('do_system_sizing_calculation', 'Unknown'),
                    "Do Plant Sizing Calculation": sim.get('do_plant_sizing_calculation', 'Unknown'),
                    "Run Simulation for Sizing Periods": sim.get('run_simulation_for_sizing_periods', 'Unknown'),
                    "Run Simulation for Weather File Run Periods": sim.get('run_simulation_for_weather_file_run_periods', 'Unknown'),
                    "Do HVAC Sizing Simulation for Sizing Periods": sim.get('do_hvac_sizing_simulation_for_sizing_periods', 'Unknown'),
                    "Max Number of HVAC Sizing Simulation Passes": sim.get('maximum_number_of_hvac_sizing_simulation_passes', 'Unknown')
                }
            
            # Version information
            version_objs = ep.get("Version", {})
            if version_objs:
                version_name = list(version_objs.keys())[0]
                version = version_objs[version_name]
                basics["Version"] = {
                    "Version Identifier": version.get('version_identifier', 'Unknown')
                }
            
            logger.debug(f"Model basics extracted for {len(basics)} sections")
            return json.dumps(basics, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting model basics for {resolved_path}: {e}")
            raise RuntimeError(f"Error getting model basics: {str(e)}")
    

    def check_simulation_settings(self, epjson_path: str) -> str:
        """Check SimulationControl and RunPeriod settings with modifiable fields info"""
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.debug(f"Checking simulation settings for: {resolved_path}")
            ep = self.load_json(resolved_path)
            
            settings_info = {
                "file_path": resolved_path,
                "SimulationControl": {
                    "current_values": {},
                    "modifiable_fields": {
                        "Do_Zone_Sizing_Calculation": "Yes/No - Controls zone sizing calculations",
                        "Do_System_Sizing_Calculation": "Yes/No - Controls system sizing calculations", 
                        "Do_Plant_Sizing_Calculation": "Yes/No - Controls plant sizing calculations",
                        "Run_Simulation_for_Sizing_Periods": "Yes/No - Run design day simulations",
                        "Run_Simulation_for_Weather_File_Run_Periods": "Yes/No - Run annual weather file simulation",
                        "Do_HVAC_Sizing_Simulation_for_Sizing_Periods": "Yes/No - Run HVAC sizing simulations",
                        "Maximum_Number_of_HVAC_Sizing_Simulation_Passes": "Integer - Max number of sizing passes (typically 1-3)"
                    }
                },
                "RunPeriod": {
                    "current_values": [],
                    "modifiable_fields": {
                        "Name": "String - Name of the run period",
                        "Begin_Month": "Integer 1-12 - Starting month",
                        "Begin_Day_of_Month": "Integer 1-31 - Starting day", 
                        "Begin_Year": "Integer - Starting year (optional)",
                        "End_Month": "Integer 1-12 - Ending month",
                        "End_Day_of_Month": "Integer 1-31 - Ending day",
                        "End_Year": "Integer - Ending year (optional)",
                        "Day_of_Week_for_Start_Day": "String - Monday/Tuesday/etc or UseWeatherFile",
                        "Use_Weather_File_Holidays_and_Special_Days": "Yes/No",
                        "Use_Weather_File_Daylight_Saving_Period": "Yes/No",
                        "Apply_Weekend_Holiday_Rule": "Yes/No",
                        "Use_Weather_File_Rain_Indicators": "Yes/No",
                        "Use_Weather_File_Snow_Indicators": "Yes/No"
                    }
                }
            }
            
            # Get current SimulationControl values
            sim_objs = ep.get("SimulationControl", {})
            if sim_objs:
                sim_name = list(sim_objs.keys())[0]
                sim = sim_objs[sim_name]
                settings_info["SimulationControl"]["current_values"] = {
                    "Do_Zone_Sizing_Calculation": sim.get('do_zone_sizing_calculation', 'Unknown'),
                    "Do_System_Sizing_Calculation": sim.get('do_system_sizing_calculation', 'Unknown'),
                    "Do_Plant_Sizing_Calculation": sim.get('do_plant_sizing_calculation', 'Unknown'),
                    "Run_Simulation_for_Sizing_Periods": sim.get('run_simulation_for_sizing_periods', 'Unknown'),
                    "Run_Simulation_for_Weather_File_Run_Periods": sim.get('run_simulation_for_weather_file_run_periods', 'Unknown'),
                    "Do_HVAC_Sizing_Simulation_for_Sizing_Periods": sim.get('do_hvac_sizing_simulation_for_sizing_periods', 'Unknown'),
                    "Maximum_Number_of_HVAC_Sizing_Simulation_Passes": sim.get('maximum_number_of_hvac_sizing_simulation_passes', 'Unknown')
                }
            else:
                settings_info["SimulationControl"]["error"] = "No SimulationControl object found"
            
            # Get current RunPeriod values  
            run_objs = ep.get("RunPeriod", {})
            for i, (run_name, run_period) in enumerate(run_objs.items()):
                run_data = {
                    "index": i,
                    "Name": run_name,
                    "Begin_Month": run_period.get('begin_month', 'Unknown'),
                    "Begin_Day_of_Month": run_period.get('begin_day_of_month', 'Unknown'),
                    "Begin_Year": run_period.get('begin_year', 'Unknown'),
                    "End_Month": run_period.get('end_month', 'Unknown'),
                    "End_Day_of_Month": run_period.get('end_day_of_month', 'Unknown'),
                    "End_Year": run_period.get('end_year', 'Unknown'),
                    "Day_of_Week_for_Start_Day": run_period.get('day_of_week_for_start_day', 'Unknown'),
                    "Use_Weather_File_Holidays_and_Special_Days": run_period.get('use_weather_file_holidays_and_special_days', 'Unknown'),
                    "Use_Weather_File_Daylight_Saving_Period": run_period.get('use_weather_file_daylight_saving_period', 'Unknown'),
                    "Apply_Weekend_Holiday_Rule": run_period.get('apply_weekend_holiday_rule', 'Unknown'),
                    "Use_Weather_File_Rain_Indicators": run_period.get('use_weather_file_rain_indicators', 'Unknown'),
                    "Use_Weather_File_Snow_Indicators": run_period.get('use_weather_file_snow_indicators', 'Unknown')
                }
                settings_info["RunPeriod"]["current_values"].append(run_data)
            
            if not run_objs:
                settings_info["RunPeriod"]["error"] = "No RunPeriod objects found"
            
            logger.debug(f"Found {len(sim_objs)} SimulationControl and {len(run_objs)} RunPeriod objects")
            return json.dumps(settings_info, indent=2)
            
        except Exception as e:
            logger.error(f"Error checking simulation settings for {resolved_path}: {e}")
            raise RuntimeError(f"Error checking simulation settings: {str(e)}")
    
    
    def list_zones(self, epjson_path: str) -> str:
        """List all zones in the model"""
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.debug(f"Listing zones for: {resolved_path}")
            ep = self.load_json(resolved_path)
            zones = ep.get("Zone", {})
            
            zone_info = []
            for i, (zone_name, zone) in enumerate(zones.items()):
                zone_data = {
                    "Index": i + 1,
                    "Name": zone_name,
                    "Direction of Relative North": zone.get('direction_of_relative_north', 'Unknown'),
                    "X Origin": zone.get('x_origin', 'Unknown'),
                    "Y Origin": zone.get('y_origin', 'Unknown'),
                    "Z Origin": zone.get('z_origin', 'Unknown'),
                    "Type": zone.get('type', 'Unknown'),
                    "Multiplier": zone.get('multiplier', 'Unknown'),
                    "Ceiling Height": zone.get('ceiling_height', 'autocalculate'),
                    "Volume": zone.get('volume', 'autocalculate')
                }
                zone_info.append(zone_data)
            
            logger.debug(f"Found {len(zone_info)} zones")
            return json.dumps(zone_info, indent=2)
            
        except Exception as e:
            logger.error(f"Error listing zones for {resolved_path}: {e}")
            raise RuntimeError(f"Error listing zones: {str(e)}")
    

    def get_surfaces(self, epjson_path: str) -> str:
        """Get detailed surface information"""
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.debug(f"Getting surfaces for: {resolved_path}")
            ep = self.load_json(resolved_path)
            surfaces = ep.get("BuildingSurface:Detailed", {})
            
            surface_info = []
            for i, (surf_name, surface) in enumerate(surfaces.items()):
                surface_data = {
                    "Index": i + 1,
                    "Name": surf_name,
                    "Surface Type": surface.get('surface_type', 'Unknown'),
                    "Construction Name": surface.get('construction_name', 'Unknown'),
                    "Zone Name": surface.get('zone_name', 'Unknown'),
                    "Outside Boundary Condition": surface.get('outside_boundary_condition', 'Unknown'),
                    "Sun Exposure": surface.get('sun_exposure', 'Unknown'),
                    "Wind Exposure": surface.get('wind_exposure', 'Unknown'),
                    "Number of Vertices": surface.get('number_of_vertices', 'Unknown')
                }
                surface_info.append(surface_data)
            
            logger.debug(f"Found {len(surface_info)} surfaces")
            return json.dumps(surface_info, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting surfaces for {resolved_path}: {e}")
            raise RuntimeError(f"Error getting surfaces: {str(e)}")
    

    def get_materials(self, epjson_path: str) -> str:
        """Get material information"""
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.debug(f"Getting materials for: {resolved_path}")
            ep = self.load_json(resolved_path)
            
            materials = []
            
            # Regular materials
            material_objs = ep.get("Material", {})
            for mat_name, material in material_objs.items():
                material_data = {
                    "Type": "Material",
                    "Name": mat_name,
                    "Roughness": material.get('roughness', 'Unknown'),
                    "Thickness": material.get('thickness', 'Unknown'),
                    "Conductivity": material.get('conductivity', 'Unknown'),
                    "Density": material.get('density', 'Unknown'),
                    "Specific Heat": material.get('specific_heat', 'Unknown')
                }
                materials.append(material_data)
            
            # No-mass materials
            nomass_objs = ep.get("Material:NoMass", {})
            for mat_name, material in nomass_objs.items():
                material_data = {
                    "Type": "Material:NoMass",
                    "Name": mat_name,
                    "Roughness": material.get('roughness', 'Unknown'),
                    "Thermal Resistance": material.get('thermal_resistance', 'Unknown'),
                    "Thermal Absorptance": material.get('thermal_absorptance', 'Unknown'),
                    "Solar Absorptance": material.get('solar_absorptance', 'Unknown'),
                    "Visible Absorptance": material.get('visible_absorptance', 'Unknown')
                }
                materials.append(material_data)
            
            logger.debug(f"Found {len(materials)} materials")
            return json.dumps(materials, indent=2)
            
        except Exception as e:
            logger.error(f"Error getting materials for {resolved_path}: {e}")
            raise RuntimeError(f"Error getting materials: {str(e)}")
    

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


    # ----------------------- Schedule Inspector Module ------------------------
    def inspect_schedules(self, epjson_path: str, include_values: bool = False) -> str:
        """
        Inspect and inventory all schedule objects in the EnergyPlus model
        
        Args:
            epjson_path: Path to the epJSON file
            include_values: Whether to extract actual schedule values (default: False)
        
        Returns:
            JSON string with schedule inventory and analysis
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.debug(f"Inspecting schedules for: {resolved_path} (include_values={include_values})")
            ep = self.load_json(resolved_path)
            
            # Define all schedule object types to inspect
            schedule_object_types = [
                "ScheduleTypeLimits",
                "Schedule:Day:Hourly", 
                "Schedule:Day:Interval",
                "Schedule:Day:List",
                "Schedule:Week:Daily",
                "Schedule:Week:Compact", 
                "Schedule:Year",
                "Schedule:Compact",
                "Schedule:Constant",
                "Schedule:File",
                "Schedule:File:Shading"
            ]
            
            schedule_inventory = {
                "file_path": resolved_path,
                "include_values": include_values,
                "summary": {
                    "total_schedule_objects": 0,
                    "schedule_types_found": [],
                    "schedule_type_limits_count": 0,
                    "day_schedules_count": 0,
                    "week_schedules_count": 0, 
                    "annual_schedules_count": 0
                },
                "schedule_type_limits": [],
                "day_schedules": [],
                "week_schedules": [],
                "annual_schedules": [],
                "other_schedules": []
            }
            
            # Inspect ScheduleTypeLimits
            schedule_type_limits = ep.get("ScheduleTypeLimits", {})
            for stl_name, stl in schedule_type_limits.items():
                stl_info = {
                    "name": stl_name,
                    "lower_limit": stl.get('lower_limit_value', 'Not specified'),
                    "upper_limit": stl.get('upper_limit_value', 'Not specified'),
                    "numeric_type": stl.get('numeric_type', 'Not specified'),
                    "unit_type": stl.get('unit_type', 'Not specified')
                }
                schedule_inventory["schedule_type_limits"].append(stl_info)
            
            # Inspect Day Schedules
            day_schedule_types = ["Schedule:Day:Hourly", "Schedule:Day:Interval", "Schedule:Day:List"]
            for day_type in day_schedule_types:
                day_schedules = ep.get(day_type, {})
                for day_name, day_sched in day_schedules.items():
                    day_info = {
                        "object_type": day_type,
                        "name": day_name,
                        "schedule_type_limits": day_sched.get('schedule_type_limits_name', 'Not specified')
                    }
                    
                    # Add type-specific fields
                    if day_type == "Schedule:Day:Hourly":
                        # For hourly, we could count non-zero hours, but keep simple for now
                        day_info["profile_type"] = "24 hourly values"
                    elif day_type == "Schedule:Day:Interval":
                        day_info["interpolate_to_timestep"] = day_sched.get('interpolate_to_timestep', 'No')
                    elif day_type == "Schedule:Day:List":
                        day_info["interpolate_to_timestep"] = day_sched.get('interpolate_to_timestep', 'No')
                        day_info["minutes_per_item"] = day_sched.get('minutes_per_item', 'Not specified')
                    
                    # Extract values if requested
                    if include_values:
                        try:
                            values = ScheduleValueParser.parse_schedule_values(day_sched, day_type)
                            if values:
                                day_info["values"] = values
                        except Exception as e:
                            logger.warning(f"Failed to extract values for {day_info['name']}: {e}")
                            day_info["values"] = {"error": f"Value extraction failed: {str(e)}"}
                    
                    schedule_inventory["day_schedules"].append(day_info)
            
            # Inspect Week Schedules  
            week_schedule_types = ["Schedule:Week:Daily", "Schedule:Week:Compact"]
            for week_type in week_schedule_types:
                week_schedules = ep.get(week_type, {})
                for week_name, week_sched in week_schedules.items():
                    week_info = {
                        "object_type": week_type,
                        "name": week_name
                    }
                    
                    if week_type == "Schedule:Week:Daily":
                        # Extract day schedule references
                        day_types = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday',
                                   'holiday', 'summerdesignday', 'winterdesignday', 'customday1', 'customday2']
                        day_refs = {}
                        for day_type in day_types:
                            field_name = f"{day_type}_schedule_day_name"
                            day_refs[day_type] = week_sched.get(field_name, 'Not specified')
                        week_info["day_schedule_references"] = day_refs
                    
                    # Note: Week schedules don't have direct values, they reference day schedules
                    
                    schedule_inventory["week_schedules"].append(week_info)
            
            # Inspect Annual/Full Schedules
            annual_schedule_types = ["Schedule:Year", "Schedule:Compact", "Schedule:Constant", "Schedule:File"]
            for annual_type in annual_schedule_types:
                annual_schedules = ep.get(annual_type, {})
                for annual_name, annual_sched in annual_schedules.items():
                    annual_info = {
                        "object_type": annual_type,
                        "name": annual_name,
                        "schedule_type_limits": annual_sched.get('schedule_type_limits_name', 'Not specified')
                    }
                    
                    # Add type-specific fields
                    if annual_type == "Schedule:Constant":
                        annual_info["hourly_value"] = annual_sched.get('hourly_value', 'Not specified')
                    elif annual_type == "Schedule:File":
                        annual_info["file_name"] = annual_sched.get('file_name', 'Not specified')
                        annual_info["column_number"] = annual_sched.get('column_number', 'Not specified')
                        annual_info["number_of_hours"] = annual_sched.get('number_of_hours_of_data', 'Not specified')
                        # Skip Schedule:File value extraction as requested
                        if include_values:
                            annual_info["values"] = {"note": "Schedule:File value extraction skipped"}
                    
                    # Extract values if requested (for Schedule:Compact and Schedule:Constant)
                    if include_values and annual_type in ["Schedule:Compact", "Schedule:Constant"]:
                        try:
                            values = ScheduleValueParser.parse_schedule_values(annual_sched, annual_type)
                            if values:
                                annual_info["values"] = values
                        except Exception as e:
                            logger.warning(f"Failed to extract values for {annual_info['name']}: {e}")
                            annual_info["values"] = {"error": f"Value extraction failed: {str(e)}"}
                    
                    schedule_inventory["annual_schedules"].append(annual_info)
            
            # Handle Schedule:File:Shading separately
            shading_schedules = ep.get("Schedule:File:Shading", {})
            for shading_name, shading_sched in shading_schedules.items():
                other_info = {
                    "object_type": "Schedule:File:Shading",
                    "name": shading_name,
                    "file_name": shading_sched.get('file_name', 'Not specified'),
                    "purpose": "Shading schedules for exterior surfaces"
                }
                # Skip shading schedule value extraction
                if include_values:
                    other_info["values"] = {"note": "Schedule:File:Shading value extraction skipped"}
                
                schedule_inventory["other_schedules"].append(other_info)
            
            # Calculate summary statistics
            total_objects = (len(schedule_inventory["schedule_type_limits"]) + 
                            len(schedule_inventory["day_schedules"]) +
                            len(schedule_inventory["week_schedules"]) + 
                            len(schedule_inventory["annual_schedules"]) +
                            len(schedule_inventory["other_schedules"]))
            
            schedule_inventory["summary"] = {
                "total_schedule_objects": total_objects,
                "schedule_type_limits_count": len(schedule_inventory["schedule_type_limits"]),
                "day_schedules_count": len(schedule_inventory["day_schedules"]),
                "week_schedules_count": len(schedule_inventory["week_schedules"]),
                "annual_schedules_count": len(schedule_inventory["annual_schedules"]),
                "other_schedules_count": len(schedule_inventory["other_schedules"]),
                "schedule_types_found": [
                    obj_type for obj_type in schedule_object_types 
                    if len(ep.get(obj_type, {})) > 0
                ]
            }
            
            # Add value extraction summary if values were requested
            if include_values:
                value_extraction_summary = {
                    "schedules_with_values": 0,
                    "schedules_with_errors": 0,
                    "skipped_file_schedules": 0
                }
                
                all_schedules = (schedule_inventory["day_schedules"] + 
                               schedule_inventory["annual_schedules"] + 
                               schedule_inventory["other_schedules"])
                
                for sched in all_schedules:
                    if "values" in sched:
                        if "error" in sched["values"]:
                            value_extraction_summary["schedules_with_errors"] += 1
                        elif "note" in sched["values"]:
                            value_extraction_summary["skipped_file_schedules"] += 1
                        else:
                            value_extraction_summary["schedules_with_values"] += 1
                
                schedule_inventory["summary"]["value_extraction"] = value_extraction_summary
            
            logger.debug(f"Found {total_objects} schedule objects across {len(schedule_inventory['summary']['schedule_types_found'])} object types")
            logger.info(f"Schedule inspection for {resolved_path} completed successfully")
            return json.dumps(schedule_inventory, indent=2)
            
        except Exception as e:
            logger.error(f"Error inspecting schedules for {resolved_path}: {e}")
            raise RuntimeError(f"Error inspecting schedules: {str(e)}")




    # ------------------------ Loop Discovery and Topology ------------------------
    def discover_hvac_loops(self, epjson_path: str) -> str:
        """Discover all HVAC loops (Plant, Condenser, Air) in the EnergyPlus model
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.debug(f"Discovering HVAC loops for: {resolved_path}")
            ep = self.load_json(resolved_path)
            
            hvac_info = {
                "file_path": resolved_path,
                "plant_loops": [],
                "condenser_loops": [],
                "air_loops": [],
                "summary": {
                    "total_plant_loops": 0,
                    "total_condenser_loops": 0,
                    "total_air_loops": 0,
                    "total_zones": 0
                }
            }
            
            # # Discover Plant Loops
            plant_loops = ep.get("PlantLoop", {})
            for i, (loop_name, loop_data) in enumerate(plant_loops.items()):
                loop_info = {
                    "index": i + 1,
                    "name": loop_name,
                    "fluid_type": loop_data.get("fluid_type", "Unknown"),
                    "max_loop_flow_rate": loop_data.get("maximum_loop_flow_rate", "Uknown"),
                    "loop_inlet_node": loop_data.get("plant_side_inlet_node_name", "Uknown"),
                    "loop_outlet_node": loop_data.get("plant_side_outlet_node_name", "Uknown"),
                    "demand_inlet_node": loop_data.get("demand_side_inlet_node_name", "Uknown"),
                    "demand_outlet_node": loop_data.get("demand_side_outlet_node_name", "Uknown")
                }
                hvac_info["plant_loops"].append(loop_info)

            # Discover Condenser Loops
            condenser_loops = ep.get("CondenserLoop", {})
            for i, (loop_name, loop_data) in enumerate(condenser_loops.items()):
                loop_info = {
                    "index": i + 1,
                    "name": loop_name,
                    "fluid_type": loop_data.get("fluid_type", "Unknown"),
                    "max_loop_flow_rate": loop_data.get("maximum_loop_flow_rate", "Unknown"),
                    "loop_inlet_node": loop_data.get("condenser_side_inlet_node_name", "Unknown"),
                    "loop_outlet_node": loop_data.get("condenser_side_outlet_node_name", "Unknown"),
                    "demand_inlet_node": loop_data.get("demand_side_inlet_node_name", "Unknown"),
                    "demand_outlet_node": loop_data.get("demand_side_outlet_node_name", "Unknown")            }
                hvac_info["condenser_loops"].append(loop_info)

            # Discover Air Loops
            air_loops = ep.get("AirLoopHVAC", {})
            for i, (loop_name, loop_data) in enumerate(air_loops.items()):
                loop_info = {
                    "index": i + 1,
                    "name": loop_name,
                    "supply_inlet_node": loop_data.get("supply_side_inlet_node_name", "Unknown"),
                    "supply_outlet_node": loop_data.get("supply_side_outlet_node_name", "Unknown"),
                    "demand_inlet_node": loop_data.get("demand_side_inlet_node_names", "Unknown"),
                    "demand_outlet_node": loop_data.get("demand_side_outlet_node_names", "Unknown")
                }
                hvac_info["air_loops"].append(loop_info)
            
            # Get zone count for context
            zones = ep.get("Zone", {})

            # Update summary
            hvac_info["summary"] = {
                "total_plant_loops": len(plant_loops),
                "total_condenser_loops": len(condenser_loops),
                "total_air_loops": len(air_loops),
                "total_zones": len(zones)
            }

            return json.dumps(hvac_info, indent=2)
            
        except Exception as e:
            logger.error(f"Error discovering HVAC loops for {epjson_path}: {e}")
            raise RuntimeError(f"Error discovering HVAC loops: {str(e)}")


    def get_loop_topology(self, epjson_path: str, loop_name: str) -> str:
        """Get detailed topology information for a specific HVAC loop"""
        resolved_path = self._resolve_epjson_path(epjson_path)
        try:
            logger.debug(f"Getting loop topology for '{loop_name}' in: {resolved_path}")
            ep = self.load_json(resolved_path)

            # Try to find the loop in different loop types
            loop_obj = None
            loop_type = None
            
            # Discover Plant Loops
            plant_loops = ep.get("PlantLoop", {})
            condenser_loops = ep.get("CondenserLoop", {})
            air_loops = ep.get("AirLoopHVAC", {})
            
            if loop_name in plant_loops:
                loop_type = "PlantLoop"
                loop_obj = plant_loops[loop_name]
            elif loop_name in condenser_loops:
                loop_type = "CondenserLoop"
                loop_obj = condenser_loops[loop_name]
            elif loop_name in air_loops:
                loop_type = "AirLoopHVAC"
                loop_obj = air_loops[loop_name]

            if not loop_obj:
                raise ValueError(f"Loop '{loop_name}' not found in the IDF file")
                
            topology_info = {
                "loop_name": loop_name,
                "loop_type": loop_type,
                "supply_side": {
                    "branches": [],
                    "inlet_node": "",
                    "outlet_node": "",
                    "connector_lists": []
                },
                "demand_side": {
                    "branches": [],
                    "inlet_node": "",
                    "outlet_node": "",
                    "connector_lists": []
                }
            }

            # Handle AirLoopHVAC differently from Plant/Condenser loops
            if loop_type == "AirLoopHVAC":
                topology_info = self._get_airloop_topology(ep, loop_obj, loop_name)
            else:
                # Handle Plant and Condenser loops (existing logic)
                topology_info = self._get_plant_condenser_topology(ep, loop_obj, loop_type, loop_name)
            
            logger.debug(f"Topology extracted for loop '{loop_name}' of type {loop_type}")
            return json.dumps(topology_info, indent=2)

        except Exception as e:
            logger.error(f"Error getting loop topology for {resolved_path}: {e}")
            raise RuntimeError(f"Error getting loop topology: {str(e)}")


    def _get_airloop_topology(self, ep, loop_obj, loop_name: str) -> Dict[str, Any]:
        """Get topology information specifically for AirLoopHVAC systems"""
        
        # Debug: Print all available fields in the loop object
        logger.debug(f"Loop object fields for {loop_name}:")
        for field, value in loop_obj.items():
            if isinstance(value, (str, int, float)) and str(value).strip():
                logger.debug(f"  {field}: {value}")

        topology_info = {
            "loop_name": loop_name,
            "loop_type": "AirLoopHVAC",
            "supply_side": {
                "branches": [],
                "inlet_node": loop_obj.get("supply_side_inlet_node_name", "Unknown"),
                "outlet_node": loop_obj.get("supply_side_outlet_node_name", "Unknown"),
                "components": [],
                "supply_paths": []
            },
            "demand_side": {
                "inlet_node": loop_obj.get("demand_side_inlet_node_names", "Unknown"),
                "outlet_node": loop_obj.get("demand_side_outlet_node_names", "Unknown"),
                "zone_splitters": [],
                "zone_mixers": [],
                "return_plenums": [],
                "zone_equipment": [],
                "supply_paths": [],
                "return_paths": []
            }
        }
        
        # Get supply side branches (main equipment) - try different possible field names
        supply_branch_list_name = loop_obj.get("plant_side_branch_list_name", "Unknown"),
        logger.debug(f"Branch list name from loop object: '{supply_branch_list_name}'")
        
        if supply_branch_list_name:
            supply_branches = self._get_branches_from_list(ep, supply_branch_list_name)
            logger.debug(f"Found {len(supply_branches)} supply branches")
            topology_info["supply_side"]["branches"] = supply_branches
            
            # Also extract components from supply branches for easier access
            components = []
            for branch in supply_branches:
                components.extend(branch.get("components", []))
            topology_info["supply_side"]["components"] = components
            logger.debug(f"Found {len(components)} supply components")
        
        # Get AirLoopHVAC:SupplyPath objects - find by matching demand inlet node
        demand_inlet_node = topology_info["demand_side"]["inlet_node"]
        logger.debug(f"Looking for supply paths with inlet node: '{demand_inlet_node}'")
        supply_paths = self._get_airloop_supply_paths_by_node(ep, demand_inlet_node)
        topology_info["demand_side"]["supply_paths"] = supply_paths
        logger.debug(f"Found {len(supply_paths)} supply paths")
        
        # Get AirLoopHVAC:ReturnPath objects - find by matching demand outlet node
        demand_outlet_node = topology_info["demand_side"]["outlet_node"]
        logger.debug(f"Looking for return paths with outlet node: '{demand_outlet_node}'")
        return_paths = self._get_airloop_return_paths_by_node(ep, demand_outlet_node)
        topology_info["demand_side"]["return_paths"] = return_paths
        logger.debug(f"Found {len(return_paths)} return paths")
        
        # Get zone splitters from supply paths
        zone_splitters = []
        for supply_path in supply_paths:
            for component in supply_path.get("components", []):
                if component["type"] == "AirLoopHVAC:ZoneSplitter":
                    splitter_details = self._get_airloop_zone_splitter_details(ep, component["name"])
                    if splitter_details:
                        zone_splitters.append(splitter_details)
        topology_info["demand_side"]["zone_splitters"] = zone_splitters
        
        # Get zone mixers from return paths
        zone_mixers = []
        return_plenums = []
        for return_path in return_paths:
            for component in return_path.get("components", []):
                if component["type"] == "AirLoopHVAC:ZoneMixer":
                    mixer_details = self._get_airloop_zone_mixer_details(ep, component["name"])
                    if mixer_details:
                        zone_mixers.append(mixer_details)
                elif component["type"] == "AirLoopHVAC:ReturnPlenum":
                    plenum_details = self._get_airloop_return_plenum_details(ep, component["name"])
                    if plenum_details:
                        return_plenums.append(plenum_details)
        topology_info["demand_side"]["zone_mixers"] = zone_mixers
        topology_info["demand_side"]["return_plenums"] = return_plenums
        
        # Get zone equipment connected to splitters
        zone_equipment = []
        for splitter in zone_splitters:
            for outlet_node in splitter.get("outlet_nodes", []):
                equipment = self._get_zone_equipment_for_node(ep, outlet_node)
                zone_equipment.extend(equipment)
        topology_info["demand_side"]["zone_equipment"] = zone_equipment
        
        return topology_info

    def _get_plant_condenser_topology(self, ep, loop_obj, loop_type: str, loop_name: str) -> Dict[str, Any]:
        """Get topology information for Plant and Condenser loops using epJSON"""
        topology_info = {
            "loop_name": loop_name,
            "loop_type": loop_type,
            "supply_side": {
                "branches": [],
                "inlet_node": "",
                "outlet_node": "",
                "connector_lists": []
            },
            "demand_side": {
                "branches": [],
                "inlet_node": "",
                "outlet_node": "",
                "connector_lists": []
            }
        }
        
        # Get supply side information (epJSON format - lowercase with underscores)
        if loop_type == "PlantLoop":
            topology_info["supply_side"]["inlet_node"] = loop_obj.get("plant_side_inlet_node_name", "Unknown")
            topology_info["supply_side"]["outlet_node"] = loop_obj.get("plant_side_outlet_node_name", "Unknown")
        elif loop_type == "CondenserLoop":
            topology_info["supply_side"]["inlet_node"] = loop_obj.get("condenser_side_inlet_node_name", "Unknown")
            topology_info["supply_side"]["outlet_node"] = loop_obj.get("condenser_side_outlet_node_name", "Unknown")
        
        # Get demand side information
        topology_info["demand_side"]["inlet_node"] = loop_obj.get("demand_side_inlet_node_name", "Unknown")
        topology_info["demand_side"]["outlet_node"] = loop_obj.get("demand_side_outlet_node_name", "Unknown")
        
        # Get branch information
        if loop_type == "PlantLoop":
            supply_branch_list_name = loop_obj.get("plant_side_branch_list_name", "")
        elif loop_type == "CondenserLoop":
            supply_branch_list_name = loop_obj.get("condenser_side_branch_list_name", "")
        else:
            supply_branch_list_name = loop_obj.get("supply_side_branch_list_name", "")
        
        demand_branch_list_name = loop_obj.get("demand_side_branch_list_name", "")
        
        # Get supply side branches
        if supply_branch_list_name:
            supply_branches = self._get_branches_from_list(ep, supply_branch_list_name)
            topology_info["supply_side"]["branches"] = supply_branches
        
        # Get demand side branches
        if demand_branch_list_name:
            demand_branches = self._get_branches_from_list(ep, demand_branch_list_name)
            topology_info["demand_side"]["branches"] = demand_branches
        
        # Get connector information (splitters/mixers)
        if loop_type == "PlantLoop":
            supply_connector_list = loop_obj.get("plant_side_connector_list_name", "")
        elif loop_type == "CondenserLoop":
            supply_connector_list = loop_obj.get("condenser_side_connector_list_name", "")
        else:
            supply_connector_list = loop_obj.get("supply_side_connector_list_name", "")
        
        demand_connector_list = loop_obj.get("demand_side_connector_list_name", "")
        
        if supply_connector_list:
            topology_info["supply_side"]["connector_lists"] = self._get_connectors_from_list(ep, supply_connector_list)
        
        if demand_connector_list:
            topology_info["demand_side"]["connector_lists"] = self._get_connectors_from_list(ep, demand_connector_list)
        
        return topology_info

    def _get_airloop_supply_paths_by_node(self, ep, inlet_node: str) -> List[Dict[str, Any]]:
        """Get AirLoopHVAC:SupplyPath objects that match the specified inlet node (epJSON)"""
        supply_paths = []
        
        supply_path_objs = ep.get("AirLoopHVAC:SupplyPath", {})
        for path_name, supply_path in supply_path_objs.items():
            path_inlet_node = supply_path.get("supply_air_path_inlet_node_name", "")
            if path_inlet_node == inlet_node:
                path_info = {
                    "name": path_name,
                    "inlet_node": path_inlet_node,
                    "components": []
                }
                
                # Get components in the supply path
                for i in range(1, 10):  # Supply paths can have multiple components
                    comp_type_field = f"component_{i}_object_type" if i > 1 else "component_1_object_type"
                    comp_name_field = f"component_{i}_name" if i > 1 else "component_1_name"
                    
                    comp_type = supply_path.get(comp_type_field)
                    comp_name = supply_path.get(comp_name_field)
                    
                    if not comp_type or not comp_name:
                        break
                    
                    component_info = {
                        "type": comp_type,
                        "name": comp_name
                    }
                    path_info["components"].append(component_info)
                
                supply_paths.append(path_info)
        
        return supply_paths

    def _get_airloop_return_paths_by_node(self, ep, outlet_node: str) -> List[Dict[str, Any]]:
        """Get AirLoopHVAC:ReturnPath objects that match the specified outlet node (epJSON)"""
        return_paths = []
        
        return_path_objs = ep.get("AirLoopHVAC:ReturnPath", {})
        for path_name, return_path in return_path_objs.items():
            path_outlet_node = return_path.get("return_air_path_outlet_node_name", "")
            if path_outlet_node == outlet_node:
                path_info = {
                    "name": path_name,
                    "outlet_node": path_outlet_node,
                    "components": []
                }
                
                # Get components in the return path
                for i in range(1, 10):  # Return paths can have multiple components
                    comp_type_field = f"component_{i}_object_type" if i > 1 else "component_1_object_type"
                    comp_name_field = f"component_{i}_name" if i > 1 else "component_1_name"
                    
                    comp_type = return_path.get(comp_type_field)
                    comp_name = return_path.get(comp_name_field)
                    
                    if not comp_type or not comp_name:
                        break
                    
                    component_info = {
                        "type": comp_type,
                        "name": comp_name
                    }
                    path_info["components"].append(component_info)
                
                return_paths.append(path_info)
        
        return return_paths

    def _get_zone_equipment_for_node(self, ep, inlet_node: str) -> List[Dict[str, Any]]:
        """Get zone equipment objects connected to the specified inlet node (epJSON)"""
        zone_equipment = []
        
        # Common zone equipment types that might be connected to air loop nodes
        air_terminal_types = [
            "AirTerminal:SingleDuct:Uncontrolled",
            "AirTerminal:SingleDuct:VAV:Reheat",
            "AirTerminal:SingleDuct:VAV:NoReheat", 
            "AirTerminal:SingleDuct:ConstantVolume:Reheat",
            "AirTerminal:SingleDuct:ConstantVolume:NoReheat",
            "AirTerminal:DualDuct:VAV",
            "AirTerminal:DualDuct:ConstantVolume",
            "ZoneHVAC:Baseboard:Convective:Electric",
            "ZoneHVAC:Baseboard:Convective:Water",
            "ZoneHVAC:PackagedTerminalAirConditioner",
            "ZoneHVAC:PackagedTerminalHeatPump",
            "ZoneHVAC:WindowAirConditioner",
            "ZoneHVAC:UnitHeater",
            "ZoneHVAC:UnitVentilator",
            "ZoneHVAC:EnergyRecoveryVentilator",
            "ZoneHVAC:FourPipeFanCoil",
            "ZoneHVAC:IdealLoadsAirSystem"
        ]
        
        for terminal_type in air_terminal_types:
            terminals = ep.get(terminal_type, {})
            for terminal_name, terminal in terminals.items():
                # Check multiple possible field names for inlet node (epJSON format)
                terminal_inlet = (terminal.get("air_inlet_node_name", "") or 
                                terminal.get("air_inlet_node", "") or
                                terminal.get("supply_air_inlet_node_name", "") or
                                terminal.get("zone_supply_air_node_name", ""))
                
                if terminal_inlet == inlet_node:
                    equipment_info = {
                        "type": terminal_type,
                        "name": terminal_name,
                        "inlet_node": terminal_inlet,
                        "outlet_node": (terminal.get("air_outlet_node_name", "") or 
                                      terminal.get("air_outlet_node", "") or
                                      terminal.get("zone_air_node_name", "Unknown"))
                    }
                    
                    # Add zone name if available
                    if "zone_name" in terminal:
                        equipment_info["zone_name"] = terminal.get("zone_name", "Unknown")
                    
                    zone_equipment.append(equipment_info)
        
        return zone_equipment

    def _get_airloop_zone_splitter_details(self, ep, splitter_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an AirLoopHVAC:ZoneSplitter (epJSON)"""
        splitter_objs = ep.get("AirLoopHVAC:ZoneSplitter", {})
        
        if splitter_name in splitter_objs:
            splitter = splitter_objs[splitter_name]
            splitter_info = {
                "name": splitter_name,
                "type": "AirLoopHVAC:ZoneSplitter",
                "inlet_node": splitter.get("inlet_node_name", "Unknown"),
                "outlet_nodes": []
            }
            
            # Get all outlet nodes
            for i in range(1, 50):  # Zone splitters can have many outlets
                outlet_field = f"outlet_{i}_node_name" if i > 1 else "outlet_1_node_name"
                outlet_node = splitter.get(outlet_field)
                if not outlet_node:
                    break
                splitter_info["outlet_nodes"].append(outlet_node)
            
            return splitter_info
        
        return None

    def _get_airloop_zone_mixer_details(self, ep, mixer_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an AirLoopHVAC:ZoneMixer (epJSON)"""
        mixer_objs = ep.get("AirLoopHVAC:ZoneMixer", {})
        
        if mixer_name in mixer_objs:
            mixer = mixer_objs[mixer_name]
            mixer_info = {
                "name": mixer_name,
                "type": "AirLoopHVAC:ZoneMixer",
                "outlet_node": mixer.get("outlet_node_name", "Unknown"),
                "inlet_nodes": []
            }
            
            # Get all inlet nodes
            for i in range(1, 50):  # Zone mixers can have many inlets
                inlet_field = f"inlet_{i}_node_name" if i > 1 else "inlet_1_node_name"
                inlet_node = mixer.get(inlet_field)
                if not inlet_node:
                    break
                mixer_info["inlet_nodes"].append(inlet_node)
            
            return mixer_info
        
        return None

    def _get_airloop_return_plenum_details(self, ep, plenum_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an AirLoopHVAC:ReturnPlenum (epJSON)"""
        plenum_objs = ep.get("AirLoopHVAC:ReturnPlenum", {})
        
        if plenum_name in plenum_objs:
            plenum = plenum_objs[plenum_name]
            plenum_info = {
                "name": plenum_name,
                "type": "AirLoopHVAC:ReturnPlenum",
                "zone_name": plenum.get("zone_name", "Unknown"),
                "zone_node_name": plenum.get("zone_node_name", "Unknown"),
                "outlet_node": plenum.get("outlet_node_name", "Unknown"),
                "induced_air_outlet_node": plenum.get("induced_air_outlet_node_or_nodelist_name", ""),
                "inlet_nodes": []
            }
            
            # Get all inlet nodes
            for i in range(1, 50):  # Return plenums can have many inlets
                inlet_field = f"inlet_{i}_node_name" if i > 1 else "inlet_1_node_name"
                inlet_node = plenum.get(inlet_field)
                if not inlet_node:
                    break
                plenum_info["inlet_nodes"].append(inlet_node)
            
            return plenum_info
        
        return None


    def visualize_loop_diagram(self, epjson_path: str, loop_name: str = None, 
                            output_path: Optional[str] = None, format: str = "png", 
                            show_legend: bool = True) -> str:
        """
        Generate and save a visual diagram of HVAC loop(s) using custom topology-based approach
        
        Args:
            epjson_path: Path to the epJSON file
            loop_name: Optional specific loop name (if None, creates diagram for first found loop)
            output_path: Optional custom output path (if None, creates one automatically)
            format: Image format for the diagram (png, jpg, pdf, svg)
            show_legend: Whether to include legend in topology-based diagrams (default: True)
        
        Returns:
            JSON string with diagram generation results and file path
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Creating custom loop diagram for: {resolved_path}")
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                diagram_name = f"{path_obj.stem}_hvac_diagram" if not loop_name else f"{path_obj.stem}_{loop_name}_diagram"
                output_path = str(path_obj.parent / f"{diagram_name}.{format}")
            
            # Method 1: Use topology data for custom diagram (PRIMARY)
            try:
                result = self._create_topology_based_diagram(resolved_path, loop_name, output_path, show_legend)
                if result["success"]:
                    logger.info(f"Custom topology diagram created: {output_path}")
                    return json.dumps(result, indent=2)
            except Exception as e:
                logger.warning(f"Topology-based diagram failed: {e}. Using simplified approach.")
            
            # Method 2: Simplified diagram (LAST RESORT)
            result = self._create_simplified_diagram(resolved_path, loop_name, output_path, format)
            logger.info(f"Simplified diagram created: {output_path}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error creating loop diagram for {resolved_path}: {e}")
            raise RuntimeError(f"Error creating loop diagram: {str(e)}")


    def _create_topology_based_diagram(self, epjson_path: str, loop_name: Optional[str], 
                                     output_path: str, show_legend: bool = True) -> Dict[str, Any]:
        """
        Create diagram using topology data from get_loop_topology
        """
        if not GRAPHVIZ_AVAILABLE:
            raise ImportError(
                "Graphviz is required for topology-based diagrams. "
                "Please install it with: pip install graphviz"
            )
        
        # Get available loops
        loops_info = json.loads(self.discover_hvac_loops(epjson_path))
        
        # Determine which loop to diagram
        target_loop = None
        if loop_name:
            # Find specific loop
            for loop_type in ['plant_loops', 'condenser_loops', 'air_loops']:
                for loop in loops_info.get(loop_type, []):
                    if loop.get('name') == loop_name:
                        target_loop = loop_name
                        break
                if target_loop:
                    break
        else:
            # Use first available loop
            for loop_type in ['plant_loops', 'condenser_loops', 'air_loops']:
                loops = loops_info.get(loop_type, [])
                if loops:
                    target_loop = loops[0].get('name')
                    break
        
        if not target_loop:
            raise ValueError("No HVAC loops found or specified loop not found")
        
        # Get detailed topology for the target loop
        topology_json = self.get_loop_topology(epjson_path, target_loop)
        
        # Create custom diagram using the topology data
        result = self.diagram_generator.create_diagram_from_topology(
            topology_json, output_path, f"Custom HVAC Diagram - {target_loop}", show_legend=show_legend
        )
        
        # Add additional metadata
        result.update({
            "input_file": epjson_path,
            "method": "topology_based",
            "total_loops_available": sum(len(loops_info.get(key, [])) 
                                       for key in ['plant_loops', 'condenser_loops', 'air_loops'])
        })
        
        return result
    

    def _create_simplified_diagram(self, epjson_path: str, loop_name: str, 
                                output_path: str, format: str) -> Dict[str, Any]:
        """Create a simplified diagram for HVAC loops from epJSON data"""
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError(
                "Matplotlib is required for diagram generation. "
                "Please install it with: pip install matplotlib"
            )
        
        ep = self.load_json(epjson_path)
        
        # Get basic loop information
        loops_info = []
        
        # Plant loops
        plant_loops = ep.get("PlantLoop", {})
        for plant_loop_name, plant_loop_data in plant_loops.items():
            if not loop_name or plant_loop_name == loop_name:
                loops_info.append({
                    "name": plant_loop_name,
                    "type": "PlantLoop"
                })
        
        # Condenser loops
        condenser_loops = ep.get("CondenserLoop", {})
        for condenser_loop_name, condenser_loop_data in condenser_loops.items():
            if not loop_name or condenser_loop_name == loop_name:
                loops_info.append({
                    "name": condenser_loop_name,
                    "type": "CondenserLoop"
                })
        
        # Air loops
        air_loops = ep.get("AirLoopHVAC", {})
        for air_loop_name, air_loop_data in air_loops.items():
            if not loop_name or air_loop_name == loop_name:
                loops_info.append({
                    "name": air_loop_name,
                    "type": "AirLoopHVAC"
                })
        
        # Create a simple matplotlib diagram
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if loops_info:
            # Simple box diagram
            for i, loop_info in enumerate(loops_info):
                y_pos = len(loops_info) - i - 1
                
                # Choose color based on loop type
                if loop_info["type"] == "PlantLoop":
                    supply_color = 'lightblue'
                    demand_color = 'lightcoral'
                elif loop_info["type"] == "CondenserLoop":
                    supply_color = 'lightgreen'
                    demand_color = 'lightyellow'
                else:  # AirLoopHVAC
                    supply_color = 'lightgray'
                    demand_color = 'lavender'
                
                # Draw supply side
                supply_box = FancyBboxPatch((0, y_pos), 3, 0.8, 
                                        boxstyle="round,pad=0.1", 
                                        facecolor=supply_color, 
                                        edgecolor='black')
                ax.add_patch(supply_box)
                ax.text(1.5, y_pos + 0.4, f"{loop_info['name']}\nSupply Side", 
                    ha='center', va='center', fontsize=10)
                
                # Draw demand side
                demand_box = FancyBboxPatch((4, y_pos), 3, 0.8, 
                                        boxstyle="round,pad=0.1", 
                                        facecolor=demand_color, 
                                        edgecolor='black')
                ax.add_patch(demand_box)
                ax.text(5.5, y_pos + 0.4, f"{loop_info['name']}\nDemand Side", 
                    ha='center', va='center', fontsize=10)
                
                # Draw connections
                ax.arrow(3, y_pos + 0.6, 1, 0, head_width=0.1, 
                        head_length=0.1, fc='black', ec='black')
                ax.arrow(4, y_pos + 0.2, -1, 0, head_width=0.1, 
                        head_length=0.1, fc='black', ec='black')
        
        ax.set_xlim(-0.5, 7.5)
        ax.set_ylim(-0.5, len(loops_info))
        ax.set_title(f"HVAC Loops: {loop_name or 'All Loops'}")
        ax.axis('off')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return {
            "success": True,
            "input_file": epjson_path,
            "output_file": output_path,
            "loop_name": loop_name or "all_loops",
            "format": format,
            "loops_found": len(loops_info),
            "diagram_type": "simplified"
        }        
    
    # ------------------------ Model Modification Methods ------------------------
    def modify_simulation_settings(self, epjson_path: str, object_type: str, field_updates: Dict[str, Any], 
                                 run_period_index: int = 0, output_path: Optional[str] = None) -> str:
        """
        Modify SimulationControl or RunPeriod settings and save to a new file
        
        Args:
            epjson_path: Path to the input epJSON file
            object_type: "SimulationControl" or "RunPeriod"
            field_updates: Dictionary of field names and new values
            run_period_index: Index of RunPeriod to modify (default 0, ignored for SimulationControl)
            output_path: Path for output file (if None, creates one with _modified suffix)
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Modifying {object_type} settings for: {resolved_path}")
            ep = self.load_json(resolved_path)
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
            
            modifications_made = []
            
            if object_type == "SimulationControl":
                sim_objs = ep.get("SimulationControl", {})
                if not sim_objs:
                    raise ValueError("No SimulationControl object found in the epJSON file")
                
                sim_name = list(sim_objs.keys())[0]
                sim_obj = sim_objs[sim_name]
                
                # Valid SimulationControl fields (epJSON format - lowercase with underscores)
                valid_fields = {
                    "do_zone_sizing_calculation", "do_system_sizing_calculation", 
                    "do_plant_sizing_calculation", "run_simulation_for_sizing_periods",
                    "run_simulation_for_weather_file_run_periods", 
                    "do_hvac_sizing_simulation_for_sizing_periods",
                    "maximum_number_of_hvac_sizing_simulation_passes"
                }
                
                for field_name, new_value in field_updates.items():
                    field_key = field_name.lower().replace(" ", "_")
                    if field_key not in valid_fields:
                        logger.warning(f"Invalid field name for SimulationControl: {field_name}")
                        continue
                    
                    try:
                        old_value = sim_obj.get(field_key, "Not set")
                        sim_obj[field_key] = new_value
                        modifications_made.append({
                            "field": field_key,
                            "old_value": old_value,
                            "new_value": new_value
                        })
                        logger.debug(f"Updated {field_key}: {old_value} -> {new_value}")
                    except Exception as e:
                        logger.error(f"Error setting {field_key} to {new_value}: {e}")
            
            elif object_type == "RunPeriod":
                run_objs = ep.get("RunPeriod", {})
                if not run_objs:
                    raise ValueError("No RunPeriod objects found in the epJSON file")
                
                if run_period_index >= len(run_objs):
                    raise ValueError(f"RunPeriod index {run_period_index} out of range (0-{len(run_objs)-1})")
                
                # Get the RunPeriod object by index (convert dict to list)
                run_period_names = list(run_objs.keys())
                run_period_name = run_period_names[run_period_index]
                run_obj = run_objs[run_period_name]
                
                # Valid RunPeriod fields (epJSON format - lowercase with underscores)
                valid_fields = {
                    "name", "begin_month", "begin_day_of_month", "begin_year",
                    "end_month", "end_day_of_month", "end_year", "day_of_week_for_start_day",
                    "use_weather_file_holidays_and_special_days", "use_weather_file_daylight_saving_period",
                    "apply_weekend_holiday_rule", "use_weather_file_rain_indicators", 
                    "use_weather_file_snow_indicators", "treat_weather_as_actual"
                }
                
                for field_name, new_value in field_updates.items():
                    field_key = field_name.lower().replace(" ", "_")
                    if field_key not in valid_fields:
                        logger.warning(f"Invalid field name for RunPeriod: {field_name}")
                        continue
                    
                    try:
                        old_value = run_obj.get(field_key, "Not set")
                        run_obj[field_key] = new_value
                        modifications_made.append({
                            "field": field_key,
                            "old_value": old_value,
                            "new_value": new_value
                        })
                        logger.debug(f"Updated {field_key}: {old_value} -> {new_value}")
                    except Exception as e:
                        logger.error(f"Error setting {field_key} to {new_value}: {e}")
            
            else:
                raise ValueError(f"Invalid object_type: {object_type}. Must be 'SimulationControl' or 'RunPeriod'")
            
            # Save the modified epJSON
            self.save_json(ep, output_path)
            
            result = {
                "success": True,
                "input_file": resolved_path,
                "output_file": output_path,
                "object_type": object_type,
                "run_period_index": run_period_index if object_type == "RunPeriod" else None,
                "modifications_made": modifications_made,
                "total_modifications": len(modifications_made)
            }
            
            logger.info(f"Successfully modified {object_type} and saved to: {output_path}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error modifying simulation settings for {resolved_path}: {e}")
            raise RuntimeError(f"Error modifying simulation settings: {str(e)}")

    def add_coating_outside(self, epjson_path: str, location: str, solar_abs: float = 0.4, 
                            thermal_abs: float = 0.9, output_path: Optional[str] = None) -> str:
        """
        Add exterior coating to all exterior surfaces of the specified location (wall or roof)
        
        Args:
            epjson_path: Path to the input epJSON file
            location: Surface location - either "wall" or "roof"
            solar_abs: Solar Absorptance of the exterior coating (default: 0.4)
            thermal_abs: Thermal Absorptance of the exterior coating (default: 0.9)
            output_path: Path for output file (if None, creates one with _modified suffix)
        
        Returns:
            JSON string with modification results
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        modifications_made = []

        try:
            ep = self.load_json(resolved_path)
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
            
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

            # Save the modified epJSON
            self.save_json(ep, output_path)
            
            result = {
                "success": True,
                "input_file": resolved_path,
                "output_file": output_path,
                "location": location,
                "solar_absorptance": solar_abs,
                "thermal_absorptance": thermal_abs,
                "surfaces_found": len(all_surfs),
                "modifications_made": modifications_made,
                "total_modifications": len(modifications_made)
            }
            
            logger.info(f"Successfully modified exterior coating for {len(ext_layer_names)} materials and saved to: {output_path}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error modifying exterior coating for {resolved_path}: {e}")
            raise RuntimeError(f"Error modifying exterior coating: {str(e)}")


    def add_window_film_outside(self, epjson_path: str, u_value: float = 4.94, shgc: float = 0.45, 
                                visible_transmittance: float = 0.66, output_path: Optional[str] = None) -> str:
        """
        Add window film to exterior windows using WindowMaterial:SimpleGlazingSystem
        
        Args:
            epjson_path: Path to the input epJSON file
            u_value: U-factor of the window film (default: 4.94 W/m²-K from CBES)
            shgc: Solar Heat Gain Coefficient (default: 0.45 from CBES)
            visible_transmittance: Visible transmittance (default: 0.66 from CBES)
            output_path: Path for output file (if None, creates one with _modified suffix)
        
        Returns:
            JSON string with modification results
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        modifications_made = []

        try:
            ep = self.load_json(resolved_path)
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
            
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
                return json.dumps({
                    "success": False,
                    "message": "No exterior windows found in the model",
                    "windows_found": 0
                }, indent=2)
            
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
            
            # Save the modified epJSON
            self.save_json(ep, output_path)
            
            result = {
                "success": True,
                "input_file": resolved_path,
                "output_file": output_path,
                "window_film_material": window_film_name,
                "window_film_construction": window_film_construction_name,
                "u_factor": u_value,
                "solar_heat_gain_coefficient": shgc,
                "visible_transmittance": visible_transmittance,
                "windows_modified": len(ext_window_surfs),
                "modifications_made": modifications_made,
                "total_modifications": len(modifications_made)
            }
            
            logger.info(f"Successfully added window film to {len(ext_window_surfs)} windows and saved to: {output_path}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error modifying window film properties for {resolved_path}: {e}")
            raise RuntimeError(f"Error modifying window film properties: {str(e)}")


    def change_infiltration_by_mult(self, epjson_path: str, mult: float = 0.9,
                                 output_path: Optional[str] = None) -> str:
        """
        Modify infiltration rates in the epJSON file by a multiplier

        Args:
            epjson_path: Path to the input epJSON file
            mult: Multiplier for infiltration rates (default: 0.9)
            output_path: Path for output file (if None, creates one with _modified suffix)
        
        Returns:
            JSON string with modification results
        """
        resolved_path = self._resolve_epjson_path(epjson_path)
        
        modifications_made = []

        try:
            ep = self.load_json(resolved_path)
            
            # Determine output path
            if output_path is None:
                path_obj = Path(resolved_path)
                output_path = str(path_obj.parent / f"{path_obj.stem}_modified{path_obj.suffix}")
            
            object_type = "ZoneInfiltration:DesignFlowRate"
            infiltration_objs = ep.get(object_type, {})
            
            if not infiltration_objs:
                logger.warning(f"No {object_type} objects found in the epJSON file")
                return json.dumps({
                    "success": False,
                    "message": f"No {object_type} objects found",
                    "input_file": resolved_path,
                    "infiltration_objects_found": 0
                }, indent=2)

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

            # Save the modified epJSON
            self.save_json(ep, output_path)
            
            result = {
                "success": True,
                "input_file": resolved_path,
                "output_file": output_path,
                "multiplier": mult,
                "infiltration_objects_found": len(infiltration_objs),
                "modifications_made": modifications_made,
                "total_modifications": len(modifications_made)
            }
            
            logger.info(f"Successfully modified {len(modifications_made)} infiltration objects and saved to: {output_path}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error modifying infiltration rate for {resolved_path}: {e}")
            raise RuntimeError(f"Error modifying infiltration rate: {str(e)}")
    
    
    # ------------------------ Simulation Execution ------------------------
    def run_simulation(self, epjson_path: str, weather_file: str = None, 
                        output_directory: str = None, annual: bool = True,
                        design_day: bool = False, readvars: bool = True,
                        expandobjects: bool = True, ep_version: str = "25-1-0") -> str:
        """
        Run EnergyPlus simulation with specified epjson and weather file
        
        Args:
            epjson_path: Path to the epjson file
            weather_file: Path to weather file (.epw). If None, searches for weather files in sample_files
            output_directory: Directory for simulation outputs. If None, creates one in outputs/
            annual: Run annual simulation (default: True)
            design_day: Run design day only simulation (default: False)
            readvars: Run ReadVarsESO after simulation (default: True)
            expandobjects: Run ExpandObjects prior to simulation (default: True)
            ep_version: EnergyPlus version (default: "25-1-0")
        
        Returns:
            JSON string with simulation results and output file paths
        """
        resolved_epjson_path = self._resolve_epjson_path(epjson_path)
        
        try:
            logger.info(f"Starting simulation for: {resolved_epjson_path}")
            
            # Resolve weather file path
            resolved_weather_path = None
            if weather_file:
                resolved_weather_path = self._resolve_weather_file_path(weather_file)
                logger.info(f"Using weather file: {resolved_weather_path}")
            
            # Set up output directory
            if output_directory is None:
                epjson_name = Path(resolved_epjson_path).stem
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_directory = str(Path(self.config.paths.output_dir) / f"{epjson_name}_simulation_{timestamp}")
            
            # Create output directory if it doesn't exist
            os.makedirs(output_directory, exist_ok=True)
            logger.info(f"Output directory: {output_directory}")
            
            # Load epjson file
            ep = self.load_json(epjson_path)
            version = ep["Version"]["Version 1"]["version_identifier"]
            # Split, pad to 3 parts, and join with dashes
            ep_version = "-".join((version.split(".") + ["0", "0"])[:3])
            
            # Configure simulation options
            simulation_options = {
                'idf': epjson_path,
                'output_directory': output_directory,
                'annual': annual,
                'design_day': design_day,
                'readvars': readvars,
                'expandobjects': expandobjects,
                'output_prefix': Path(resolved_epjson_path).stem,
                'output_suffix': 'C',  # Capital suffix style
                'verbose': 'v',  # Verbose output,
                'ep_version': ep_version
            }
            
            # Add weather file to options if provided
            if resolved_weather_path:
                simulation_options['weather'] = resolved_weather_path
            
            logger.info("Starting EnergyPlus simulation...")
            start_time = datetime.now()
            
            # Run the simulation
            try:
                result = run(**simulation_options)
                end_time = datetime.now()
                duration = end_time - start_time
                
                # Check for common output files
                output_files = self._find_simulation_outputs(output_directory)
                
                simulation_result = {
                    "success": True,
                    "input_idf": resolved_epjson_path,
                    "weather_file": resolved_weather_path,
                    "output_directory": output_directory,
                    "simulation_duration": str(duration),
                    "simulation_options": simulation_options,
                    "output_files": output_files,
                    "energyplus_result": str(result) if result else "Simulation completed",
                    "timestamp": end_time.isoformat()
                }
                
                logger.info(f"Simulation completed successfully in {duration}")
                return json.dumps(simulation_result, indent=2)
                
            except Exception as e:
                # Try to find error file for more detailed error information
                error_file = Path(output_directory) / f"{Path(resolved_epjson_path).stem}.err"
                error_details = ""
                
                if error_file.exists():
                    try:
                        with open(error_file, 'r') as f:
                            error_details = f.read()
                    except Exception:
                        error_details = "Could not read error file"
                
                simulation_result = {
                    "success": False,
                    "input_idf": resolved_epjson_path,
                    "weather_file": resolved_weather_path,
                    "output_directory": output_directory,
                    "error": str(e),
                    "error_details": error_details,
                    "simulation_options": simulation_options,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.error(f"Simulation failed: {str(e)}")
                return json.dumps(simulation_result, indent=2)
                
        except Exception as e:
            logger.error(f"Error setting up simulation for {resolved_epjson_path}: {e}")
            raise RuntimeError(f"Error running simulation: {str(e)}")

        

    def _resolve_weather_file_path(self, weather_file: str) -> str:
        """Resolve weather file path (handle relative paths, sample files, EnergyPlus weather data, etc.)"""
        from .utils.path_utils import resolve_path
        return resolve_path(self.config, weather_file, file_types=['.epw'], description="weather file", 
                           enable_fuzzy_weather_matching=True)
    

    def _find_simulation_outputs(self, output_directory: str) -> Dict[str, Any]:
        """Find and categorize simulation output files"""
        output_dir = Path(output_directory)
        if not output_dir.exists():
            return {}
        
        output_files = {
            "summary_reports": [],
            "time_series_outputs": [],
            "error_files": [],
            "other_files": []
        }
        
        # Common EnergyPlus output file patterns
        file_patterns = {
            "summary_reports": ["*Table.html", "*Table.htm", "*Table.csv", "*Summary.csv"],
            "time_series_outputs": ["*.csv", "*.eso", "*.mtr"],
            "error_files": ["*.err", "*.audit", "*.bnd"]
        }
        
        for file_path in output_dir.iterdir():
            if file_path.is_file():
                file_info = {
                    "name": file_path.name,
                    "path": str(file_path),
                    "size_bytes": file_path.stat().st_size,
                    "modified": file_path.stat().st_mtime
                }
                
                categorized = False
                for category, patterns in file_patterns.items():
                    for pattern in patterns:
                        if file_path.match(pattern):
                            output_files[category].append(file_info)
                            categorized = True
                            break
                    if categorized:
                        break
                
                if not categorized:
                    output_files["other_files"].append(file_info)
        
        return output_files

    # ------------------------ Post-Processing and Visualization ------------------------
    def create_interactive_plot(self, output_directory: str, idf_name: str = None, 
                                file_type: str = "auto", custom_title: str = None) -> str:
        """
        Create interactive HTML plot from EnergyPlus output files (meter or variable outputs)
        
        Args:
            output_directory: Directory containing the output files
            idf_name: Name of the IDF file (without extension). If None, tries to detect from directory
            file_type: "meter", "variable", or "auto" to detect automatically
            custom_title: Custom title for the plot
        
        Returns:
            JSON string with plot creation results
        """
        if not PANDAS_AVAILABLE:
            raise ImportError(
                "Pandas is required for data processing. "
                "Please install it with: pip install pandas"
            )
        
        if not PLOTLY_AVAILABLE:
            raise ImportError(
                "Plotly is required for interactive plots. "
                "Please install it with: pip install plotly"
            )
        
        try:
            logger.info(f"Creating interactive plot from: {output_directory}")
            
            output_dir = Path(output_directory)
            if not output_dir.exists():
                raise FileNotFoundError(f"Output directory not found: {output_directory}")
            
            # Auto-detect IDF name if not provided
            if not idf_name:
                csv_files = list(output_dir.glob("*.csv"))
                if csv_files:
                    # Try to find the pattern
                    for csv_file in csv_files:
                        if csv_file.name.endswith("Meter.csv"):
                            idf_name = csv_file.name[:-9]  # Remove "Meter.csv"
                            break
                        elif not csv_file.name.endswith("Meter.csv"):
                            idf_name = csv_file.stem  # Remove .csv
                            break
                
                if not idf_name:
                    raise ValueError("Could not auto-detect IDF name. Please specify idf_name parameter.")
            
            # Determine which file to process
            meter_file = output_dir / f"{idf_name}Meter.csv"
            variable_file = output_dir / f"{idf_name}.csv"
            
            csv_file = None
            data_type = None
            
            if file_type == "auto":
                if meter_file.exists():
                    csv_file = meter_file
                    data_type = "Meter"
                elif variable_file.exists():
                    csv_file = variable_file  
                    data_type = "Variable"
            elif file_type == "meter":
                csv_file = meter_file
                data_type = "Meter"
            elif file_type == "variable":
                csv_file = variable_file
                data_type = "Variable"
            
            if not csv_file or not csv_file.exists():
                raise FileNotFoundError(f"Output CSV file not found. Checked: {meter_file}, {variable_file}")
            
            logger.info(f"Processing {data_type} file: {csv_file}")
            
            # Read CSV file
            df = pd.read_csv(csv_file)
            
            if df.empty:
                raise ValueError(f"CSV file is empty: {csv_file}")
            
            # Try to parse Date/Time column
            datetime_col = None
            datetime_parsed = False
            
            # Look for Date/Time column (case insensitive)
            for col in df.columns:
                if 'date' in col.lower() and 'time' in col.lower():
                    datetime_col = col
                    break
            
            if datetime_col:
                try:
                    # Try MM/DD HH:MM:SS format first
                    def parse_datetime_mmdd(dt_str):
                        try:
                            # Add current year and parse
                            current_year = datetime.now().year
                            full_dt_str = f"{current_year}/{dt_str}"
                            return pd.to_datetime(full_dt_str, format="%Y/%m/%d  %H:%M:%S")
                        except:
                            return None
                    
                    # Try monthly format
                    def parse_monthly(dt_str):
                        try:
                            dt_str = dt_str.strip()
                            if dt_str in calendar.month_name[1:]:  # Full month names
                                month_num = list(calendar.month_name).index(dt_str)
                                return pd.to_datetime(f"2023-{month_num:02d}-01")  # Use 2023 as default year
                            return None
                        except:
                            return None
                    
                    # Try to parse datetime
                    sample_value = str(df[datetime_col].iloc[0]).strip()
                    
                    if '/' in sample_value and ':' in sample_value:
                        # MM/DD HH:MM:SS format
                        df['parsed_datetime'] = df[datetime_col].apply(parse_datetime_mmdd)
                    elif sample_value in calendar.month_name[1:]:
                        # Monthly format
                        df['parsed_datetime'] = df[datetime_col].apply(parse_monthly)
                    else:
                        df['parsed_datetime'] = pd.to_datetime(df[datetime_col], errors='coerce')
                    
                    # Check if parsing was successful
                    if df['parsed_datetime'].notna().any():
                        datetime_parsed = True
                        x_values = df['parsed_datetime']
                        x_title = "Date/Time"
                        logger.info("Successfully parsed datetime column")
                    else:
                        logger.warning("DateTime parsing failed, using index")
                        
                except Exception as e:
                    logger.warning(f"DateTime parsing error: {e}, falling back to index")
            
            # Fallback to simple version if datetime parsing failed
            if not datetime_parsed:
                x_values = df.index
                x_title = "Index"
            
            # Create plotly figure
            fig = go.Figure()
            
            # Add traces for all numeric columns (except datetime)
            numeric_cols = df.select_dtypes(include=['number']).columns
            colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
            
            for i, col in enumerate(numeric_cols):
                if col != datetime_col:  # Skip original datetime column
                    color = colors[i % len(colors)]
                    fig.add_trace(go.Scatter(
                        x=x_values,
                        y=df[col],
                        mode='lines',
                        name=col,
                        line=dict(color=color),
                        hovertemplate=f'<b>{col}</b><br>Value: %{{y}}<br>Time: %{{x}}<extra></extra>'
                    ))
            
            # Update layout
            title = custom_title or f"EnergyPlus {data_type} Output - {idf_name}"
            fig.update_layout(
                title=dict(text=title, x=0.5),
                xaxis_title=x_title,
                yaxis_title="Value",
                hovermode='x unified',
                template='plotly_white',
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                )
            )
            
            # Save as HTML
            html_filename = f"{idf_name}_{data_type.lower()}_plot.html"
            html_path = output_dir / html_filename
            
            fig.write_html(str(html_path))
            
            result = {
                "success": True,
                "input_file": str(csv_file),
                "output_file": str(html_path),
                "data_type": data_type,
                "idf_name": idf_name,
                "datetime_parsed": datetime_parsed,
                "columns_plotted": list(numeric_cols),
                "total_data_points": len(df),
                "title": title
            }
            
            logger.info(f"Interactive plot created: {html_path}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error creating interactive plot: {e}")
            raise RuntimeError(f"Error creating interactive plot: {str(e)}")

    def _get_branches_from_list(self, ep, branch_list_name: str) -> List[Dict[str, Any]]:
        """Helper method to get branch information from a branch list"""
        branches = []
        branch_lists = ep.get("BranchList", {})
        for branch_list in branch_lists:
            if branch_list == branch_list_name:
                # Get all branch names from the list
                for branch in branch_lists[branch_list]["branches"]:
                    branch_name = branch["branch_name"]                   
                    # Get detailed branch information
                    branch_info = self._get_branch_details(ep, branch_name)
                    if branch_info:
                        branches.append(branch_info)
                break
        
        return branches


    def _get_branch_details(self, ep, branch_name: str) -> Optional[Dict[str, Any]]:
        """Helper method to get detailed information about a specific branch"""
        branch_objs = ep.get("Branch", {})
        if branch_name in branch_objs:
            branch_info = {
                "name": branch_name,
                "components": []
            }
            comps = branch_objs[branch_name]["components"]
            for comp in comps:
                component_info = {
                    "type": comp["component_object_type"],
                    "name": comp["component_name"],
                    "inlet_node": comp["component_inlet_node_name"],
                    "outlet_node": comp["component_outlet_node_name"]
                }
                branch_info["components"].append(component_info)
            return branch_info       
        return None


    def _get_connectors_from_list(self, ep, connector_list_name: str) -> List[Dict[str, Any]]:
        """Helper method to get connector information (splitters/mixers) from a connector list"""
        connectors = []
        connector_lists = ep.get("ConnectorList", {})
        if connector_list_name in connector_lists:
            connector_data = connector_lists[connector_list_name]
            len_connector_keys = len(list(connector_data.keys()))
            if not len_connector_keys % 2 == 0:
                # This should never happen; there should be a name and object_type for each component. If not, the epJSON is invalid. 
                print(f"ConnectorList {connector_list_name} has uneven number of keys. This is invalid.")
                return None
            num_connector_items = int(len_connector_keys / 2)
            for i in range(num_connector_items):
                connector_name = connector_data[f"connector_{i + 1}_name"]
                connector_type = connector_data[f"connector_{i + 1}_object_type"]
                if connector_type.lower().endswith('splitter'):
                    # For splitters: one inlet branch, multiple outlet branches
                    splitter_data = ep.get("Connector:Splitter", {}).get(connector_name, {})               
                    outlet_branches = [
                        branch.get("outlet_branch_name", "Unknown") 
                        for branch in splitter_data.get("branches", [])
                        if isinstance(branch, dict) and "outlet_branch_name" in branch
                    ]
                    connector_info = {
                        "name": connector_name,
                        "type": connector_type,
                        "inlet_branch": splitter_data.get("inlet_branch_name", "Unknown"),
                        "outlet_branches": outlet_branches
                    }
                elif connector_type.lower().endswith('mixer'):
                    # For mixers: multiple inlet branches, one outlet branch
                    mixer_data = ep.get("Connector:Mixer", {}).get(connector_name, {}) 
                    inlet_branches = [
                        branch.get("inlet_branch_name", "Unknown") 
                        for branch in mixer_data.get("branches", [])
                        if isinstance(branch, dict) and "inlet_branch_name" in branch
                    ]
                    connector_info = {
                        "name": connector_name,
                        "type": connector_type,
                        "inlet_branches": inlet_branches,
                        "outlet_branch": mixer_data.get("outlet_branch_name", "Unknown")
                    }
                connectors.append(connector_info)    
            return connectors
        return None

