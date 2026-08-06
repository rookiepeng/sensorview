nuScenes mini — sample dataset built from real automotive sensor data
====================================================================

PROVENANCE — READ THIS FIRST
----------------------------
Every number in this case folder is derived from the nuScenes v1.0-mini split
(Motional / nuTonomy). Nothing is synthetic. Nothing was invented to fill a
panel: where a sensor recorded nothing, the curve carries NaN and draws a gap.

  Source    : https://www.nuscenes.org/nuscenes  (v1.0-mini, 4 GB)
  License   : CC BY-NC-SA 4.0 — NON-COMMERCIAL. This folder is a derivative
              work and carries the same terms, which are NOT the GPL-3.0 the
              rest of this repository is under. It is deliberately left out of
              git (data/* is ignored); rebuild it locally rather than
              committing it.
  Citation  : Caesar et al., "nuScenes: A multimodal dataset for autonomous
              driving", CVPR 2020.

Five scenes, five logs
----------------------
  frames    time (s)       log           where / what
  ------    ---------      -----------   ------------------------------------
    0- 38    0.0- 19.2     scene_0061    singapore-onenorth, day. "Parked
                                         truck, construction, intersection,
                                         turn left, following a van" — the
                                         turn sweeps the heading through 98
                                         degrees, so the host mesh visibly
                                         rotates while scrubbing.
   39- 78   19.7- 39.1     scene_0103    boston-seaport, day. "Many peds
                                         right, wait for turning car, long
                                         bike rack left, cyclist."
   79-118   39.6- 59.2     scene_0796    singapore-queenstown, day. "Scooter,
                                         peds, bus, truck, cross
                                         intersection, car overtaking us" —
                                         the overtake stands off the zero
                                         line in the compensated range rate.
  119-159   59.7- 79.6     scene_1077    singapore-hollandvillage, night.
                                         "Big street, bus stop, high speed,
                                         construction vehicle" — highway
                                         speeds, so the gap between measured
                                         and compensated range rate is large.
  160-199   80.1- 99.6     scene_1094    singapore-hollandvillage, night
                                         after rain. "Many peds, PMD, ped
                                         with bag, jaywalker, truck, scooter."

Frames are nuScenes *keyframes* (samples) at 2 Hz: the one instant where all
twelve sensors are synchronised.

Frame ids run **end to end across the whole case folder**, 0 to 199, rather
than each log restarting at zero — and so does Time, 0 to 99.6 s. The logs
read as consecutive segments of one recording, and a frame id belongs to
exactly one of them.

That is deliberate, and it is worth keeping in any dataset built this way. Per-
log ids that all start at zero collide across logs, and anything downstream
that caches per frame id — the browser's point-cloud cache did exactly this —
can serve one log's data while another is selected, with nothing in the view
saying so. Disjoint ids turn that class of bug into something you see
immediately instead of something you squint at.

The frame column stays the slider key either way: SensorView derives the frame
index from the table rather than assuming it starts at zero, so the slider
reads "Index: 5 (Frame: 84)" and the sidecars are addressed by the real id.

Coordinates
-----------
Everything is in a world frame, recentred on the scene's first ego position:

    X  east (m)      Y  north (m)      Z  up (m)

so the host vehicle travels *through* a fixed world rather than sitting at the
origin while the world slides past. That is what makes the decay slider draw
trails, the lidar backdrop accumulate into a map, and the reference pose worth
carrying. Yaw is measured from +X, which is where the host mesh points at
yaw = 0.

Each sensor is placed with the ego pose recorded at *its own* timestamp, not
the lidar's: the radars fire 10-30 ms either side of the keyframe, which is
worth up to 0.3 m at speed.

What each file holds
--------------------
  <log>.parquet             table  — 5 radars' detections, ~19k rows/log
  <log>.cloud.h5            cloud  — LIDAR_TOP, decimated to ~10k points/frame
  <log>.radar_front.h5      curve  — one file per radar, five in all
  <log>.radar_front_left.h5
  <log>.radar_front_right.h5
  <log>.radar_back_left.h5
  <log>.radar_back_right.h5
  <log>.lidar.h5            curve  — a sixth source, with its own plot list
  <log>.mp4                 image  — CAM_FRONT
  <log>.back.mp4            image  — CAM_BACK
  <log>.reference.parquet   ego pose per frame: position + yaw/pitch/roll

Table columns
-------------
Positions and kinematics are computed per detection; the five categorical
columns are the radar's own status words, decoded to their documented labels.

  X / Y / Z               world position (m)
  Range / Azimuth         relative to the ego frame (m, deg)
  RCS                     radar cross section (dBsm)
  Range_Rate              range rate as measured (m/s)
  Range_Rate_Comp         the same, compensated for ego motion (m/s)
  Speed                   |compensated velocity| (m/s)
  Sensor                  which of the five radars
  Dyn_Prop                moving / stationary / oncoming / crossing / ...
  Ambig_State             unambiguous / ambiguous / staggered ramp / ...
  False_Alarm_Prob        the radar's own confidence class (<25% ... <=100%)
  Valid                   valid, or the invalid_state code that rejected it

About half of nuScenes' radar detections carry a non-zero invalid_state. They
are kept rather than dropped, because filtering them out is exactly the kind of
thing the filter rail is for. Detections with no position at all — a handful
per log — are dropped, since nothing can place, bin, or filter them.

Curves (derived, not recorded)
------------------------------
nuScenes ships detections, not the range profiles behind them, so the 1D curves
are computed from the detections in each frame. They are real measurements,
binned — not a model of what a radar might have seen.

  Range Profile        peak and mean RCS per 2 m range bin. Bins with no
                       detection are NaN and draw as gaps, which is most of
                       them: a radar frame is ~125 detections over 130 m.

  Range Rate           measured vs. ego-motion compensated range rate per bin,
                       against a flat zero line. Compensation is the whole
                       story here: measured range rates of stationary objects
                       track the host's own speed, and collapse onto zero once
                       compensated. What is left off the line is genuinely
                       moving.

  Lidar Range Density  returns per 2 m bin, all and above 0.5 m. The split is
                       roughly ground vs. everything else. Binning starts at
                       2 m; nearer than that is the ego's own bodywork.

  Lidar Height Profile returns per 0.25 m bin of height above the ego ground
                       plane. Peaks hard at 0 m — that is the road.

Each radar gets its own range grid, sized to the furthest that sensor saw in
that log — 130 m for one, 254 m for another in the same scene. This is why the
curve panel keeps sources separate instead of merging them into shared axes.

Rebuilding
----------
build_nuscenes_case.py, in this folder, is what produced everything here. It
reads the nuScenes JSON tables and PCD/bin point clouds directly -- no devkit
install, only numpy, pandas, pyarrow, h5py, and the ffmpeg that imageio-ffmpeg
already bundles for the camera transcode.

  curl -O https://www.nuscenes.org/data/v1.0-mini.tgz
  tar -xzf v1.0-mini.tgz -C /path/to/nuscenes
  python build_nuscenes_case.py --root /path/to/nuscenes --out data/NuScenes \
      --scenes scene-0061 scene-0103 scene-0796 scene-1077 scene-1094

Any of the ten mini scenes can be named instead; each becomes another log in
the same case folder, with no manifest edit. Scenes are numbered in sorted
order regardless of the order given, so the running frame count matches the
order the file picker lists them in — which is what makes the logs read as one
continuous recording rather than a shuffled one.

The whole folder is rewritten on every run, info.json included, so hand edits
to the manifest belong in the script.
