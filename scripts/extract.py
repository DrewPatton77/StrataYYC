import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "include"))

from extract_311 import ServiceRequestExtractor
from extract_weather import CalgaryWeatherExtractor

ServiceRequestExtractor().run()
CalgaryWeatherExtractor().run()
