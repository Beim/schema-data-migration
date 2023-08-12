from . import load

LEVEL_INFO = "INFO"
LEVEL_DEBUG = "DEBUG"

LOG_LEVEL = load.getenv("LOG_LEVEL", default=LEVEL_INFO, required=False)
LOG_FILE = load.getenv("LOG_FILE", default="sdm.log", required=False)
