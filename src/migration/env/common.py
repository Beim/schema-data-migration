import os
from pathlib import Path

from dotenv import load_dotenv

_HERE = Path(os.getcwd())

try:
    # only necessary during development
    load_dotenv(_HERE / ".env", override=True)
except Exception as e:
    print(e)


def getenv(key: str, default: str = "", required: bool = False) -> str:
    """
    get an Environment variable

    :param key: Environment Variable key
    :param default:
    :param required: throw error if required
    """
    res = os.getenv(key, default)
    if (res == "" or res is None) and required:
        raise KeyError("Required Environment variable {} not defined".format(key))
    return res
