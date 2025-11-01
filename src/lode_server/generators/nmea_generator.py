from lode_server.core import FileGenerator, NMEADecoder
from lode_server.generators import register_generator


@register_generator("nmea")
class NMEAGenerator(FileGenerator):
    """
    Generator that reads NMEA sentences from a file and yields Position objects.
    Each line in the file should be a valid NMEA sentence.
    Unsupported or unparsable lines are skipped and logged.
    """
    def __init__(self, *args) -> None:
        super().__init__()
        
        # Parse common parameters and get remaining args
        remaining_args = self._parse_common_params(args)
        
        if len(remaining_args) < 1:
            raise ValueError("NMEA file path must be specified")
        
        self._load_file(remaining_args[0])

    def _load_file(self, filename: str) -> None:
        """Load NMEA sentences from the specified file and parse them into Position objects."""
        with open(filename, 'r') as f:
            index = 1
            for line in f:
                try:
                    pos = NMEADecoder.decode(line)
                    if pos:
                        pos.index = index
                        pos.duration = 1.0  # Default duration
                        
                        # Apply common parameter overrides
                        pos = self._apply_common_params(pos, index)
                        
                        self._positions.append(pos)
                        index += 1
                except Exception as e:
                    continue
