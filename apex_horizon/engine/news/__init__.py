"""The News System — Design Bible Volume 10.

News gives texture and explanation to the otherwise abstract movements of the
Market and Economy (V10.18). It informs rather than predicts (V10.3), and every
article is traceable to something the simulation actually did (V10.9, V10.24).
"""

from .article import NewsArticle, NewsTier
from .generator import NewsSystem

__all__ = ["NewsArticle", "NewsSystem", "NewsTier"]
