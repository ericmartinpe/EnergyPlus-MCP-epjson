"""
EnergyPlus tools with configuration management and simulation control.
Provides comprehensive interface for EnergyPlus epJSON file operations,
simulation execution, and results analysis.
"""

import os
import logging
from typing import Optional

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

# Define DATA_PATH for internal use
DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')

from .config import get_config, Config
from .utils.output_variables import OutputVariableManager
from .utils.output_meters import OutputMeterManager
from .utils.people_utils import PeopleManager
from .utils.lights_utils import LightsManager
from .utils.electric_equipment_utils import ElectricEquipmentManager

# Import measure mixins
from .measures.file_operations import FileOperationsMeasures
from .measures.inspection import InspectionMeasures
from .measures.internal_loads import InternalLoadsMeasures
from .measures.outputs import OutputsMeasures
from .measures.schedules import SchedulesMeasures
from .measures.hvac import HVACMeasures
from .measures.envelope import EnvelopeMeasures
from .measures.simulation import SimulationMeasures

logger = logging.getLogger(__name__)


class EnergyPlusManager(
    FileOperationsMeasures,
    InspectionMeasures,
    InternalLoadsMeasures,
    OutputsMeasures,
    SchedulesMeasures,
    HVACMeasures,
    EnvelopeMeasures,
    SimulationMeasures
):
    """
    Manager class for EnergyPlus epJSON operations with configuration management.
    
    Provides comprehensive interface for:
    - Loading and manipulating epJSON files
    - Running EnergyPlus simulations  
    - Inspecting and modifying building components
    - Analyzing simulation results
    - Managing output variables and meters
    - Visualizing HVAC systems
    
    All functionality is organized into separate measure modules:
    - FileOperationsMeasures: File I/O, conversion, validation
    - InspectionMeasures: Model inspection and basic information
    - InternalLoadsMeasures: People, lights, and equipment management
    - OutputsMeasures: Output variables and meters
    - SchedulesMeasures: Schedule inspection
    - HVACMeasures: HVAC system discovery and visualization
    - EnvelopeMeasures: Envelope modifications and coating
    - SimulationMeasures: Running simulations and post-processing
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
