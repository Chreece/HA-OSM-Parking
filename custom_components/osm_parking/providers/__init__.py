from .base import ParkingProvider, ProviderFetchResult
from .brussels import BrusselsParkingProvider
from .ghent import GhentParkingProvider
from .dublin import DublinParkingProvider
from .golemio import GolemioParkingProvider
from .helsinki import HelsinkiParkingProvider
from .hong_kong import HongKongParkingProvider
from .madrid import MadridParkingProvider
from .malaga import MalagaParkingProvider
from .lyon import LyonParkingProvider
from .ispark import IstanbulIsparkProvider
from .izmir import IzmirIzumProvider
from .lille import LilleParkingProvider
from .grenoble import GrenobleParkingProvider
from .nantes import NantesParkAndRideProvider, NantesPublicParkingProvider
from .montpellier import MontpellierParkingProvider
from .melbourne import MelbourneParkingProvider
from .netherlands_rdw import NetherlandsRdwProvider
from .parkapi import ParkApiProvider
from .parkendd import ParkenDdProvider
from .singapore import SingaporeHdbProvider
from .strasbourg import StrasbourgParkingProvider
from .st_gallen import StGallenParkingProvider
from .swiss import SwissParkingProvider
from .tfnsw import TfNswParkingProvider
from .tdx import TaiwanTdxParkingProvider

PROVIDERS: tuple[ParkingProvider, ...] = (
    IstanbulIsparkProvider(),
    IzmirIzumProvider(),
    LilleParkingProvider(),
    GrenobleParkingProvider(),
    LyonParkingProvider(),
    NantesPublicParkingProvider(),
    NantesParkAndRideProvider(),
    StrasbourgParkingProvider(),
    MontpellierParkingProvider(),
    MalagaParkingProvider(),
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
