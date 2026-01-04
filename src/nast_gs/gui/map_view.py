"""Simple PyQt6 map view using Leaflet in QWebEngineView."""
from PyQt6 import QtWidgets, QtCore, QtWebEngineWidgets
from typing import List, Tuple


class MapWindow(QtWidgets.QMainWindow):
    """Map window built around a Leaflet HTML template. Provides methods to update track and ground station marker dynamically via JavaScript."""

    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
      <style>html,body,#map{height:100%;margin:0}</style>
    </head>
    <body>
      <div id="map"></div>
      <script>
        var map = L.map('map').setView([0,0], 2);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19}).addTo(map);
        var poly = L.polyline([], {color: 'red'}).addTo(map);
        var gs_marker = null;
        var sat_marker = null;

        function setTrack(coords) {
          poly.setLatLngs(coords);
          if (coords.length) map.fitBounds(poly.getBounds());
        }

        function setGroundStation(lat, lon) {
          if (gs_marker) map.removeLayer(gs_marker);
          gs_marker = L.circleMarker([lat, lon], {radius:6, color:'yellow', fillColor:'orange', fillOpacity:0.9}).addTo(map);
        }

        function setSatellite(lat, lon) {
          if (sat_marker) map.removeLayer(sat_marker);
          sat_marker = L.circleMarker([lat, lon], {radius:5, color:'cyan', fillColor:'aqua', fillOpacity:0.9}).addTo(map);
        }
      </script>
    </body>
    </html>
    """

    def __init__(self, title: str = "NAST Geo Suite - Map"):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1200, 800)
        self.view = QtWebEngineWidgets.QWebEngineView()
        self.setCentralWidget(self.view)
        self._page_ready = False
        self._pending_js = []
        self.view.page().loadFinished.connect(self._on_load_finished)
        self.view.setHtml(self.HTML_TEMPLATE)

    def _on_load_finished(self, ok: bool):
        self._page_ready = ok
        # flush pending JS commands
        while self._pending_js:
            js = self._pending_js.pop(0)
            self.view.page().runJavaScript(js)

    def set_track(self, points: List[Tuple[float, float]]):
        """Points is a list of (lat, lon) tuples."""
        # Split the track into segments when longitude jumps across the dateline to avoid long wrap-around lines
        if not points:
            return
        segs = []
        cur = [points[0]]
        for a, b in zip(points, points[1:]):
            lon1 = a[1]
            lon2 = b[1]
            raw = lon2 - lon1
            if raw > 180 or raw < -180:
                # break segment
                segs.append(cur)
                cur = [b]
            else:
                cur.append(b)
        if cur:
            segs.append(cur)

        # Build JS to clear existing polylines and add new ones per segment
        js_segments = []
        for seg in segs:
            coords_js = ",".join([f"[{lat},{lon}]" for lat, lon in seg])
            js_segments.append(f"L.polyline([{coords_js}], {{color:'red'}}).addTo(map);")
        clear_and_add = (
            "(function(){ if(window._lines) { for(var i=0;i<window._lines.length;i++){map.removeLayer(window._lines[i]);} } window._lines = [];"
            + ";".join([f"var l = {s} window._lines.push(l)" for s in js_segments])
            + "})()"
        )
        if self._page_ready:
            self.view.page().runJavaScript(clear_and_add)
        else:
            self._pending_js.append(clear_and_add)

    def set_ground_station(self, lat: float, lon: float):
        js = f"setGroundStation({lat},{lon});"
        if self._page_ready:
            self.view.page().runJavaScript(js)
        else:
            self._pending_js.append(js)

    def set_satellite(self, lat: float, lon: float):
        js = f"setSatellite({lat},{lon});"
        if self._page_ready:
            self.view.page().runJavaScript(js)
        else:
            self._pending_js.append(js)
