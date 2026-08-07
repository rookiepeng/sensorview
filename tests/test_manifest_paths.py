"""Manifest path resolution: log stems and sidecar discovery.

"Adding a log is dropping files in the folder" is the design claim these tests
hold to. Sidecars are found by scanning the case directory and matching
``<stem><suffix>`` or ``<stem>.<id><suffix>``, which puts real weight on two edge
cases that are invisible in the happy path: a generic suffix such as ``.h5`` must
not swallow the cloud sidecar, and one log's stem must not claim another log
whose name merely starts with the same text.

Author: Zhengyu Peng
License: GPL-3.0
"""

import os

import pytest

from dataio.manifest import (
    DEFAULT_REFERENCE_SUFFIX,
    Manifest,
    _suffix_source_id,
    log_stem,
    table_sidecar_suffixes,
)


class TestLogStem:
    def test_strips_the_default_suffix(self):
        assert log_stem("drive_01.parquet") == "drive_01"

    def test_reduces_a_path_to_its_basename(self):
        assert log_stem(os.path.join("some", "where", "drive_01.parquet")) == "drive_01"

    def test_strips_a_custom_suffix(self):
        assert log_stem("drive_01.table.parquet", ".table.parquet") == "drive_01"

    def test_plain_parquet_still_reduces_under_a_custom_suffix(self):
        # A dataset declaring ".table.parquet" may still hold plain .parquet
        # logs; those must not be left with the extension attached.
        assert log_stem("drive_01.parquet", ".table.parquet") == "drive_01"

    def test_matching_is_case_insensitive(self):
        assert log_stem("DRIVE_01.PARQUET") == "DRIVE_01"

    def test_unknown_extension_falls_back_to_splitext(self):
        assert log_stem("drive_01.csv") == "drive_01"

    def test_dots_inside_the_stem_are_kept(self):
        assert log_stem("drive.01.parquet") == "drive.01"


class TestSuffixSourceId:
    @pytest.mark.parametrize(
        "suffix, expected",
        [
            (".sensor_1.h5", "sensor_1"),
            (".curve.h5", "curve"),
            # A bare extension distinguishes nothing, so it takes the default id.
            (".h5", "curve"),
        ],
    )
    def test_names_a_source_after_its_suffix(self, suffix, expected):
        assert _suffix_source_id(suffix) == expected


class TestCloudPaths:
    def test_no_cloud_block_yields_no_path(self, make_case):
        manifest = Manifest.load(make_case({"manifest_version": 2, "table": {}}))
        assert manifest.cloud_path("drive_01") is None
        assert manifest.has_cloud("drive_01") is False

    def test_path_is_built_from_stem_and_suffix(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest))
        assert manifest.cloud_path("drive_01").endswith("drive_01.cloud.h5")

    def test_has_cloud_requires_the_file_to_exist(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest, files=["drive_01.cloud.h5"]))
        assert manifest.has_cloud("drive_01") is True
        assert manifest.has_cloud("drive_02") is False


class TestCurveSources:
    def test_default_suffix_yields_the_curve_source(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest, files=["drive_01.curve.h5"]))
        sources = manifest.curve_sources("drive_01")
        assert [source["id"] for source in sources] == ["curve"]
        assert sources[0]["file"].endswith("drive_01.curve.h5")

    def test_generic_suffix_discovers_named_sensors(self, make_case):
        manifest = Manifest.load(
            make_case(
                {"manifest_version": 2, "table": {}, "curve": {"suffix": ".h5"}},
                files=["drive_01.h5", "drive_01.sensor_2.h5", "drive_01.sensor_6.h5"],
            )
        )
        assert sorted(s["id"] for s in manifest.curve_sources("drive_01")) == [
            "curve",
            "sensor_2",
            "sensor_6",
        ]

    def test_generic_suffix_does_not_swallow_the_cloud_sidecar(self, make_case):
        # ".h5" matches the cloud file too; it is a different kind of file and
        # must stay out of the curve picker.
        manifest = Manifest.load(
            make_case(
                {
                    "manifest_version": 2,
                    "table": {},
                    "cloud": {"suffix": ".cloud.h5"},
                    "curve": {"suffix": ".h5"},
                },
                files=["drive_01.h5", "drive_01.cloud.h5"],
            )
        )
        assert [s["id"] for s in manifest.curve_sources("drive_01")] == ["curve"]

    def test_an_explicitly_declared_suffix_is_never_reserved(self, make_case):
        # Declaring ".cloud.h5" as the curve suffix means exactly that, even
        # though it is also the cloud default.
        manifest = Manifest.load(
            make_case(
                {
                    "manifest_version": 2,
                    "table": {},
                    "cloud": {"suffix": ".cloud.h5"},
                    "curve": {"suffix": ".cloud.h5"},
                },
                files=["drive_01.cloud.h5"],
            )
        )
        assert [s["id"] for s in manifest.curve_sources("drive_01")] == ["cloud"]

    def test_declared_list_preserves_listing_order(self, make_case):
        manifest = Manifest.load(
            make_case(
                {
                    "manifest_version": 2,
                    "table": {},
                    "curve": {"suffix": [".sensor_2.h5", ".sensor_1.h5"]},
                },
                files=["drive_01.sensor_1.h5", "drive_01.sensor_2.h5"],
            )
        )
        # Declared order, not alphabetical: that is the reason to list them.
        assert [s["id"] for s in manifest.curve_sources("drive_01")] == [
            "sensor_2",
            "sensor_1",
        ]

    def test_a_file_matching_two_suffixes_is_listed_once(self, make_case):
        manifest = Manifest.load(
            make_case(
                {
                    "manifest_version": 2,
                    "table": {},
                    "curve": {"suffix": [".curve.h5", ".h5"]},
                },
                files=["drive_01.curve.h5"],
            )
        )
        assert len(manifest.curve_sources("drive_01")) == 1

    def test_a_longer_stem_is_not_claimed(self, make_case, v2_manifest):
        # drive_011 is a different log that merely starts with drive_01.
        manifest = Manifest.load(make_case(v2_manifest, files=["drive_011.curve.h5"]))
        assert manifest.curve_sources("drive_01") == []

    def test_label_is_humanised_from_the_id(self, make_case):
        manifest = Manifest.load(
            make_case(
                {"manifest_version": 2, "table": {}, "curve": {"suffix": ".h5"}},
                files=["drive_01.rear_left.h5"],
            )
        )
        assert manifest.curve_sources("drive_01")[0]["label"] == "Rear Left"

    def test_no_curve_block_yields_nothing(self, make_case):
        manifest = Manifest.load(make_case({"manifest_version": 2, "table": {}}))
        assert manifest.curve_sources("drive_01") == []

    def test_empty_stem_yields_nothing(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest, files=["drive_01.curve.h5"]))
        assert manifest.curve_sources("") == []

    def test_unreadable_case_directory_yields_nothing(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest))
        manifest.case_dir = os.path.join(manifest.case_dir, "gone")
        assert manifest.curve_sources("drive_01") == []


class TestCurvePath:
    @pytest.fixture
    def manifest(self, make_case):
        return Manifest.load(
            make_case(
                {"manifest_version": 2, "table": {}, "curve": {"suffix": ".h5"}},
                files=["drive_01.h5", "drive_01.sensor_2.h5"],
            )
        )

    def test_defaults_to_the_first_source(self, manifest):
        assert manifest.curve_path("drive_01").endswith("drive_01.h5")

    def test_selects_a_named_source(self, manifest):
        assert manifest.curve_path("drive_01", "sensor_2").endswith(
            "drive_01.sensor_2.h5"
        )

    def test_unknown_source_yields_none(self, manifest):
        assert manifest.curve_path("drive_01", "sensor_9") is None

    def test_log_without_curves_yields_none(self, manifest):
        assert manifest.curve_path("drive_02") is None

    def test_has_curve_tracks_discovery(self, manifest):
        assert manifest.has_curve("drive_01") is True
        assert manifest.has_curve("drive_02") is False


class TestImageStreams:
    def test_bare_stem_is_the_default_stream(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest, files=["drive_01.mp4"]))
        streams = manifest.image_streams("drive_01")
        assert [(s["id"], s["label"]) for s in streams] == [("image", "Image")]

    def test_named_streams_are_discovered(self, make_case, v2_manifest):
        manifest = Manifest.load(
            make_case(v2_manifest, files=["drive_01.mp4", "drive_01.rear_left.mp4"])
        )
        streams = manifest.image_streams("drive_01")
        assert [(s["id"], s["label"]) for s in streams] == [
            ("image", "Image"),
            ("rear_left", "Rear Left"),
        ]

    def test_default_stream_sorts_first(self, make_case, v2_manifest):
        # "image" sorts after "back" alphabetically, so this ordering is the
        # explicit sort key rather than a coincidence.
        manifest = Manifest.load(
            make_case(v2_manifest, files=["drive_01.back.mp4", "drive_01.mp4"])
        )
        assert [s["id"] for s in manifest.image_streams("drive_01")] == [
            "image",
            "back",
        ]

    def test_mp4_wins_over_avi_for_the_same_stream(self, make_case, v2_manifest):
        # Serving the mp4 skips a transcode the avi would have required.
        manifest = Manifest.load(
            make_case(v2_manifest, files=["drive_01.avi", "drive_01.mp4"])
        )
        streams = manifest.image_streams("drive_01")
        assert len(streams) == 1
        assert streams[0]["file"].endswith(".mp4")

    def test_avi_is_still_served_when_alone(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest, files=["drive_01.avi"]))
        assert manifest.image_streams("drive_01")[0]["file"].endswith(".avi")

    def test_a_longer_stem_is_not_claimed(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest, files=["drive_011.mp4"]))
        assert manifest.image_streams("drive_01") == []

    def test_no_image_block_yields_nothing(self, make_case):
        manifest = Manifest.load(make_case({"manifest_version": 2, "table": {}}))
        assert manifest.image_streams("drive_01") == []

    def test_has_image_tracks_discovery(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest, files=["drive_01.mp4"]))
        assert manifest.has_image("drive_01") is True
        assert manifest.has_image("drive_02") is False


class TestTableSidecarSuffixes:
    def test_defaults_apply_without_a_manifest(self, tmp_path):
        # The picker must still refuse to offer a reference sidecar as a log,
        # even in a folder it cannot read a manifest from.
        assert table_sidecar_suffixes(str(tmp_path)) == [DEFAULT_REFERENCE_SUFFIX]

    def test_custom_reference_suffix_is_included(self, make_case):
        case_dir = make_case(
            {
                "manifest_version": 2,
                "table": {},
                "reference": {"suffix": ".pose.parquet"},
            }
        )
        # Sorted, so the declared suffix can land either side of the default.
        assert table_sidecar_suffixes(case_dir) == [
            ".pose.parquet",
            DEFAULT_REFERENCE_SUFFIX,
        ]

    def test_results_are_deduplicated_and_lowercased(self, make_case):
        case_dir = make_case(
            {
                "manifest_version": 2,
                "table": {},
                "reference": {"suffix": ".REFERENCE.PARQUET"},
            }
        )
        assert table_sidecar_suffixes(case_dir) == [DEFAULT_REFERENCE_SUFFIX]
