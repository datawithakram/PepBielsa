"""
collectors/ — Multi-Source Football Data Collection Engine
Each collector is independent and returns standardized dicts.
"""
from .api_football  import APIFootballCollector
from .sofascore     import SofaScoreCollector
from .fotmob        import FotMobCollector
from .fbref         import FBrefCollector
from .understat     import UnderstatCollector
from .statsbomb     import StatsBombCollector
from .injuries      import InjuriesCollector
from .news_collector import NewsCollector
from .youtube_collector import YouTubeCollector

__all__ = [
    "APIFootballCollector",
    "SofaScoreCollector",
    "FotMobCollector",
    "FBrefCollector",
    "UnderstatCollector",
    "StatsBombCollector",
    "InjuriesCollector",
    "NewsCollector",
    "YouTubeCollector",
]
