"""
People object utility module for EnergyPlus MCP Server.
Handles inspection and modification of People objects in EnergyPlus models.
"""

import logging
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger(__name__)


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file and return its content"""
    with open(file_path, "r") as f:
        return json.load(f)


class PeopleManager:
    """Manager for EnergyPlus People objects"""

    # Valid calculation methods for Number of People
    VALID_CALCULATION_METHODS = {
        "People": "Direct number of people",
        "People/Area": "People per floor area (people/m2)",
        "Area/Person": "Floor area per person (m2/person)",
    }

    # Common activity levels (W/person) - from ASHRAE
    COMMON_ACTIVITY_LEVELS = {
        "Seated, quiet": 108,
        "Seated, light work": 126,
        "Standing, relaxed": 126,
        "Standing, light work": 207,
        "Walking": 207,
        "Light bench work": 234,
    }

    def __init__(self):
        """Initialize the People manager"""
        pass

    def get_people_objects(self, ep_path: str) -> Dict[str, Any]:
        """
        Get all People objects from the IDF file with detailed information

        Args:
            ep_path: Path to the epJSON file

        Returns:
            Dictionary with people objects information
        """
        try:
            ep = load_json(ep_path)
            people_objects = ep.get("People", {})

            result = {
                "success": True,
                "file_path": ep_path,
                "total_people_objects": len(people_objects),
                "people_objects": [],
                "summary": {
                    "by_calculation_method": {},
                    "by_zone": {},
                    "total_design_occupancy": 0.0,
                },
            }

            # Get all zones as a dictionary for lookup
            zones_dict = ep.get("Zone", {})

            for people_name, people_data in people_objects.items():
                people_info = {
                    "name": people_name,
                    "zone_or_zonelist": people_data.get(
                        "zone_or_zonelist_or_space_or_spacelist_name", "Unknown"
                    ),
                    "schedule": people_data.get(
                        "number_of_people_schedule_name", "Unknown"
                    ),
                    "calculation_method": people_data.get(
                        "number_of_people_calculation_method", "Unknown"
                    ),
                    "number_of_people": people_data.get("number_of_people", ""),
                    "people_per_area": people_data.get("people_per_floor_area", ""),
                    "area_per_person": people_data.get("floor_area_per_person", ""),
                    "fraction_radiant": people_data.get("fraction_radiant", ""),
                    "sensible_heat_fraction": people_data.get(
                        "sensible_heat_fraction", ""
                    ),
                    "activity_schedule": people_data.get(
                        "activity_level_schedule_name", ""
                    ),
                    "co2_generation_rate": people_data.get(
                        "carbon_dioxide_generation_rate", ""
                    ),
                    "clothing_insulation_schedule": people_data.get(
                        "clothing_insulation_schedule_name", ""
                    ),
                    "air_velocity_schedule": people_data.get(
                        "air_velocity_schedule_name", ""
                    ),
                    "work_efficiency_schedule": people_data.get(
                        "work_efficiency_schedule_name", ""
                    ),
                    "thermal_comfort_model_1": people_data.get(
                        "thermal_comfort_model_1_type", ""
                    ),
                    "thermal_comfort_model_2": people_data.get(
                        "thermal_comfort_model_2_type", ""
                    ),
                }

                # Calculate design occupancy if possible
                zone_name = people_info["zone_or_zonelist"]
                zone_data = (
                    zones_dict.get(zone_name) if zone_name != "Unknown" else None
                )
                design_occupancy = self._calculate_design_occupancy(
                    people_info, zone_data
                )
                people_info["design_occupancy"] = design_occupancy

                result["people_objects"].append(people_info)

                # Update summaries
                calc_method = people_info["calculation_method"]
                if calc_method:
                    result["summary"]["by_calculation_method"][calc_method] = (
                        result["summary"]["by_calculation_method"].get(calc_method, 0)
                        + 1
                    )

                zone_name = people_info["zone_or_zonelist"]
                if zone_name:
                    if zone_name not in result["summary"]["by_zone"]:
                        result["summary"]["by_zone"][zone_name] = []
                    result["summary"]["by_zone"][zone_name].append(people_info["name"])

                if design_occupancy is not None:
                    result["summary"]["total_design_occupancy"] += design_occupancy

            logger.info(f"Found {len(people_objects)} People objects in {ep_path}")
            return result

        except Exception as e:
            logger.error(f"Error getting People objects: {e}")
            return {"success": False, "error": str(e), "file_path": ep_path}

    def _calculate_design_occupancy(
        self, people_info: Dict[str, Any], zone_data: Optional[Dict[str, Any]]
    ) -> Optional[float]:
        """Calculate design occupancy based on calculation method and zone data"""
        try:
            calc_method = people_info["calculation_method"]

            if calc_method == "People":
                value = people_info["number_of_people"]
                if value and value != "":
                    return float(value)

            elif calc_method == "People/Area" and zone_data:
                people_per_area = people_info["people_per_area"]
                if people_per_area and people_per_area != "":
                    # Get zone floor area from epJSON
                    floor_area = zone_data.get("floor_area")
                    if (
                        floor_area
                        and floor_area != ""
                        and floor_area != "autocalculate"
                    ):
                        return float(people_per_area) * float(floor_area)

            elif calc_method == "Area/Person" and zone_data:
                area_per_person = people_info["area_per_person"]
                if (
                    area_per_person
                    and area_per_person != ""
                    and float(area_per_person) > 0
                ):
                    # Get zone floor area from epJSON
                    floor_area = zone_data.get("floor_area")
                    if (
                        floor_area
                        and floor_area != ""
                        and floor_area != "autocalculate"
                    ):
                        return float(floor_area) / float(area_per_person)

        except (ValueError, TypeError) as e:
            logger.warning(f"Could not calculate design occupancy: {e}")

        return None

    def modify_people_objects(
        self, ep_path: str, modifications: List[Dict[str, Any]], output_path: str
    ) -> Dict[str, Any]:
        """
        Modify People objects in the epJSON file

        Args:
            ep_path: Path to the input epJSON file
            modifications: List of modification specifications
            output_path: Path for the output epJSON file

        Returns:
            Dictionary with modification results
        """
        try:
            ep = load_json(ep_path)
            people_objects = ep.get("People", {})

            result = {
                "success": True,
                "input_file": ep_path,
                "output_file": output_path,
                "modifications_requested": len(modifications),
                "modifications_applied": [],
                "errors": [],
            }

            for mod_spec in modifications:
                try:
                    # Apply modification based on target
                    target = mod_spec.get("target", "all")
                    field_updates = mod_spec.get("field_updates", {})

                    if target == "all":
                        # Apply to all People objects
                        for people_name, people_data in people_objects.items():
                            self._apply_people_modifications(
                                people_name, people_data, field_updates, result
                            )
                    elif target.startswith("zone:"):
                        # Apply to People objects in specific zone
                        zone_name = target.replace("zone:", "").strip()
                        for people_name, people_data in people_objects.items():
                            if (
                                people_data.get(
                                    "zone_or_zonelist_or_space_or_spacelist_name", ""
                                )
                                == zone_name
                            ):
                                self._apply_people_modifications(
                                    people_name, people_data, field_updates, result
                                )
                    elif target.startswith("name:"):
                        # Apply to specific People object by name
                        target_name = target.replace("name:", "").strip()
                        if target_name in people_objects:
                            self._apply_people_modifications(
                                target_name,
                                people_objects[target_name],
                                field_updates,
                                result,
                            )
                        else:
                            result["errors"].append(
                                f"People object '{target_name}' not found"
                            )
                    else:
                        result["errors"].append(
                            f"Invalid target specification: {target}"
                        )

                except Exception as e:
                    result["errors"].append(f"Error processing modification: {str(e)}")

            # Save the modified epJSON
            with open(output_path, "w") as f:
                json.dump(ep, f, indent=2)

            result["total_modifications_applied"] = len(result["modifications_applied"])

            logger.info(
                f"Applied {len(result['modifications_applied'])} modifications to People objects"
            )
            return result

        except Exception as e:
            logger.error(f"Error modifying People objects: {e}")
            return {"success": False, "error": str(e), "input_file": ep_path}

    def _apply_people_modifications(
        self,
        people_name: str,
        people_data: Dict[str, Any],
        field_updates: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Apply field updates to a People object in epJSON format"""
        # Valid People object fields (epJSON format - lowercase with underscores)
        valid_fields = {
            "number_of_people_schedule_name",
            "number_of_people_calculation_method",
            "number_of_people",
            "people_per_floor_area",
            "floor_area_per_person",
            "fraction_radiant",
            "sensible_heat_fraction",
            "activity_level_schedule_name",
            "carbon_dioxide_generation_rate",
            "enable_ashrae_55_comfort_warnings",
            "mean_radiant_temperature_calculation_type",
            "surface_name_or_angle_factor_list_name",
            "work_efficiency_schedule_name",
            "clothing_insulation_schedule_name",
            "air_velocity_schedule_name",
            "thermal_comfort_model_1_type",
            "thermal_comfort_model_2_type",
        }

        for field_name, new_value in field_updates.items():
            # Normalize field name to lowercase with underscores
            field_key = field_name.lower().replace(" ", "_")

            if field_key not in valid_fields:
                result["errors"].append(
                    f"Invalid field '{field_name}' for People object '{people_name}'"
                )
                continue

            try:
                # Validate calculation method change
                if field_key == "number_of_people_calculation_method":
                    if new_value not in self.VALID_CALCULATION_METHODS:
                        result["errors"].append(
                            f"Invalid calculation method '{new_value}' for '{people_name}'"
                        )
                        continue

                old_value = people_data.get(field_key, "")
                people_data[field_key] = new_value

                result["modifications_applied"].append(
                    {
                        "object_name": people_name,
                        "field": field_key,
                        "old_value": old_value,
                        "new_value": new_value,
                    }
                )

                logger.debug(
                    f"Updated {people_name}.{field_key}: {old_value} -> {new_value}"
                )

            except Exception as e:
                result["errors"].append(
                    f"Error setting {field_name} to {new_value} for '{people_name}': {str(e)}"
                )

    def validate_people_modifications(
        self, modifications: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate modification specifications before applying them

        Args:
            modifications: List of modification specifications

        Returns:
            Validation result dictionary
        """
        validation_result = {"valid": True, "errors": [], "warnings": []}

        for i, mod_spec in enumerate(modifications):
            # Check required fields
            if "target" not in mod_spec:
                validation_result["errors"].append(
                    f"Modification {i}: Missing 'target' field"
                )
                validation_result["valid"] = False

            if "field_updates" not in mod_spec:
                validation_result["errors"].append(
                    f"Modification {i}: Missing 'field_updates' field"
                )
                validation_result["valid"] = False
            elif not isinstance(mod_spec["field_updates"], dict):
                validation_result["errors"].append(
                    f"Modification {i}: 'field_updates' must be a dictionary"
                )
                validation_result["valid"] = False

            # Validate target format
            target = mod_spec.get("target", "")
            if target and not (
                target == "all"
                or target.startswith("zone:")
                or target.startswith("name:")
            ):
                validation_result["errors"].append(
                    f"Modification {i}: Invalid target format '{target}'. "
                    "Use 'all', 'zone:ZoneName', or 'name:PeopleName'"
                )
                validation_result["valid"] = False

        return validation_result
