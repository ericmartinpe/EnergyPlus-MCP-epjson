"""
Schedule inspection measures for EnergyPlus models.

This module provides mixin class for inspecting schedule objects in EnergyPlus models,
including schedule type limits, day schedules, week schedules, and annual schedules.
"""

import json
import logging
from typing import Dict, Any

from ..utils.schedules import ScheduleValueParser

logger = logging.getLogger(__name__)


class SchedulesMeasures:
    """Mixin class for schedule inspection measures"""
    
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
