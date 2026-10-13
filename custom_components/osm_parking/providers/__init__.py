from .base import ParkingProvider, ProviderFetchResult
from .brussels import BrusselsParkingProvider
from .ghent import GhentParkingProvider
from .dublin import DublinParkingProvider
from .golemio import GolemioParkingProvider
from .helsinki import HelsinkiParkingProvider
from .hong_kong import HongKongParkingProvider
from .madrid import MadridParkingProvider
from .melbourne import MelbourneParkingProvider
from .netherlands_rdw import NetherlandsRdwProvider
from .parkapi import ParkApiProvider
from .parkendd import ParkenDdProvider
from .singapore import SingaporeHdbProvider
from .st_gallen import StGallenParkingProvider
from .swiss import SwissParkingProvider
from .tfnsw import TfNswParkingProvider
from .tdx import TaiwanTdxParkingProvider

PROVIDERS: tuple[ParkingProvider, ...] = (
    SwissParkingProvider(),
    StGallenParkingProvider(),
    MadridParkingProvider(),
    MelbourneParkingProvider(),
    BrusselsParkingProvider(),
    DublinParkingProvider(),
    TaiwanTdxParkingProvider(),
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
