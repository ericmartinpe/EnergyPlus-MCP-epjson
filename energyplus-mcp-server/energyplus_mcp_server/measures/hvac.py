"""
HVAC system measures for EnergyPlus models.

This module provides mixin class for HVAC loop discovery, topology analysis,
and visualization of plant loops, condenser loops, and air loops.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None
    FancyBboxPatch = None

try:
    from ..utils.diagrams import HVACDiagramGenerator
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False
    HVACDiagramGenerator = None

from ..utils.hvac_utils import iter_numbered_components, iter_numbered_nodes

logger = logging.getLogger(__name__)


class HVACMeasures:
    """Mixin class for HVAC system measures"""
    
    def discover_hvac_loops(self, epjson_data: Dict[str, Any]) -> str:
        """Discover all HVAC loops (Plant, Condenser, Air) in the EnergyPlus model
        
        Args:
            epjson_data: The epJSON data dictionary
            
        Returns:
            JSON string with HVAC loop information
        """
        try:
            logger.debug("Discovering HVAC loops")
            ep = epjson_data
            
            hvac_info = {
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
            logger.error(f"Error discovering HVAC loops: {e}")
            raise RuntimeError(f"Error discovering HVAC loops: {str(e)}")


    def get_loop_topology(self, epjson_data: Dict[str, Any], loop_name: str) -> str:
        """Get detailed topology information for a specific HVAC loop
        
        Args:
            epjson_data: The epJSON data dictionary
            loop_name: Name of the HVAC loop to analyze
            
        Returns:
            JSON string with loop topology information
        """
        try:
            logger.debug(f"Getting loop topology for '{loop_name}'")
            ep = epjson_data

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
            logger.error(f"Error getting loop topology: {e}")
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
                    "components": iter_numbered_components(
                        supply_path,
                        name_field_pattern="component_{}_name",
                        type_field_pattern="component_{}_object_type"
                    )
                }
                
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
                    "components": iter_numbered_components(
                        return_path,
                        name_field_pattern="component_{}_name",
                        type_field_pattern="component_{}_object_type"
                    )
                }
                
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
                "outlet_nodes": iter_numbered_nodes(
                    splitter,
                    node_field_pattern="outlet_{}_node_name"
                )
            }
            
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
                "inlet_nodes": iter_numbered_nodes(
                    mixer,
                    node_field_pattern="inlet_{}_node_name"
                )
            }
            
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
                "inlet_nodes": iter_numbered_nodes(
                    plenum,
                    node_field_pattern="inlet_{}_node_name"
                )
            }
            
            return plenum_info
        
        return None


    def visualize_loop_diagram(self, epjson_data: Dict[str, Any], loop_name: str = None, 
                            output_path: Optional[str] = None, format: str = "png", 
                            show_legend: bool = True) -> str:
        """
        Generate and save a visual diagram of HVAC loop(s) using custom topology-based approach
        
        Args:
            epjson_data: The epJSON data dictionary
            loop_name: Optional specific loop name (if None, creates diagram for first found loop)
            output_path: Optional custom output path (if None, creates one automatically)
            format: Image format for the diagram (png, jpg, pdf, svg)
            show_legend: Whether to include legend in topology-based diagrams (default: True)
        
        Returns:
            JSON string with diagram generation results and file path
        """
        try:
            logger.info("Creating custom loop diagram")
            
            # Determine output path
            if output_path is None:
                diagram_name = "hvac_diagram" if not loop_name else f"{loop_name}_diagram"
                output_path = f"{diagram_name}.{format}"
            
            # Method 1: Use topology data for custom diagram (PRIMARY)
            try:
                result = self._create_topology_based_diagram(epjson_data, loop_name, output_path, show_legend)
                if result["success"]:
                    logger.info(f"Custom topology diagram created: {output_path}")
                    return json.dumps(result, indent=2)
            except Exception as e:
                logger.warning(f"Topology-based diagram failed: {e}. Using simplified approach.")
            
            # Method 2: Simplified diagram (LAST RESORT)
            result = self._create_simplified_diagram(epjson_data, loop_name, output_path, format)
            logger.info(f"Simplified diagram created: {output_path}")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Error creating loop diagram: {e}")
            raise RuntimeError(f"Error creating loop diagram: {str(e)}")


    def _create_topology_based_diagram(self, epjson_data: Dict[str, Any], loop_name: Optional[str], 
                                     output_path: str, show_legend: bool = True) -> Dict[str, Any]:
        """
        Create diagram using topology data from get_loop_topology
        
        Args:
            epjson_data: The epJSON data dictionary
            loop_name: Optional specific loop name
            output_path: Path to save the diagram
            show_legend: Whether to show legend
            
        Returns:
            Dictionary with diagram generation results
        """
        if not GRAPHVIZ_AVAILABLE:
            raise ImportError(
                "Graphviz is required for topology-based diagrams. "
                "Please install it with: pip install graphviz"
            )
        
        # Get available loops
        loops_info = json.loads(self.discover_hvac_loops(epjson_data))
        
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
        topology_json = self.get_loop_topology(epjson_data, target_loop)
        
        # Create custom diagram using the topology data
        result = self.diagram_generator.create_diagram_from_topology(
            topology_json, output_path, f"Custom HVAC Diagram - {target_loop}", show_legend=show_legend
        )
        
        # Add additional metadata
        result.update({
            "method": "topology_based",
            "total_loops_available": sum(len(loops_info.get(key, [])) 
                                       for key in ['plant_loops', 'condenser_loops', 'air_loops'])
        })
        
        return result
    

    def _create_simplified_diagram(self, epjson_data: Dict[str, Any], loop_name: str, 
                                output_path: str, format: str) -> Dict[str, Any]:
        """Create a simplified diagram for HVAC loops from epJSON data
        
        Args:
            epjson_data: The epJSON data dictionary
            loop_name: Name of the loop to diagram
            output_path: Path to save the diagram
            format: Image format
            
        Returns:
            Dictionary with diagram generation results
        """
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError(
                "Matplotlib is required for diagram generation. "
                "Please install it with: pip install matplotlib"
            )
        
        ep = epjson_data
        
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
            "output_file": output_path,
            "loop_name": loop_name or "all_loops",
            "format": format,
            "loops_found": len(loops_info),
            "diagram_type": "simplified"
        }

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
