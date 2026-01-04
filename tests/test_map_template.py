import pytest

# Skip if PyQt6 isn't available in test environment
pytest.importorskip("PyQt6")
from nast_gs.gui.map_view import MapWindow


def test_html_template_valid():
    tpl = MapWindow.HTML_TEMPLATE
    # Ensure no leftover double-brace artifacts and that JS functions exist
    assert '{{' not in tpl and '}}' not in tpl
    assert 'function setTrack' in tpl
    assert 'function setGroundStation' in tpl
    assert 'function setSatellite' in tpl
