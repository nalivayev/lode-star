from datetime import datetime, timezone
from json import load

from lode_server.core import FileGenerator, Position
from lode_server.generators import register_generator


@register_generator("geojson")
class GeoJSONGenerator(FileGenerator):
    """
    NMEA generator that follows a route defined in GeoJSON format.
    Returns Position objects with recommended duration and transition for each point.
    """
    def __init__(self, *args) -> None:
        super().__init__()
        
        # Parse common parameters and get remaining args
        remaining_args = self._parse_common_params(args)
        
        if len(remaining_args) < 1:
            raise ValueError("Route file path must be specified")
            
        self._load_file(remaining_args[0])
        
    def _load_file(self, filename: str) -> None:
        """Load and validate the GeoJSON route file"""
        try:
            with open(filename, 'r') as f:
                route_data = load(f)
                
            if not isinstance(route_data, dict):
                raise ValueError("Invalid GeoJSON format")
                
            if 'features' not in route_data:
                raise ValueError("GeoJSON file must contain 'features'")
            
            index = 1
            
            for feature in route_data['features']:
                if feature['geometry']['type'] != 'Point':
                    continue
                    
                coords = feature['geometry']['coordinates']
                props = feature.get('properties', {})
                
                point = Position(
                    index=index,
                    lat=coords[1],
                    lon=coords[0],
                    speed=float(props.get('speed', 0)),
                    elevation=float(props.get('elevation', 0)),
                    time=datetime(1970, 1, 1, tzinfo=timezone.utc),  # Placeholder, updated in _update_position()
                    duration=float(props.get('duration', 0)),
                    transition=props.get('transition', 'auto'),
                    description=props.get('description', '')
                )
                
                # Apply common parameter overrides
                point = self._apply_common_params(point, index)
                self._positions.append(point)
                index += 1
                
            if not self._positions:
                raise ValueError("No valid points found in route file")
                
        except Exception as e:
            raise ValueError(f"Failed to load route file: {str(e)}")

    def _update_position(self):
        """
        Get next position and add current timestamp.
        GeoJSON files don't contain meaningful timestamps, so we add current time.
        """
        position = super()._update_position()
        if position is not None:
            position.time = datetime.now(timezone.utc)
        return position
