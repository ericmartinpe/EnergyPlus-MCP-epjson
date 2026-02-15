"""
Simulation control and execution measures for EnergyPlus models.

This module provides mixin class for modifying simulation settings, running simulations,
and creating interactive plots from simulation results.
"""

import os
import json
import logging
import calendar
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

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

from ..utils.run_functions import run

logger = logging.getLogger(__name__)


class SimulationMeasures:
    """Mixin class for simulation control and execution measures"""
    
    def modify_simulation_settings(self, epjson_data: Dict[str, Any], object_type: str, field_updates: Dict[str, Any], 
                                 run_period_index: int = 0) -> Dict[str, Any]:
        """
        Modify SimulationControl or RunPeriod settings in the epJSON data
        
        Args:
            epjson_data: The epJSON data dictionary to modify
            object_type: "SimulationControl" or "RunPeriod"
            field_updates: Dictionary of field names and new values
            run_period_index: Index of RunPeriod to modify (default 0, ignored for SimulationControl)
        
        Returns:
            Modified epJSON data dictionary
        """
        try:
            logger.info(f"Modifying {object_type} settings")
            ep = epjson_data
            
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
            
            logger.info(f"Successfully modified {object_type} ({len(modifications_made)} modifications)")
            return ep
            
        except Exception as e:
            logger.error(f"Error modifying simulation settings: {e}")
            raise RuntimeError(f"Error modifying simulation settings: {str(e)}")

    
    def run_simulation(self, epjson_data: Dict[str, Any], weather_file: str = None, 
                        output_directory: str = None, annual: bool = True,
                        design_day: bool = False, readvars: bool = True,
                        expandobjects: bool = True, ep_version: str = "25-1-0") -> str:
        """
        Run EnergyPlus simulation with specified epJSON data and weather file
        
        Args:
            epjson_data: The epJSON data dictionary to simulate
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
        import tempfile
        
        try:
            logger.info(f"Starting simulation")
            
            # Resolve weather file path
            resolved_weather_path = None
            if weather_file:
                resolved_weather_path = self._resolve_weather_file_path(weather_file)
                logger.info(f"Using weather file: {resolved_weather_path}")
            
            # Save epJSON data to a temporary file
            temp_fd, temp_epjson_path = tempfile.mkstemp(suffix='.epJSON', prefix='energyplus_sim_')
            os.close(temp_fd)  # Close the file descriptor
            self.save_json(epjson_data, temp_epjson_path)
            logger.info(f"Saved epJSON data to temporary file: {temp_epjson_path}")
            
            # Set up output directory
            if output_directory is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_directory = str(Path(self.config.paths.output_dir) / f"simulation_{timestamp}")
            
            # Create output directory if it doesn't exist
            os.makedirs(output_directory, exist_ok=True)
            logger.info(f"Output directory: {output_directory}")
            
            # Get version from epJSON data
            ep = epjson_data
            version = ep["Version"]["Version 1"]["version_identifier"]
            # Split, pad to 3 parts, and join with dashes
            ep_version = "-".join((version.split(".") + ["0", "0"])[:3])
            
            # Configure simulation options
            simulation_options = {
                'idf': temp_epjson_path,
                'output_directory': output_directory,
                'annual': annual,
                'design_day': design_day,
                'readvars': readvars,
                'expandobjects': expandobjects,
                'output_prefix': Path(temp_epjson_path).stem,
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
                    "weather_file": resolved_weather_path,
                    "output_directory": output_directory,
                    "simulation_duration": str(duration),
                    "output_files": output_files,
                    "energyplus_result": str(result) if result else "Simulation completed",
                    "timestamp": end_time.isoformat()
                }
                
                logger.info(f"Simulation completed successfully in {duration}")
                
                # Clean up temporary file
                try:
                    os.unlink(temp_epjson_path)
                    logger.debug(f"Cleaned up temporary file: {temp_epjson_path}")
                except Exception:
                    pass
                
                return json.dumps(simulation_result, indent=2)
                
            except Exception as e:
                # Try to find error file for more detailed error information
                error_file = Path(output_directory) / f"{Path(temp_epjson_path).stem}.err"
                error_details = ""
                
                if error_file.exists():
                    try:
                        with open(error_file, 'r') as f:
                            error_details = f.read()
                    except Exception:
                        error_details = "Could not read error file"
                
                simulation_result = {
                    "success": False,
                    "weather_file": resolved_weather_path,
                    "output_directory": output_directory,
                    "error": str(e),
                    "error_details": error_details,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.error(f"Simulation failed: {str(e)}")
                
                # Clean up temporary file
                try:
                    os.unlink(temp_epjson_path)
                except Exception:
                    pass
                
                return json.dumps(simulation_result, indent=2)
                
        except Exception as e:
            logger.error(f"Error setting up simulation: {e}")
            raise RuntimeError(f"Error running simulation: {str(e)}")

        

    def _resolve_weather_file_path(self, weather_file: str) -> str:
        """Resolve weather file path (handle relative paths, sample files, EnergyPlus weather data, etc.)"""
        from ..utils.path import resolve_path
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
