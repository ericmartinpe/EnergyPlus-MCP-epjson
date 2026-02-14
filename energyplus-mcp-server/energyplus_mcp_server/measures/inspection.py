"""
Inspection Measures for EnergyPlus MCP Server.

This module contains all model inspection related methods including:
- Model basics (Building, Site:Location, Version info)
- Simulation settings
- Zone inspection
- Surface inspection
- Material inspection
"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class InspectionMeasures:
    """Mixin class containing inspection methods for EnergyPlusManager"""
    
    def get_model_basics(self, epjson_data: Dict[str, Any]) -> str:
        """Get basic model information from Building, Site:Location, and SimulationControl"""
        try:
            logger.debug("Getting model basics")
            ep = epjson_data
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
            logger.error(f"Error getting model basics: {e}")
            raise RuntimeError(f"Error getting model basics: {str(e)}")
    
    def check_simulation_settings(self, epjson_data: Dict[str, Any]) -> str:
        """Check SimulationControl and RunPeriod settings with modifiable fields info"""
        try:
            logger.debug("Checking simulation settings")
            ep = epjson_data
            
            settings_info = {
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
            logger.error(f"Error checking simulation settings: {e}")
            raise RuntimeError(f"Error checking simulation settings: {str(e)}")
    
    def list_zones(self, epjson_data: Dict[str, Any]) -> str:
        """List all zones in the model"""
        try:
            logger.debug("Listing zones")
            ep = epjson_data
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
            logger.error(f"Error listing zones: {e}")
            raise RuntimeError(f"Error listing zones: {str(e)}")
    
    def get_surfaces(self, epjson_data: Dict[str, Any]) -> str:
        """Get detailed surface information"""
        try:
            logger.debug("Getting surfaces")
            ep = epjson_data
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
            logger.error(f"Error getting surfaces: {e}")
            raise RuntimeError(f"Error getting surfaces: {str(e)}")
    
    def get_materials(self, epjson_data: Dict[str, Any]) -> str:
        """Get material information"""
        try:
            logger.debug("Getting materials")
            ep = epjson_data
            
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
            logger.error(f"Error getting materials: {e}")
            raise RuntimeError(f"Error getting materials: {str(e)}")
