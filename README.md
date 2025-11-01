# Lode Star TCP Server

Lode Star is a TCP server for emulating GNSS/NMEA data streams.  
It supports dynamic simulation (circular movement), route playback from GeoJSON or CSV files, and playback from files containing NMEA sentences.

## Requirements

- Python 3.10 or higher

## Installation

### From Source

```bash
# Clone the repository
git clone <repository-url>
cd lode_star/lode_server

# Install the server package
pip install -e .
```

### Using pip (when published)

```bash
pip install lode_server
```

## Features

- **NMEA 0183 output** (RMC, GGA sentences)
- **Flexible plugin-based generator system**:
  - **dynamic**: Simulates circular movement from a given point with configurable speed, radius, and duration
  - **geojson**: Plays back a route from a GeoJSON file
  - **csv**: Plays back a route from a CSV file
  - **nmea**: Plays back a sequence of NMEA sentences from a text file (one per line)
  - **Extensible**: Support for custom generators via plugin system
- **TCP server**: Multiple clients can connect and receive the same data stream
- **Console output**: Each point's data is printed in a formatted table and updates in-place
- **Optional interactive start**: Use `--wait-for-keypress` to start transmission after pressing ENTER

## Usage

After installation, use the `lode-server` command:

```bash
lode-server <port> --source <type> [params...] [--wait-for-keypress]
```

Or run the module directly:

```bash
python -m lode_server <port> --source <type> [params...] [--wait-for-keypress]
```

### Sources and Parameters

**Parameter Formats:**
- **Positional parameters**: Required parameters specified by position (e.g., file paths, coordinates)
- **Named parameters**: Optional parameters in `name=value` format (e.g., `speed=10.0`, `duration=2.0`)

#### 1. Dynamic Generation (`dynamic`)

Simulates circular movement from a starting point.

**Syntax:**
```
dynamic <lat> <lon> [speed=<km/h>] [duration=<seconds>] [radius=<km>] [transition=<mode>]
```

**Required parameters:**
- `lat`, `lon` — starting coordinates (float)

**Optional parameters:**
- `speed=<value>` — speed in km/h (default: 10.0)
- `duration=<value>` — time in seconds between points (default: 1.0)
- `radius=<value>` — radius of the circular path in km (default: 0.1)
- `transition=<value>` — transition mode: `auto` (default) or `manual`

**Example:**
```bash
lode-server 10110 --source dynamic 55.7522 37.6156 speed=15.0 duration=2.0 radius=0.2 transition=manual
```

#### 2. GeoJSON Playback (`geojson`)

Plays back a route from a GeoJSON file.

**Syntax:**
```
geojson <path/to/route.json> [duration=<seconds>] [index=<start_number>]
```

**Required parameters:**
- `path/to/route.json` — path to GeoJSON file

**Optional parameters:**
- `duration=<value>` — override duration for all points in seconds (default: use values from file)
- `index=<value>` — starting point number (default: 1)

**GeoJSON format requirements:**
- Each point should have `speed` (km/h), `duration` (seconds), and optionally `transition` and `description` in its properties

**Examples:**
```bash
lode-server 10110 --source geojson examples/example.geojson
lode-server 10110 --source geojson examples/example.geojson duration=2.0 index=100
```

#### 3. CSV Playback (`csv`)

Plays back a route from a CSV file.

**Syntax:**
```
csv <path/to/route.csv> [duration=<seconds>] [index=<start_number>]
```

**Required parameters:**
- `path/to/route.csv` — path to CSV file

**Optional parameters:**
- `duration=<value>` — override duration for all points in seconds (default: use values from file)
- `index=<value>` — starting point number (default: 1)

**CSV format requirements:**
- CSV columns: `index,latitude,longitude,speed,elevation,duration,transition,description`
- Only latitude and longitude are required; others are optional with defaults

**Examples:**
```bash
lode-server 10110 --source csv examples/example.csv
lode-server 10110 --source csv examples/example.csv duration=1.5 index=50
```

#### 4. NMEA File Playback (`nmea`)

Plays back a sequence of NMEA sentences from a text file.  
Each line in the file should be a valid NMEA sentence (e.g., `$GPRMC,...`, `$GPGGA,...`).  
Currently, only RMC and GGA sentences are guaranteed to be parsed; others are skipped with a warning.

**Syntax:**
```
nmea <path/to/nmea.txt>
```

**Syntax:**
```
nmea <path/to/nmea.txt> [duration=<seconds>] [index=<start_number>]
```

**Required parameters:**
- `path/to/nmea.txt` — path to NMEA file

**Optional parameters:**
- `duration=<value>` — time in seconds between points (default: 1.0)
- `index=<value>` — starting point number (default: 1)

**Example:**
```bash
lode-server 10110 --source nmea examples/example.nmea duration=2.0
```

### Optional Flags

- `--wait-for-keypress` — Wait for user to press ENTER before starting transmission.

## Example Output

```
TCP Server started on port 10110
========================================
Generator source: dynamic
         Param 1: 55.7522
         Param 2: 37.6156
         Param 3: speed=15.0
         Param 4: duration=2.0
         Param 5: radius=0.2
         Param 6: transition=manual
Wait for keypress: No
========================================

      Point, #:	1
 Latitude, deg:	55.752200   
Longitude, deg:	37.615600   
   Speed, km/h:	10.00       
  Elevation, m:	0.00        
         Time:	2025-06-19 12:00:00
  Description:	
```

## GeoJSON Route Format

Each feature must be a Point with coordinates `[lon, lat]` and the following properties:

| Property     | Type    | Description                                                       |
|--------------|---------|-------------------------------------------------------------------|
| speed        | float   | Speed at this point in **km/h**.                                  |
| elevation    | float   | Elevation above sea level in meters.                              |
| duration     | float   | Duration to stay at this point, in seconds.                       |
| transition   | string  | (Optional) Transition mode: `"auto"` (default) or `"manual"`.     |
| description  | string  | (Optional) Comment or description for this point.                 |

**Example:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "speed": 15.0,
        "elevation": 100.1,
        "duration": 1.0,
        "transition": "manual",
        "description": "Start point"
      },
      "geometry": {
        "type": "Point",
        "coordinates": [37.61752, 55.75222]
      }
    }
  ]
}
```

## CSV Route Format

CSV columns:

```
number,latitude,longitude,speed,elevation,duration,transition,description
```

- Only the first five columns are required.
- `transition` and `description` are optional.
- Lines starting with `#` are treated as comments.

**Example:**
```
1,55.7522,37.6156,10.0,120.5,2.0,auto,"Moscow center"
2,55.7530,37.6200,12.0,121.0,3.0,manual,"Red Square"
```

## NMEA File Format

Each line must be a valid NMEA sentence (for example, `$GPRMC,...` or `$GPGGA,...`).  
Only RMC and GGA sentences are guaranteed to be parsed.  
If a line cannot be parsed, it will be skipped and a warning will be logged.

**Example:**
```
$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A
$GPGGA,123520,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
```

## Plugin System

Lode Star uses a plugin system for generators. Each generator (dynamic, geojson, csv, nmea) is implemented as a separate Python class and registered using a decorator. This makes it easy to add new generator types without modifying the core server code.

### Built-in Generators

The following generators are included with lode-server:
- `dynamic` - Circular movement simulation
- `geojson` - GeoJSON route playback  
- `csv` - CSV route playback
- `nmea` - NMEA sentence playback

### Creating Custom Generators

To add a new generator:

1. Create a class that inherits from `LodeGenerator`
2. Register it with the `@register_generator("name")` decorator
3. Implement the `_update_position()` method

**Example:**
```python
from lode_server.core import LodeGenerator, Position
from lode_server.generators import register_generator
from datetime import datetime, timezone

@register_generator("my_custom")
class MyCustomGenerator(LodeGenerator):
    def __init__(self, *args):
        super().__init__()
        # Your initialization logic here
        
    def _update_position(self):
        # Your position generation logic
        return Position(
            index=1,
            lat=55.7522,
            lon=37.6156,
            speed=10.0,
            elevation=0.0,
            time=datetime.now(timezone.utc),
            duration=1.0,
            transition="auto",
            description=""
        )
```

### External Plugin Distribution

External generators can be distributed as separate Python packages using entry points:

```toml
# pyproject.toml
[project.entry-points."lode_server.generators"]
my_generator = "my_package.generators:MyGenerator"
```

This allows extending the server with custom data sources or simulation logic without modifying the core codebase.

## Notes

- **Speed is always specified in km/h** in all sources and in GeoJSON/CSV.
- The server prints each point's data and sends sentences to all connected clients.
- If `--wait-for-keypress` is used, the server will not start sending data until you press ENTER.
- For `transition="manual"` in GeoJSON or CSV or generator, the server will wait for ENTER before sending the next point.

---
