from __future__ import annotations

from src.selector.choose_dataset import MetricsRow


def test_weighted_scoring_ranks_python_over_node():
    # Given metrics similar to the example
    py = MetricsRow(
        crawler="python",
        coverage=0.945,
        phone_fill=0.78,
        social_fill=0.65,
        address_fill=0.42,
    )
    node = MetricsRow(
        crawler="node",
        coverage=0.938,
        phone_fill=0.75,
        social_fill=0.68,
        address_fill=0.38,
    )

    # Our selector uses: score = 0.6 * coverage + 0.4 * quality
    # where quality = average(phone/social/address)
    def score(m: MetricsRow, cw=0.6, qw=0.4) -> float:
        return cw * m.coverage + qw * m.quality

    py_score = score(py)
    node_score = score(node)

    assert py.quality == (0.78 + 0.65 + 0.42) / 3
    assert node.quality == (0.75 + 0.68 + 0.38) / 3
    assert py_score > node_score, f"expected python to win; {py_score=}, {node_score=}"
