"""Stacked curve panels, one per log that recorded the frame.

The grid is assembled from raw axis domains rather than ``make_subplots``, to
match every other builder in ``viz`` returning a plain dict. That means nothing
validates the layout for us: an axis id that no trace names, or two domains that
overlap, produces a figure Plotly renders without complaint and a reader
misreads.

Author: Zhengyu Peng
License: GPL-3.0
"""

import numpy as np
import pytest

from viz.viz import TITLE_BAND_HEIGHT, get_curve_plot, get_curve_plot_grid

TRACES = [
    {"name": "signal", "label": "Signal", "color": "#4c78a8"},
    {"name": "threshold", "label": "Threshold", "color": "#e8734c", "dash": "dash"},
]


def _panel(title, offset=0.0):
    """One log's panel, both traces present."""
    axis = np.arange(8, dtype=float)
    return {
        "title": title,
        "series": {
            "signal": axis + offset,
            "threshold": np.full(8, 4.0 + offset),
        },
        "x_series": {"signal": axis, "threshold": axis},
        "traces": TRACES,
    }


@pytest.fixture
def three_logs():
    return [_panel("log_a"), _panel("log_b", 1.0), _panel("log_c", 2.0)]


class TestDomains:
    """One band per log, top to bottom, never overlapping."""

    @pytest.mark.parametrize("count", [2, 3, 5])
    def test_one_y_axis_per_panel(self, count):
        figure = get_curve_plot_grid([_panel(f"log_{i}") for i in range(count)])
        axes = [k for k in figure["layout"] if k.startswith("yaxis")]
        assert len(axes) == count

    def test_domains_descend_and_do_not_overlap(self, three_logs):
        layout = get_curve_plot_grid(three_logs)["layout"]
        domains = [
            layout["yaxis"]["domain"],
            layout["yaxis2"]["domain"],
            layout["yaxis3"]["domain"],
        ]
        # Panel 0 is drawn at the top, so each domain sits wholly below the last.
        for upper, lower in zip(domains, domains[1:]):
            assert lower[1] <= upper[0]
        for low, high in domains:
            assert 0 <= low < high <= 1

    def test_bands_are_equal_height(self, three_logs):
        layout = get_curve_plot_grid(three_logs)["layout"]
        heights = [
            round(layout[key]["domain"][1] - layout[key]["domain"][0], 6)
            for key in ("yaxis", "yaxis2", "yaxis3")
        ]
        assert len(set(heights)) == 1


class TestAxisWiring:
    """Every trace has to name an axis that exists, or it lands in the wrong band."""

    def test_traces_are_assigned_to_their_panel(self, three_logs):
        figure = get_curve_plot_grid(three_logs)
        assigned = [trace["yaxis"] for trace in figure["data"]]
        # Two traces per panel, in panel order.
        assert assigned == ["y", "y", "y2", "y2", "y3", "y3"]

    def test_every_named_axis_is_defined(self, three_logs):
        figure = get_curve_plot_grid(three_logs)
        defined = {"y"} | {
            f"y{key[len('yaxis'):]}"
            for key in figure["layout"]
            if key.startswith("yaxis") and key != "yaxis"
        }
        assert {trace["yaxis"] for trace in figure["data"]} <= defined

    def test_the_shared_x_axis_is_anchored_to_the_bottom_band(self, three_logs):
        layout = get_curve_plot_grid(three_logs)["layout"]
        # Anchoring anywhere else draws the ticks between two bands.
        assert layout["xaxis"]["anchor"] == "y3"
        assert all(
            trace["xaxis"] == "x" for trace in get_curve_plot_grid(three_logs)["data"]
        )


class TestSharedScales:
    """Stacking is only worth doing if the bands can be read against each other."""

    def test_y_range_is_applied_to_every_panel(self, three_logs):
        layout = get_curve_plot_grid(three_logs, y_range=[-10, 10])["layout"]
        for key in ("yaxis", "yaxis2", "yaxis3"):
            assert layout[key]["range"] == [-10, 10]

    def test_log_scale_is_applied_to_every_panel(self, three_logs):
        layout = get_curve_plot_grid(three_logs, log_y=True)["layout"]
        for key in ("yaxis", "yaxis2", "yaxis3"):
            assert layout[key]["type"] == "log"

    def test_x_range_is_set_once(self, three_logs):
        layout = get_curve_plot_grid(three_logs, x_range=[0, 100])["layout"]
        assert layout["xaxis"]["range"] == [0, 100]
        assert "xaxis2" not in layout


class TestLegend:
    """The panels repeat the same series, so the legend must not."""

    def test_only_the_first_panel_claims_legend_entries(self, three_logs):
        figure = get_curve_plot_grid(three_logs)
        shown = [trace["showlegend"] for trace in figure["data"]]
        assert shown == [True, True, False, False, False, False]

    def test_legend_groups_tie_the_same_series_together(self, three_logs):
        figure = get_curve_plot_grid(three_logs)
        groups = [trace["legendgroup"] for trace in figure["data"]]
        # A click on "Signal" has to toggle it in every band, not just the first.
        assert groups == ["signal", "threshold"] * 3


class TestDegenerateCounts:
    """One log, or none, must not pay for the grid."""

    def test_one_panel_matches_the_single_axes_builder(self):
        panel = _panel("log_a")
        grid = get_curve_plot_grid([panel], x_label="Range", y_label="Level")
        plain = get_curve_plot(
            series=panel["series"],
            x_series=panel["x_series"],
            traces=TRACES,
            x_label="Range",
            y_label="Level",
        )

        assert grid["layout"] == plain["layout"]
        # No subplot wiring leaks into the single-log figure: no second axis, no
        # per-trace axis assignment, no legend suppression.
        assert "yaxis2" not in grid["layout"]
        assert "annotations" not in grid["layout"]
        assert len(grid["data"]) == len(plain["data"])
        for drawn, expected in zip(grid["data"], plain["data"]):
            assert set(drawn) == set(expected)
            np.testing.assert_array_equal(drawn["x"], expected["x"])
            np.testing.assert_array_equal(drawn["y"], expected["y"])
            assert drawn["name"] == expected["name"]

    def test_no_panels_is_the_placeholder(self):
        assert get_curve_plot_grid([])["layout"] == get_curve_plot()["layout"]

    def test_panels_with_no_readable_series_still_produce_a_figure(self):
        empty = [
            {"title": "log_a", "series": {}, "x_series": {}, "traces": TRACES},
            {"title": "log_b", "series": {}, "x_series": {}, "traces": TRACES},
        ]
        figure = get_curve_plot_grid(empty)
        assert figure["data"] == [{"type": "scatter", "x": [], "y": []}]


class TestTitles:
    """Which band is which log."""

    def test_the_top_title_has_margin_to_sit_in(self, three_logs):
        layout = get_curve_plot_grid(three_logs)["layout"]
        # Panel 0's domain reaches 1 and its title sits on that edge, so the
        # text is drawn in the top margin. The single-plot figure's 10px clips
        # it -- that is the bug this guards.
        assert layout["annotations"][0]["y"] == pytest.approx(1.0)
        assert layout["margin"]["t"] >= TITLE_BAND_HEIGHT

    def test_inner_titles_have_a_gap_to_sit_in(self, three_logs):
        layout = get_curve_plot_grid(three_logs)["layout"]
        # Every title below the first is drawn in the gap above its own band,
        # which therefore must not be zero.
        gaps = [
            layout[upper]["domain"][0] - layout[lower]["domain"][1]
            for upper, lower in (("yaxis", "yaxis2"), ("yaxis2", "yaxis3"))
        ]
        assert all(gap > 0.02 for gap in gaps), gaps

    def test_each_panel_is_annotated_with_its_stem(self, three_logs):
        layout = get_curve_plot_grid(three_logs)["layout"]
        assert [a["text"] for a in layout["annotations"]] == [
            "log_a",
            "log_b",
            "log_c",
        ]

    def test_titles_sit_above_their_own_band(self, three_logs):
        layout = get_curve_plot_grid(three_logs)["layout"]
        for annotation, key in zip(
            layout["annotations"], ("yaxis", "yaxis2", "yaxis3")
        ):
            assert annotation["y"] == pytest.approx(layout[key]["domain"][1])
            assert annotation["yanchor"] == "bottom"
