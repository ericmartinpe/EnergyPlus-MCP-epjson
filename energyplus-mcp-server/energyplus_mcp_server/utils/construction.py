import os
import json
from typing import Dict, Any

def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file and return its content"""
    with open(file_path, "r") as f:
        return json.load(f)

def base_assembly_r(ep, material_list, surface_type="wall"):
    """Calculate base assembly R-value excluding insulation (returns SI units).
    
    Args:
        ep (dict): EnergyPlus input file dictionary object
        material_list (list): List of material names in the construction
        surface_type (str): Type of surface - "wall" or "roof" (default: "wall")
    
    Returns:
        float: Base assembly R-value in SI units (m²·K/W)
    """
    # Constants
    EXT_AIR_FILM = 0.03  # m²·K/W
    INT_AIR_FILMS = {
        "wall": 0.12,
        "roof": 0.107
    }  # m²·K/W
    # Start with air film resistances
    r_value_si = EXT_AIR_FILM + INT_AIR_FILMS[surface_type]
    
    # Add material resistances (excluding insulation)
    for material_name in material_list:
        if "insulation" not in material_name.lower():
            material = ep["Material"].get(material_name, {})
            conductivity = material.get("conductivity", 0)
            thickness = material.get("thickness", 0)
            if conductivity > 0:  # Avoid division by zero
                r_value_si += thickness / conductivity
    
    return r_value_si


def set_construction_ufactor(ep, ufactor, construction_name):
    """
    Update insulation material R-value to achieve target U-Factor.
    If base construction R-value is too high, reduce thickness of base materials

    Args:
        ep (dict): EnergyPlus input file dictionary object
        ufactor (float): Target U-Factor in SI units (W/m²·K)
        construction_name (str): Name of construction to modify
    
    Returns:
        dict: Modified EnergyPlus input file dictionary
    """
    # Constants
    MIN_VALUE = 0.001  # Minimum value to prevent error
    
    # Get material list from construction
    construction = ep.get("Construction", {}).get(construction_name)
    if not construction:
        raise ValueError(f"Construction '{construction_name}' not found in model")
    
    material_list = list(construction.values())

    # Calculate required insulation R-value
    r_target = 1 / ufactor
    r_val_base_si = base_assembly_r(ep, material_list)
    r_ins_si = r_target - r_val_base_si

    if r_ins_si >= MIN_VALUE:
        # Update insulation material thermal resistance
        for material_name in material_list:
            if "insulation" in material_name.lower():
                if "Material:NoMass" in ep and material_name in ep["Material:NoMass"]:
                    ep["Material:NoMass"][material_name]["thermal_resistance"] = r_ins_si
                    break
                elif "Material" in ep and material_name in ep["Material"]:
                    ep["Material"][material_name]["thickness"] = r_ins_si * ep["Material"][material_name]["conductivity"]
                    break
    
    else: # remove insulation layer
        layer_to_remove = None
        insulation_mat = None
        for layer, material in construction.items():
            if "insulation" in material.lower():
                layer_to_remove = layer
                insulation_mat = material
                break
        
        if layer_to_remove:
            # Remove insulation layer and material
            del ep["Construction"][construction_name][layer_to_remove]
            if "Material:NoMass" in ep and insulation_mat in ep["Material:NoMass"]:
                del ep["Material:NoMass"][insulation_mat]

            # Rebuild construction with numbered layers (or else error)
            # Get all remaining layers except outside_layer
            remaining_layers = []
            outside_layer_value = None
            
            for layer, material in list(ep["Construction"][construction_name].items()):
                if layer == "outside_layer":
                    outside_layer_value = material
                else:
                    remaining_layers.append(material)
            
            # Clear and rebuild construction
            ep["Construction"][construction_name] = {}
            ep["Construction"][construction_name]["outside_layer"] = outside_layer_value
            
            # Add remaining layers with proper numbering
            for i, material in enumerate(remaining_layers, start=2):
                ep["Construction"][construction_name][f"layer_{i}"] = material

    # reduce thickenss of base material if r_target < r_val_base_si
    if r_target < r_val_base_si:
        rsi_diff = r_val_base_si - r_target
        for material in material_list:
            if "insulation" not in material.lower():
                new_thickness = ep["Material"][material]["thickness"] - rsi_diff * ep["Material"][material]["conductivity"]
                if new_thickness >= MIN_VALUE: # ensure minimum thickness
                    ep["Material"][material]["thickness"] = new_thickness
                    break
    return ep
