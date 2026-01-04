"""GUI package for application.

Note: avoid importing heavy QtWebEngine components at package import time to keep
test imports lightweight. Import GUI widgets explicitly where needed, e.g.:

	from nast_gs.gui.map_view import MapWindow

"""

__all__ = []
