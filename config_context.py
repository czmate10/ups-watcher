from dataclasses import dataclass
from typing import List


@dataclass
class DatadogConfig:
    host: str
    port: int
    namespace: str
    watchlist: List[str]


@dataclass
class ConfigContext:
    datadog_config: DatadogConfig
