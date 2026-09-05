"""Manifest schema: v1 upgrade, loading, and persistence.

The promise this file guards is that a v1 ``info.json`` keeps working untouched.
It is upgraded to v2 shape *in memory*, and written back in the shape it already
had -- so a v1 dataset never silently becomes a v2 file, and a v2 dataset never
gets flattened down to the v1 projection. The 3D view saves on every axis change,
which is what makes the second half of that sentence load-bearing rather than
theoretical.

Author: Zhengyu Peng
License: GPL-3.0
"""

import json
import os

import pytest

from dataio.manifest import (
    MANIFEST_VERSION,
    Manifest,
    ManifestError,
    upgrade_to_v2,
)


class TestUpgradeToV2:
    def test_v2_is_returned_untouched(self, v2_manifest):
        # Identity, not equality: an already-current manifest is not rebuilt.
        assert upgrade_to_v2(v2_manifest) is v2_manifest

    def test_v1_table_keys_move_under_table(self, v1_manifest):
        upgraded = upgrade_to_v2(v1_manifest)
        assert upgraded["manifest_version"] == MANIFEST_VERSION
        assert upgraded["table"]["slider"] == "Frame"
        assert upgraded["table"]["x_3d"] == "x"
        assert upgraded["table"]["keys"] == {"speed": {"description": "Speed"}}

    def test_v1_name_is_carried_over(self, v1_manifest):
        assert upgrade_to_v2(v1_manifest)["name"] == "Legacy"

    def test_v1_declares_no_sidecar_blocks(self, v1_manifest):
        upgraded = upgrade_to_v2(v1_manifest)
        # A v1 dataset has no cloud/curve/image; their absence is what makes the
        # accessors return None rather than an empty block.
        for block in ("cloud", "curve", "image"):
            assert block not in upgraded

    def test_unknown_top_level_keys_are_dropped(self):
        upgraded = upgrade_to_v2({"slider": "Frame", "something_else": 1})
        assert "something_else" not in upgraded
        assert "something_else" not in upgraded["table"]

    def test_reference_stays_at_top_level(self):
        # Both schemas keep it top-level, so a v1 dataset can style its
        # reference without being migrated first.
        upgraded = upgrade_to_v2({"slider": "Frame", "reference": {"shape": "mesh"}})
        assert upgraded["reference"] == {"shape": "mesh"}

    def test_absent_reference_is_not_invented(self, v1_manifest):
        assert "reference" not in upgrade_to_v2(v1_manifest)

    def test_empty_manifest_still_gains_a_table_block(self):
        upgraded = upgrade_to_v2({})
        assert upgraded["table"] == {}
        assert upgraded["manifest_version"] == MANIFEST_VERSION


class TestLoad:
    def test_missing_manifest_names_the_directory(self, tmp_path):
        with pytest.raises(ManifestError) as excinfo:
            Manifest.load(str(tmp_path))
        assert "info.json" in str(excinfo.value)

    def test_undecodable_json_raises(self, tmp_path):
        (tmp_path / "info.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(ManifestError):
            Manifest.load(str(tmp_path))

    def test_json_that_is_not_an_object_raises(self, tmp_path):
        # A top-level list decodes fine but has none of the shape below.
        (tmp_path / "info.json").write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ManifestError) as excinfo:
            Manifest.load(str(tmp_path))
        assert "JSON object" in str(excinfo.value)

    def test_v1_file_records_source_version_1(self, make_case, v1_manifest):
        assert Manifest.load(make_case(v1_manifest)).source_version == 1

    def test_v2_file_records_source_version_2(self, make_case, v2_manifest):
        assert Manifest.load(make_case(v2_manifest)).source_version == MANIFEST_VERSION

    def test_v1_file_is_upgraded_in_memory(self, make_case, v1_manifest):
        manifest = Manifest.load(make_case(v1_manifest))
        assert manifest.frame_key == "Frame"
        assert manifest.keys == {"speed": {"description": "Speed"}}


class TestName:
    def test_declared_name_wins(self, make_case, v2_manifest):
        assert Manifest.load(make_case(v2_manifest)).name == "Example"

    def test_falls_back_to_the_directory_name(self, make_case):
        case_dir = make_case({"manifest_version": 2, "table": {}}, name="DriveDay")
        assert Manifest.load(case_dir).name == "DriveDay"

    def test_null_name_falls_back(self, make_case):
        case_dir = make_case(
            {"manifest_version": 2, "name": None, "table": {}}, name="DriveDay"
        )
        assert Manifest.load(case_dir).name == "DriveDay"

    def test_trailing_separator_does_not_blank_the_name(self, make_case):
        case_dir = make_case({"manifest_version": 2, "table": {}}, name="DriveDay")
        # normpath is what stops basename returning "" here.
        assert Manifest(({"table": {}}), case_dir + os.sep).name == "DriveDay"


class TestFrameKey:
    def test_defaults_to_frame(self, make_case):
        assert (
            Manifest.load(make_case({"manifest_version": 2, "table": {}})).frame_key
            == "Frame"
        )

    def test_reads_the_declared_slider(self, make_case):
        case_dir = make_case({"manifest_version": 2, "table": {"slider": "Scan"}})
        assert Manifest.load(case_dir).frame_key == "Scan"


class TestLegacyConfig:
    def test_projects_table_keys_flat(self, make_case, v1_manifest):
        config = Manifest.load(make_case(v1_manifest)).legacy_config()
        assert config["slider"] == "Frame"
        assert config["x_3d"] == "x"
        assert config["keys"] == {"speed": {"description": "Speed"}}

    def test_supplies_the_defaults_callbacks_assume(self, make_case):
        config = Manifest.load(
            make_case({"manifest_version": 2, "table": {}})
        ).legacy_config()
        assert config["keys"] == {}
        assert config["slider"] == "Frame"

    def test_reference_is_carried_verbatim(self, make_case):
        # Not normalized: this projection is also what save() writes over a v1
        # file, and spelling out every default would rewrite the user's manifest.
        block = {"shape": "mesh", "color": "#abcdef"}
        case_dir = make_case({"manifest_version": 2, "table": {}, "reference": block})
        assert Manifest.load(case_dir).legacy_config()["reference"] == block

    def test_absent_reference_is_omitted(self, make_case, v2_manifest):
        assert "reference" not in Manifest.load(make_case(v2_manifest)).legacy_config()


class TestUpdateTableView:
    def test_updates_known_axis_keys(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest))
        manifest.update_table_view({"x_3d": "east", "slider": "Scan"})
        assert manifest.table["x_3d"] == "east"
        assert manifest.table["slider"] == "Scan"

    def test_ignores_unknown_keys(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest))
        manifest.update_table_view({"not_a_field": "x"})
        assert "not_a_field" not in manifest.table

    def test_refuses_to_overwrite_column_metadata(self, make_case, v2_manifest):
        # "keys" is in the v1 key tuple but is column metadata, not an axis
        # selection; a view saving its pickers must not clobber it.
        manifest = Manifest.load(make_case(v2_manifest))
        manifest.update_table_view({"keys": {}})
        assert manifest.keys == {"speed": {"description": "Speed"}}

    def test_creates_the_table_block_when_absent(self, make_case):
        manifest = Manifest.load(make_case({"manifest_version": 2}))
        manifest.update_table_view({"x_3d": "east"})
        assert manifest.table["x_3d"] == "east"


class TestSave:
    def test_v2_save_preserves_every_block(self, make_case, v2_manifest):
        # The regression this whole test module exists for: the 3D view saves on
        # every axis change, and writing the flat v1 projection over a v2 file
        # would destroy cloud, curve and image.
        manifest = Manifest.load(make_case(v2_manifest))
        manifest.update_table_view({"x_3d": "east"})
        path = manifest.save()

        written = json.loads(open(path, encoding="utf-8").read())
        assert written["manifest_version"] == MANIFEST_VERSION
        assert written["cloud"] == {"suffix": ".cloud.h5"}
        assert written["curve"] == {"suffix": ".curve.h5"}
        assert written["image"] == {"suffix": [".mp4", ".avi"]}
        assert written["table"]["x_3d"] == "east"

    def test_v1_save_stays_flat(self, make_case, v1_manifest):
        # A v1 dataset must not be silently upgraded on disk.
        manifest = Manifest.load(make_case(v1_manifest))
        manifest.update_table_view({"x_3d": "east"})
        written = json.loads(open(manifest.save(), encoding="utf-8").read())

        assert "manifest_version" not in written
        assert "table" not in written
        assert written["x_3d"] == "east"
        assert written["slider"] == "Frame"

    def test_round_trips_through_load(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest))
        manifest.update_table_view({"y_3d": "north"})
        manifest.save()

        assert Manifest.load(manifest.case_dir).table["y_3d"] == "north"

    def test_writes_unix_newlines(self, make_case, v2_manifest):
        # Saving on every axis change must not rewrite every line of the user's
        # manifest just because the platform prefers CRLF.
        manifest = Manifest.load(make_case(v2_manifest))
        raw_bytes = open(manifest.save(), "rb").read()
        assert b"\r\n" not in raw_bytes

    def test_returns_the_path_it_wrote(self, make_case, v2_manifest):
        manifest = Manifest.load(make_case(v2_manifest))
        assert manifest.save() == os.path.join(manifest.case_dir, "info.json")


class TestShippedExample:
    """The manifest that ships with the repository has to stay loadable."""

    def test_bundled_nuscenes_case_loads(self):
        case_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "NuScenes",
        )
        manifest = Manifest.load(case_dir)
        assert manifest.source_version == MANIFEST_VERSION
        assert manifest.frame_key
        assert manifest.keys
        assert manifest.cloud is not None
        assert manifest.curve is not None
        assert manifest.image is not None
