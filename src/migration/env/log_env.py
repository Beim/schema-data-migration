from . import common

LEVEL_INFO = "INFO"
LEVEL_DEBUG = "DEBUG"

LOG_LEVEL = common.getenv("LOG_LEVEL", default=LEVEL_INFO, required=False)
LOG_FILE = common.getenv("LOG_FILE", default="sdm.log", required=False)
