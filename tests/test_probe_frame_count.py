"""Counting a recording's frames without trusting ffmpeg's progress line.

The probe used to scrape ``frame=`` out of stderr. That counter belongs to the
*encoder*, so from ffmpeg 7 a stream copy stopped reporting one and the probe
returned None for every file on every modern build -- silently, because None is
also what "no ffmpeg installed" looks like, and every caller treats it as "leave
the video where it is". The camera panel sat on frame 0 and the HTML export
carried no pictures.

These tests run the parser against captured muxer output rather than against a
live ffmpeg, so they say the same thing whatever version the host happens to
have -- which is the whole property that was missing when the regression landed.

Author: Zhengyu Peng
License: GPL-3.0
"""

import subprocess

import pytest

from dataio import video
from dataio.video import count_packet_lines, probe_frame_count

# What `-f framecrc` writes for a three-packet h264 stream. The header block is
# the part that must not be counted.
FRAMECRC_THREE = """#extradata 0:       46, 0x443c0f73
#software: Lavf61.1.100
#tb 0: 1/15872
#media_type 0: video
#codec_id 0: h264
#dimensions 0: 960x540
#sar 0: 1/1
0,          0,          0,     8000,    43531, 0x203ca0d4
0,       8000,       8000,     8000,    44425, 0x84e0a708
0,      16000,      16000,     8000,    45289, 0x07ac296e
"""

# The ffmpeg 7 stream-copy progress report, for the record: no `frame=` in it
# anywhere, which is exactly why nothing reads stderr any more.
FFMPEG7_COPY_STDERR = (
    "[out#0/null @ 0x3c7bba40] video:1577KiB audio:0KiB subtitle:0KiB\n"
    "size=N/A time=00:00:19.90 bitrate=N/A speed=4.9e+04x\n"
)


class TestCountPacketLines:
    """Header lines are skipped; every other line is one frame."""

    def test_counts_packets_and_skips_the_header(self):
        assert count_packet_lines(FRAMECRC_THREE) == 3

    def test_empty_output_counts_nothing(self):
        assert count_packet_lines("") == 0

    def test_header_only_counts_nothing(self):
        header = "\n".join(FRAMECRC_THREE.splitlines()[:7]) + "\n"
        assert count_packet_lines(header) == 0

    def test_unterminated_final_line_still_counts(self):
        assert count_packet_lines(FRAMECRC_THREE.rstrip("\n")) == 3

    def test_matches_a_line_split_for_a_long_dump(self):
        # The count is done with str.count rather than splitlines, so the two
        # have to be shown to agree -- including across the header boundary.
        dump = FRAMECRC_THREE + "".join(
            f"0,{index * 8000:>12},{index * 8000:>12},8000,44000, 0x0000{index:04x}\n"
            for index in range(3, 5000)
        )
        expected = sum(1 for line in dump.splitlines() if not line.startswith("#"))
        assert count_packet_lines(dump) == expected


class TestProbeFrameCount:
    """The probe reads the muxer's stdout, never the progress line."""

    @pytest.fixture
    def fake_ffmpeg(self, monkeypatch, tmp_path):
        """Point the probe at a real path and a scripted ffmpeg result."""
        clip = tmp_path / "clip.mp4"
        clip.touch()
        monkeypatch.setattr(video, "find_ffmpeg", lambda: "/nonexistent/ffmpeg")

        def _script(stdout="", stderr="", returncode=0, raises=None):
            def _run(command, timeout=None):
                if raises is not None:
                    raise raises
                _run.command = command
                return subprocess.CompletedProcess(
                    command, returncode, stdout=stdout, stderr=stderr
                )

            monkeypatch.setattr(video, "_run_ffmpeg", _run)
            return _run, str(clip)

        return _script

    def test_counts_the_packets_the_muxer_wrote(self, fake_ffmpeg):
        _, clip = fake_ffmpeg(stdout=FRAMECRC_THREE)
        assert probe_frame_count(clip) == 3

    def test_ffmpeg7_stderr_does_not_defeat_it(self, fake_ffmpeg):
        # The exact pairing that used to yield None: a good stream copy whose
        # progress line carries no frame count.
        _, clip = fake_ffmpeg(stdout=FRAMECRC_THREE, stderr=FFMPEG7_COPY_STDERR)
        assert probe_frame_count(clip) == 3

    def test_asks_for_framecrc_over_a_stream_copy(self, fake_ffmpeg):
        run, clip = fake_ffmpeg(stdout=FRAMECRC_THREE)
        probe_frame_count(clip)
        command = run.command
        assert command[command.index("-f") + 1] == "framecrc"
        assert command[command.index("-c") + 1] == "copy"
        # Only the first video stream, so a file with two cameras in it does not
        # count both.
        assert command[command.index("-map") + 1] == "0:v:0"

    def test_failed_command_reads_as_unknown(self, fake_ffmpeg):
        _, clip = fake_ffmpeg(stdout=FRAMECRC_THREE, returncode=183)
        assert probe_frame_count(clip) is None

    def test_no_packets_reads_as_unknown(self, fake_ffmpeg):
        # Zero would divide the seek mapping by nothing; None is the signal the
        # panel understands as "leave the video alone".
        _, clip = fake_ffmpeg(stdout="#media_type 0: video\n")
        assert probe_frame_count(clip) is None

    def test_timeout_reads_as_unknown(self, fake_ffmpeg):
        _, clip = fake_ffmpeg(raises=subprocess.TimeoutExpired("ffmpeg", 1.0))
        assert probe_frame_count(clip) is None

    def test_missing_file_never_runs_ffmpeg(self, monkeypatch, tmp_path):
        monkeypatch.setattr(video, "find_ffmpeg", lambda: "/nonexistent/ffmpeg")
        monkeypatch.setattr(
            video,
            "_run_ffmpeg",
            lambda *a, **k: pytest.fail("ffmpeg ran for a file that is not there"),
        )
        assert probe_frame_count(str(tmp_path / "gone.mp4")) is None

    def test_no_ffmpeg_reads_as_unknown(self, monkeypatch, tmp_path):
        clip = tmp_path / "clip.mp4"
        clip.touch()
        monkeypatch.setattr(video, "find_ffmpeg", lambda: None)
        assert probe_frame_count(str(clip)) is None


class TestAgainstRealFfmpeg:
    """The parsing tests above cannot notice ffmpeg changing its output again.

    This one can: it generates a clip of a known length with whatever ffmpeg is
    installed and asks the probe to count it back. Skipped when there is no
    ffmpeg, which is also the environment where the probe is meant to give up.
    """

    @pytest.fixture
    def clip(self, tmp_path):
        ffmpeg = video.find_ffmpeg()
        if not ffmpeg:
            pytest.skip("no ffmpeg available")

        path = tmp_path / "generated.mp4"
        result = video._run_ffmpeg(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
            + ["-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=2.5"]
            + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
            timeout=120.0,
        )
        if result.returncode != 0 or not path.exists():
            pytest.skip(f"ffmpeg could not build a fixture clip: {result.stderr}")
        return str(path)

    def test_counts_a_clip_of_known_length(self, clip):
        # 10 fps for 2.5 s.
        assert probe_frame_count(clip) == 25
