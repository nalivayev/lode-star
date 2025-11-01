from datetime import datetime, timezone
import csv

from lode_server.core import FileGenerator, Position
from lode_server.generators import register_generator


@register_generator("csv")
class CSVGenerator(FileGenerator):
    """
    NMEA generator that reads position data from a CSV file.
    
    CSV format:
    point_number,latitude,longitude,speed,elevation,duration,transition,description
    
    Example row:
    1,55.7522,37.6156,10.0,120.5,2.0,auto,"Moscow center"
    """
    
    def __init__(self, *args) -> None:
        """
        Args:
            args: [filename, duration=<seconds>, index=<start_number>] - path to CSV file and optional parameters
        """
        super().__init__()
        
        # Parse common parameters and get remaining args
        remaining_args = self._parse_common_params(args)
        
        if len(remaining_args) < 1:
            raise ValueError("CSV file path must be specified")
            
        self._load_file(remaining_args[0])
        
    def _load_file(self, filename: str) -> None:
        """Load and validate the CSV file"""
        try:
            with open(filename, 'r', newline='') as f:
                reader = csv.reader(f)
                index = 1
                for row in reader:
                    # Skip empty or comment lines
                    if not row or row[0].startswith('#'):
                        continue
                        
                    if len(row) < 5:
                        raise ValueError(f"Invalid CSV format in row: {row}. Need at least 5 columns")
                    
                    # Parse required fields
                    lat = float(row[1])
                    lon = float(row[2])
                    speed = float(row[3]) if len(row) > 3 else 0.0
                    elevation = float(row[4]) if len(row) > 4 else 0.0
                    
                    # Parse optional fields
                    duration = float(row[5]) if len(row) > 5 else 0.0
                    transition = row[6] if len(row) > 6 else "auto"
                    description = row[7] if len(row) > 7 else ""
                    
                    position = Position(
                        index=index,
                        lat=lat,
                        lon=lon,
                        speed=speed,
                        elevation=elevation,
                        time=datetime(1970, 1, 1, tzinfo=timezone.utc),  # Placeholder, updated in _update_position()
                        duration=duration,
                        transition=transition,
                        description=description
                    )
                    
                    # Apply common parameter overrides
                    position = self._apply_common_params(position, index)
                    self._positions.append(position)
                    index += 1
                
            if not self._positions:
                raise ValueError("No valid points found in CSV file")
                
        except Exception as e:
            raise ValueError(f"Failed to load CSV file: {str(e)}")

    def _update_position(self):
        """
        Get next position and add current timestamp.
        CSV files don't contain meaningful timestamps, so we add current time.
        """
        position = super()._update_position()
        if position is not None:
            position.time = datetime.now(timezone.utc)
        return position
