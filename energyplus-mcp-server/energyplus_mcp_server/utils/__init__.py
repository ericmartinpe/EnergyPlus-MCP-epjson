"""Utility modules for EnergyPlus MCP Server"""

__version__ = "0.1.0"

from .schedules import (
    ScheduleValueParser,
    ScheduleLanguageParser,
    ScheduleConverter,
    SimpleScheduleFormat,
)
from .output_variables import OutputVariableManager
from .output_meters import OutputMeterManager
from .people import PeopleManager
from .lights import LightsManager
from .equipment import EquipmentManager
from .run_functions import run

# Optional diagram generation (requires graphviz)
try:
    from .diagrams import HVACDiagramGenerator

    _DIAGRAM_AVAILABLE = True
except ImportError:
    HVACDiagramGenerator = None
    _DIAGRAM_AVAILABLE = False

from .path import (
    PathResolver,
    resolve_path,
    resolve_epjson_path,
    resolve_weather_file_path,
    resolve_output_path,
    find_weather_files_by_name,
    validate_file_path,
    ensure_directory_exists,
    get_file_info,
)

# Build __all__ list conditionally
__all__ = [
    "ScheduleValueParser",
    "ScheduleLanguageParser",
    "ScheduleConverter",
    "SimpleScheduleFormat",
    "OutputVariableManager",
    "OutputMeterManager",
    "PeopleManager",
    "LightsManager",
    "EquipmentManager",
    "run",
    "PathResolver",
    "resolve_path",
    "resolve_epjson_path",
    "resolve_weather_file_path",
    "resolve_output_path",
    "find_weather_files_by_name",
    "validate_file_path",
    "ensure_directory_exists",
    "get_file_info",
]

# Add diagram generator if available
if _DIAGRAM_AVAILABLE:
    __all__.append("HVACDiagramGenerator")
