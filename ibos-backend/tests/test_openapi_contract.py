import json
from pathlib import Path

from app.main import app


def test_openapi_paths_snapshot():
    snapshot_path = Path(__file__).parent / "snapshots" / "openapi_paths_snapshot.json"
    expected_paths = json.loads(snapshot_path.read_text(encoding="utf-8"))
    actual_paths = sorted(app.openapi()["paths"].keys())
    assert actual_paths == expected_paths
