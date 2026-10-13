from .base import ParkingProvider, ProviderFetchResult
from .ghent import GhentParkingProvider
from .golemio import GolemioParkingProvider
from .helsinki import HelsinkiParkingProvider
from .hong_kong import HongKongParkingProvider
from .netherlands_rdw import NetherlandsRdwProvider
from .parkapi import ParkApiProvider
from .parkendd import ParkenDdProvider
from .singapore import SingaporeHdbProvider
from .tfnsw import TfNswParkingProvider

PROVIDERS: tuple[ParkingProvider, ...] = (
    GolemioParkingProvider(),
    TfNswParkingProvider(),
    ParkenDdProvider(),
    HelsinkiParkingProvider(),
    NetherlandsRdwProvider(),
    GhentParkingProvider(),
    ParkApiProvider(),
    HongKongParkingProvider(),
    SingaporeHdbProvider(),
)

__all__ = [
    "PROVIDERS",
    "ParkingProvider",
    "ProviderFetchResult",
]
