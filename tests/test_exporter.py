import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exporter"))

import grin_exporter


def test_prune_removed_nodes_removes_stale_metric_cache():
    grin_exporter.LAST.clear()
    grin_exporter.LAST.update({
        "grin-gw": {"ok": 1},
        "grinpp-node-2": {"ok": 1},
    })

    grin_exporter.prune_removed_nodes({"grin-gw"})

    assert set(grin_exporter.LAST) == {"grin-gw"}
