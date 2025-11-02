import threading
import socket

from queue import Queue
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Optional, Iterator
from dataclasses import dataclass
from datetime import timezone


@dataclass
class Position:
    """
    Container for position and navigation data with timestamp.
    
    Represents a single point in space with associated navigation metrics and timing information.
    Used for both static points and route navigation.

    Attributes:
        index (int): Number of a point
        lat (float): Latitude in decimal degrees. Range: -90 to +90.
        lon (float): Longitude in decimal degrees. Range: -180 to +180.
        speed (float): Speed over ground in km/h (nautical miles per hour).
        elevation (float): Elevation/altitude above sea level in meters.
        time (datetime): UTC timestamp of the position measurement.
        duration (float): Optional. Suggested duration at this point in seconds (for routes).
                        Default: 0.0 (no pause at point).
        transition (str): Transition mode to next position: 'auto' (default), 'manual', or 'key'.
        description (str): Optional description or comment for this position.
    
    Examples:
        >>> pos = Position(1, 55.7522, 37.6156, 5.0, 120.5, datetime.now(timezone.utc))
        >>> route_point = Position(1, 59.9343, 30.3351, 10.0, 5.5, 
        ...                          datetime.now(timezone.utc), 
        ...                          duration=2.5, transition='manual', description='Start point')
    """
    index: int                  # Number of a point
    lat: float                  # Latitude in degrees
    lon: float                  # Longitude in degrees
    speed: float                # Speed in km/h
    elevation: float            # Elevation in meters
    time: datetime              # Current time
    duration: float = 0.0       # Duration at current point (for routes)
    transition: str = "auto"    # Transition mode: 'auto', 'manual'
    description: str = ""       # Optional description or comment


class NMEAEncoder:
    """Handles encoding of Position to NMEA sentences"""
    
    # Constants for GGA sentence
    GGA_FIX_QUALITY = '1'          # 0=invalid, 1=GPS fix, 2=DGPS fix, etc.
    GGA_NUM_SATELLITES = '08'       # Number of satellites in use (00-12)
    GGA_HDOP = '1.0'                # Horizontal dilution of precision
    GGA_GEOID_SEPARATION = '0.0'    # Geoid separation (meters)
    GGA_DGPS_AGE = ''               # Age of DGPS data (empty for no DGPS)
    GGA_DGPS_REF = ''               # DGPS reference station ID
    
    @staticmethod
    def format_coords(lat: float, lon: float) -> tuple[str, str, str, str]:
        """
        Format latitude and longitude for NMEA sentences.
        Returns:
            Tuple[str, str, str, str]: (lat_str, lat_dir, lon_str, lon_dir)
        """
        lat_deg = int(lat)
        lat_min = abs((lat - lat_deg) * 60)
        lat_dir = 'N' if lat >= 0 else 'S'
        lat_str = f"{abs(lat_deg):02d}{lat_min:09.6f}"

        lon_deg = int(lon)
        lon_min = abs((lon - lon_deg) * 60)
        lon_dir = 'E' if lon >= 0 else 'W'
        lon_str = f"{abs(lon_deg):03d}{lon_min:09.6f}"

        return lat_str, lat_dir, lon_str, lon_dir
    
    @staticmethod
    def calculate_checksum(sentence: str) -> str:
        """
        Calculate the NMEA checksum for a sentence.
        Args:
            sentence (str): The NMEA sentence without the starting '$' and checksum.
        Returns:
            str: The checksum as a two-digit hexadecimal string.
        """
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)
        return f"{checksum:02X}"
    
    def encode_gga(self, data: Position) -> str:
        """
        Generate an NMEA GGA sentence from position data.
        Returns:
            str: The generated GGA sentence
        """
        time_str = data.time.strftime("%H%M%S.%f")[:-3]
        lat_str, lat_dir, lon_str, lon_dir = self.format_coords(data.lat, data.lon)

        gga = (
            f"GPGGA,{time_str},{lat_str},{lat_dir},"
            f"{lon_str},{lon_dir},{self.GGA_FIX_QUALITY},{self.GGA_NUM_SATELLITES},"
            f"{self.GGA_HDOP},{data.elevation:.1f},M,{self.GGA_GEOID_SEPARATION},M,"
            f"{self.GGA_DGPS_AGE},{self.GGA_DGPS_REF}"
        )
        return f"${gga}*{self.calculate_checksum(gga)}\r\n"
    
    def encode_rmc(self, data: Position) -> str:
        """
        Generate an NMEA RMC sentence from position data.
        Returns:
            str: The generated RMC sentence
        """
        time_str = data.time.strftime("%H%M%S.%f")[:-3]
        date_str = data.time.strftime("%d%m%y")
        lat_str, lat_dir, lon_str, lon_dir = self.format_coords(data.lat, data.lon)

        speed_knots = data.speed * 0.539957  # Convert speed from km/h to knots

        rmc = (
            f"GPRMC,{time_str},A,{lat_str},{lat_dir},"
            f"{lon_str},{lon_dir},{speed_knots:.1f},0.0,{date_str},,,A"
        )
        return f"${rmc}*{self.calculate_checksum(rmc)}\r\n"


class NMEADecoder:
    """
    Decodes NMEA sentences (GGA, RMC) into Position objects.
    Unsupported or invalid sentences raise exceptions.
    """
    @staticmethod
    def decode(nmea: str) -> Optional[Position]:
        if not nmea.startswith('$'):
            raise ValueError("Not a valid NMEA sentence")
        nmea = nmea.strip()
        if '*' in nmea:
            nmea = nmea[:nmea.index('*')]
        fields = nmea[1:].split(',')

        if fields[0] == 'GPRMC' or fields[0] == 'RMC' or fields[0] == 'GNRMC':
            if len(fields) < 10 or fields[2] != 'A':
                raise ValueError("Invalid RMC sentence")
            time_str = fields[1]
            date_str = fields[9]
            lat = NMEADecoder._parse_lat(fields[3], fields[4])
            lon = NMEADecoder._parse_lon(fields[5], fields[6])
            speed = float(fields[7]) * 1.852 if fields[7] else 0.0  # knots to km/h
            elevation = 0.0  # Not present in RMC
            dt = NMEADecoder._parse_datetime(time_str, date_str)
            if dt is None:
                raise ValueError("No valid datetime in RMC")
            return Position(0, lat, lon, speed, elevation, dt)
        elif fields[0] == 'GPGGA' or fields[0] == 'GGA' or fields[0] == 'GNGGA':
            if len(fields) < 10:
                raise ValueError("Invalid GGA sentence")
            time_str = fields[1]
            lat = NMEADecoder._parse_lat(fields[2], fields[3])
            lon = NMEADecoder._parse_lon(fields[4], fields[5])
            elevation = float(fields[9]) if fields[9] else 0.0
            speed = 0.0  # Not present in GGA
            dt = NMEADecoder._parse_datetime(time_str)
            if dt is None:
                raise ValueError("No valid datetime in GGA")
            return Position(0, lat, lon, speed, elevation, dt)
        raise ValueError("Unsupported NMEA sentence type")

    @staticmethod
    def _parse_coordinate(coord_str, max_degrees_digits):
        """
        Parse NMEA coordinate string (degrees + minutes) to decimal degrees.
        
        Args:
            coord_str: Coordinate string in DDMM.MMMM or DDDMM.MMMM format
            max_degrees_digits: Maximum number of digits for degrees (2 for lat, 3 for lon)
            
        Returns:
            float: Coordinate in decimal degrees
        """
        if not coord_str:
            return 0.0
            
        # Find decimal point to determine where degrees end
        if '.' in coord_str:
            # Find the position where minutes start (should have 2 digits before decimal for minutes)
            dot_pos = coord_str.find('.')
            # Minutes should be XX.XXXXX format, so degrees end 2 positions before the dot
            if dot_pos >= 4:  # Ensure we have at least DDMM.XXXXX or DDDMM.XXXXX
                deg_end = dot_pos - 2
                deg = int(coord_str[:deg_end])
                min_val = float(coord_str[deg_end:])
            else:
                # Fallback to fixed positions based on coordinate type
                deg_digits = min(max_degrees_digits, len(coord_str) - 2)
                deg = int(coord_str[:deg_digits])
                min_val = float(coord_str[deg_digits:])
        else:
            # No decimal point, assume fixed format based on coordinate type
            deg_digits = min(max_degrees_digits, len(coord_str) - 2) if len(coord_str) > 2 else max_degrees_digits
            deg = int(coord_str[:deg_digits])
            min_val = float(coord_str[deg_digits:]) if len(coord_str) > deg_digits else 0.0
        
        return deg + min_val / 60

    @staticmethod
    def _parse_lat(lat_str, ns):
        if not lat_str or not ns:
            return 0.0
        
        lat = NMEADecoder._parse_coordinate(lat_str, 2)  # Latitude: max 2 digits for degrees
        if ns == 'S':
            lat = -lat
        return lat

    @staticmethod
    def _parse_lon(lon_str, ew):
        if not lon_str or not ew:
            return 0.0
        
        lon = NMEADecoder._parse_coordinate(lon_str, 3)  # Longitude: max 3 digits for degrees
        if ew == 'W':
            lon = -lon
        return lon

    @staticmethod
    def _parse_datetime(time_str, date_str=None):
        try:
            if not time_str:
                return None
            hour = int(time_str[0:2])
            minute = int(time_str[2:4])
            second = int(time_str[4:6])
            microsecond = int(float('0.' + time_str.split('.')[1]) * 1e6) if '.' in time_str else 0
            if date_str:
                day = int(date_str[0:2])
                month = int(date_str[2:4])
                year = int(date_str[4:6]) + 2000
                return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc)
            else:
                now = datetime.now(timezone.utc)
                return now.replace(hour=hour, minute=minute, second=second, microsecond=microsecond)
        except Exception:
            return None


class LodeGenerator(ABC, Iterator):
    """
    Abstract base class for data generators.
    Works as an iterator that yields Position objects.
    """
    def __init__(self) -> None:
        """Initialize the generator with default values."""
        pass

    @abstractmethod
    def _update_position(self) -> Optional[Position]:
        """
        Update the current position.
        Returns:
            Optional[Position]: Position data, None if finished
        """
        pass

    def __iter__(self) -> Iterator:
        return self
    
    def __next__(self) -> Position:
        """
        Get next position data.
        Returns:
            Position: Current position and navigation data
        Raises:
            StopIteration: When route is finished or generator stopped
        """
        data = self._update_position()
        if data is None:
            raise StopIteration
        return data
    

class FileGenerator(LodeGenerator):

    def __init__(self, *args) -> None:
        """Initialize file generator with common parameters support."""
        super().__init__()
        self._positions: list[Position] = []
        self._index: int = 0
        
        # Parse common parameters
        self._duration_override: Optional[float] = None
        self._index_override: Optional[int] = None
        
    def _parse_common_params(self, args: tuple) -> tuple:
        """
        Parse common file generator parameters and return remaining args.
        
        Args:
            args: All arguments passed to generator
            
        Returns:
            tuple: Arguments with common parameters removed
        """
        remaining_args = []
        
        for param in args:
            if isinstance(param, str) and param.startswith("duration="):
                try:
                    self._duration_override = float(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid duration value")
            elif isinstance(param, str) and param.startswith("index="):
                try:
                    self._index_override = int(param.split("=", 1)[1])
                except Exception:
                    raise ValueError("Invalid index value")
            else:
                remaining_args.append(param)
                
        return tuple(remaining_args)
    
    def _apply_common_params(self, position: Position, original_index: int) -> Position:
        """
        Apply common parameter overrides to a position.
        
        Args:
            position: Original position from file
            original_index: Original index (1-based) from file loading
            
        Returns:
            Position: Position with applied overrides
        """
        # Override duration if specified
        if self._duration_override is not None:
            position.duration = self._duration_override
            
        # Override index if specified
        if self._index_override is not None:
            position.index = self._index_override + (original_index - 1)
            
        return position

    def _update_position(self) -> Optional[Position]:
        """
        Get next point from file data.
        Returns the position exactly as loaded from file.
        Subclasses should override this method to add missing fields (e.g., current timestamp).
        
        Returns:
            Optional[Position]: Next position data or None if finished
        """
        if self._index >= len(self._positions):
            return None
        position = self._positions[self._index]
        self._index += 1
        return position


class ClientThread(threading.Thread):
    """Thread for handling client connections and broadcasting data."""
    
    def __init__(self, port: int):
        super().__init__(daemon=True)
        self._port = port
        self._clients = []
        self._data_queue = Queue()
        self._running = True
        self._lock = threading.Lock()
        self._server_socket = None

    def _broadcast(self, rmc: str, gga: str) -> None:
        """Send data to all connected clients."""
        with self._lock:
            for conn in self._clients[:]:
                try:
                    conn.sendall(rmc.encode('ascii'))
                    conn.sendall(gga.encode('ascii'))
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    self._clients.remove(conn)

    def _cleanup(self) -> None:
        """Clean up resources."""
        with self._lock:
            for conn in self._clients:
                try:
                    conn.close()
                except Exception:
                    pass
            self._clients.clear()
        
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass

    def run(self) -> None:
        """Main thread loop for accepting clients and broadcasting data."""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(('0.0.0.0', self._port))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1)

            while self._running:
                try:
                    # Accept new clients
                    try:
                        conn, addr = self._server_socket.accept()
                        with self._lock:
                            self._clients.append(conn)
                    except socket.timeout:
                        pass

                    # Process data from queue
                    while not self._data_queue.empty():
                        rmc, gga = self._data_queue.get()
                        self._broadcast(rmc, gga)

                except Exception as e:
                    if self._running:
                        pass  # Silent error handling
        finally:
            self._cleanup()

    def add_data(self, rmc: str, gga: str) -> None:
        """Add data to the broadcast queue."""
        self._data_queue.put((rmc, gga))

    def stop(self) -> None:
        """Stop the thread gracefully."""
        self._running = False
        self._cleanup()
