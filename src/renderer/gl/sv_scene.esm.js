// The GL scene: the one object the rest of the app talks to.
//
// `create(host)` returns the whole surface of the renderer. Nothing outside
// `src/renderer/gl/` imports three.js, and nothing in here knows that React
// exists -- the seam is a host element in and a handle out, which is what lets
// the scene keep its own render loop instead of being redrawn by a component.
//
// Two decisions shape the rest:
//
// Rendering is on demand. There is no free-running animation loop: a frame is
// drawn when something changes it, and otherwise not at all. A loop that always spins would compete with the
// dock's charts and a video element for the same main thread, and cost battery
// in a window that is usually sitting still.
//
// Geometry is pooled, in `sv_points.esm.js`. Playback steps several frames a
// second, so buffers are refilled rather than reallocated.

import {
  AmbientLight,
  DirectionalLight,
  Group,
  PerspectiveCamera,
  Scene,
  Vector3,
  WebGLRenderer,
} from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { Axes } from "./sv_axes.esm.js";
import { Hud } from "./sv_hud.esm.js";
import { LineLayer, MeshLayer, PointLayer } from "./sv_points.esm.js";
import { Picker } from "./sv_pick.esm.js";
import { categoryColor, lutTexture, setPalette } from "./sv_color.esm.js";

// Plotly draws a scatter3d marker noticeably fatter than its nominal `size`.
// This is the factor that makes a point the same weight in both renderers, so
// toggling between them does not change how dense the cloud looks. Tuned by
// eye against the Plotly view; it is a presentation constant, not a unit.
const SIZE_SCALE = 2.0;

// Matches Plotly's default 3D camera direction, so the toggle does not swing
// the view. Plotly's eye is (1.25, 1.25, 1.25) in its own normalized space.
const EYE = new Vector3(1.25, 1.25, 1.25).normalize();

const FOV = 50;

/** How wide the camera may be opened to fit a box into a narrow gap. */
const FOV_MAX = 74;

/** The room `applyLayout` leaves around the box when it sets the distance. */
const FIT = 1.25;

/** How much of the clear gap the box may fill, once it is being fitted to it. */
const GAP_FILL = 0.88;

/**
 * Build the renderer inside a host element.
 *
 * @param {HTMLElement} host Element to fill; the canvas and the label layer
 *     are created inside it. Must be positioned, since the labels are
 *     absolutely placed over the canvas.
 * @param {Object} [options] `software` when the WebGL context turned out to be
 *     a software rasteriser, which the stats readout surfaces; `onPick` to be
 *     told which point was clicked.
 * @returns {Object} The scene handle.
 */
export function create(host, options = {}) {
  const state = {
    mounted: false,
    active: true,
    software: options.software === true,
    frame: null,
    colormap: "Portland",
    paused: true,
    dirty: true,
    looping: false,
    hiddenKeys: new Set(),
    fps: 0,
    lastDraw: 0,
  };

  let renderer = null;
  let scene = null;
  let camera = null;
  let controls = null;
  let root = null;
  let axes = null;
  let hud = null;
  let picker = null;
  let cloudLayer = null;
  let meshLayer = null;
  let lineLayer = null;
  let refMarker = null;
  let canvas = null;
  let stage = null;
  let owned = [];

  // slots[0] is the live frame; slots[i>0] are decay trails, oldest last.
  const slots = [];

  /* ---------------------------------------------------------------- render */

  function requestRender() {
    state.dirty = true;
    if (!state.looping) {
      loop();
    }
  }

  function loop() {
    state.looping = true;
    requestAnimationFrame(() => {
      if (!state.mounted || !state.active) {
        state.looping = false;
        return;
      }

      const moving = controls.update();
      if (state.dirty || moving) {
        // The height is what the grid's spacing is chosen against: the step
        // is picked to cover a number of pixels, not a number of metres.
        if (axes.update(camera, root, state.height || stage.clientHeight, controls.target)) {
          // Lines or labels changed; nothing else to do, it is drawn below.
        }
        renderer.render(scene, camera);

        const now = performance.now();
        if (state.lastDraw) {
          const gap = now - state.lastDraw;
          // A gap longer than a few frames means the scene was idle, not slow;
          // starting the mean over avoids averaging across the pause.
          state.fps = gap > 250 ? 0 : state.fps * 0.8 + (1000 / Math.max(gap, 1)) * 0.2;
        }
        state.lastDraw = now;
        reportStats();
      }

      state.dirty = false;
      if (moving) {
        loop();
      } else {
        state.looping = false;
      }
    });
  }

  function reportStats() {
    if (!hud) {
      return;
    }
    let points = 0;
    slots.forEach((slot) => slot.layers.forEach((layer) => (points += layer.count)));
    if (cloudLayer) {
      points += cloudLayer.count;
    }
    hud.setStats({
      fps: state.fps,
      points,
      calls: renderer.info.render.calls,
      software: state.software === true,
    });
  }

  /* ----------------------------------------------------------------- mount */

  /**
   * Build the scene inside a host element.
   *
   * The host is handed in rather than looked up. Under Dash the DOM arrived
   * after this module ran, so mounting meant polling for three ids with a
   * MutationObserver; a React ref is synchronous, so the caller simply has the
   * element. The canvas and the label layer are created here rather than
   * written in markup, because they are this module's business and nothing
   * else should be able to restyle them by accident.
   *
   * @param {HTMLElement} host Element to fill. Must be positioned.
   * @returns {boolean} Whether the scene mounted.
   */
  function mount(host) {
    if (!host) {
      return false;
    }
    stage = host;

    canvas = document.createElement("canvas");
    canvas.id = "gl-canvas";
    host.append(canvas);
    // The panel splitters take presses up to a few pixels either side of the
    // handle, from a document-level capture listener that marks the press as
    // handled but lets it travel on. Without this the canvas beside a handle
    // got the same press, and a column resize turned into an orbit as well.
    // Registered first and in the capture phase, so it runs before the
    // orbit controls and the picker see the event.
    canvas.addEventListener(
      "pointerdown",
      (event) => {
        if (event.defaultPrevented) {
          event.stopImmediatePropagation();
        }
      },
      true,
    );
    // Remembered so dispose can take back exactly what mount added. React's
    // StrictMode mounts twice in development, so a dispose that misses one of
    // these leaves an orphan behind -- and `getElementById` then answers with
    // the dead one.
    owned = [canvas];

    renderer = new WebGLRenderer({
      canvas,
      antialias: true,
      // Transparent, so `--sv-bg` on the body is the scene background and the
      // theme reaches it without any GL work at all.
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    scene = new Scene();
    camera = new PerspectiveCamera(FOV, 1, 0.01, 2000);
    // The data has z up, as automotive frames do, and so does the Plotly scene.
    camera.up.set(0, 0, 1);

    controls = new OrbitControls(camera, canvas);
    // No damping. At 0.08 the camera moved eight per cent of the way to the
    // pointer per frame, so a drag was a dozen frames behind the hand and
    // kept gliding after it let go -- and the loop went on drawing for the
    // tail of every orbit. That reads as the app being slow rather than as
    // smoothness. movens-link's view, which is the one that feels
    // immediate, leaves OrbitControls' damping off; so does this.
    controls.enableDamping = false;
    controls.screenSpacePanning = true;
    controls.addEventListener("change", requestRender);

    root = new Group();
    scene.add(root);

    // Enough light for the reference mesh to read as a body. Parented to the
    // camera so the shading does not swing as the scene is orbited.
    scene.add(new AmbientLight(0xffffff, 1.6));
    const key = new DirectionalLight(0xffffff, 1.2);
    key.position.set(1, 1, 2);
    camera.add(key);
    scene.add(camera);

    axes = new Axes();
    // The labels were DOM and could be counted; as geometry they cannot, so
    // the count is published here. `smoke.ts` waits on it to know the axes
    // have drawn, which is the check that caught a scene that came up with
    // a floor and no numbers on it.
    axes.onLabels = (count) => stage.setAttribute("data-tick-labels", String(count));
    root.add(axes.group);

    cloudLayer = new PointLayer("categorical", false);
    root.add(cloudLayer.points);

    meshLayer = new MeshLayer();
    root.add(meshLayer.mesh);
    lineLayer = new LineLayer();
    root.add(lineLayer.lines);
    refMarker = new PointLayer("categorical", false);
    root.add(refMarker.points);

    hud = new Hud(stage, {
      onPreset: setPreset,
      onToggleGroup: (hidden) => {
        state.hiddenKeys = hidden;
        applyVisibility();
        requestRender();
      },
    });

    picker = new Picker({
      renderer,
      camera,
      canvas,
      hud,
      getFrame: () => state.frame,
      getSlots: () => slots,
      isPaused: () => state.paused,
      requestRender,
      onPick: options.onPick,
    });

    state.mounted = true;
    resize();
    applyTheme(document.documentElement.getAttribute("data-bs-theme") !== "light");
    return true;
  }

  /* -------------------------------------------------------------- geometry */

  /**
   * Place the data box in world space.
   *
   * `get_scatter3d_layout` hands over an aspect ratio already: the relative
   * edge lengths the box should be drawn with. Scaling by it and centring on
   * the origin reproduces Plotly's `aspectmode: "manual"` exactly, and leaves
   * the camera orbiting something of a predictable size whatever the data's
   * units are.
   */
  function applyLayout(layout) {
    const { ranges, aspect } = layout;
    const span = {
      x: ranges.x[1] - ranges.x[0],
      y: ranges.y[1] - ranges.y[0],
      z: ranges.z[1] - ranges.z[0],
    };

    const scale = {
      x: span.x > 0 ? aspect.x / span.x : 1,
      y: span.y > 0 ? aspect.y / span.y : 1,
      z: span.z > 0 ? aspect.z / span.z : 1,
    };

    root.scale.set(scale.x, scale.y, scale.z);
    root.position.set(
      -((ranges.x[0] + ranges.x[1]) / 2) * scale.x,
      -((ranges.y[0] + ranges.y[1]) / 2) * scale.y,
      -((ranges.z[0] + ranges.z[1]) / 2) * scale.z
    );

    axes.setRanges(ranges, layout.labels);
    picker.syncTransform(root);

    const diagonal = Math.hypot(aspect.x, aspect.y, aspect.z);
    state.radius = diagonal / 2;
    state.distance = (state.radius / Math.tan((FOV / 2) * (Math.PI / 180))) * FIT;

    if (!state.framed) {
      setPreset("iso");
      state.framed = true;
    }
  }

  /**
   * Where the data on screen is, and how far it reaches.
   *
   * The box is the filter sliders' extent over the whole log, and for a radar
   * that is set by a handful of far detections: hundreds of metres across,
   * with the frame's points in one corner of it. Framing the box put the
   * camera's target in empty space, so the data sat off to one side and slid
   * away on every zoom. This is the live frame's own extent -- its points and
   * the reference -- which is what a preset is asked to show.
   *
   * @returns {{centre: Vector3, radius: number} | null} In data units, or null
   *     when the frame has nothing in it.
   */
  function dataFocus() {
    const frame = state.frame;
    if (!frame) {
      return null;
    }
    const lo = [Infinity, Infinity, Infinity];
    const hi = [-Infinity, -Infinity, -Infinity];
    const take = (position, count) => {
      if (!position) {
        return;
      }
      const n = Math.min(count ?? position.length / 3, position.length / 3);
      for (let i = 0; i < n; i++) {
        for (let k = 0; k < 3; k++) {
          const v = position[i * 3 + k];
          if (Number.isFinite(v)) {
            if (v < lo[k]) lo[k] = v;
            if (v > hi[k]) hi[k] = v;
          }
        }
      }
    };
    (frame.groups || []).forEach((group) => take(group.position, group.count));
    if (frame.ref) {
      take(frame.ref.mesh?.position);
      take(frame.ref.marker?.position, frame.ref.marker?.count);
    }
    if (!(lo[0] <= hi[0])) {
      return null;
    }
    const centre = new Vector3((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2);
    const radius = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2;
    return { centre, radius };
  }

  function setPreset(id) {
    if (!state.distance) {
      return;
    }
    const tan = Math.tan((FOV / 2) * (Math.PI / 180));
    const target = new Vector3(0, 0, 0);
    let d = state.distance;
    const focus = dataFocus();
    if (focus) {
      root.updateMatrixWorld();
      target.copy(root.localToWorld(focus.centre.clone()));
      // Fitted the way the box is, so the gap fitting in `frame` holds for
      // it too. Floored so one point, or a frame of points stacked on one
      // spot, does not put the camera inside them.
      const reach = Math.max(focus.radius * root.scale.x, state.radius * 0.02, 1e-3);
      d = (reach / tan) * FIT;
      axes.setDataRadius(Math.max(focus.radius, 1e-6));
    }
    const directions = {
      iso: EYE.clone(),
      top: new Vector3(0, 0, 1),
      front: new Vector3(0, -1, 0),
      side: new Vector3(-1, 0, 0),
    };
    const direction = (directions[id] || directions.iso).clone().normalize();

    controls.target.copy(target);
    camera.position.copy(direction.multiplyScalar(d).add(target));
    // A camera looking straight down a pole has an undefined roll; nudging the
    // up vector off the view axis is what keeps the top view from flipping.
    camera.up.set(0, 0, 1);
    if (id === "top") {
      camera.up.set(0, 1, 0);
    }
    camera.lookAt(controls.target);
    controls.update();
    requestRender();
  }

  /**
   * Make sure slot `s` has at least `n` point layers in the given colour mode.
   */
  function ensureSlot(s, n, mode, pickable) {
    while (slots.length <= s) {
      slots.push({ layers: [], mode: null });
    }
    const slot = slots[s];

    if (slot.mode !== mode) {
      slot.layers.forEach((layer) => {
        root.remove(layer.points);
        if (layer.pickPoints) {
          root.remove(layer.pickPoints);
        }
        layer.dispose();
      });
      slot.layers = [];
      slot.mode = mode;
    }

    while (slot.layers.length < n) {
      const layer = new PointLayer(mode, pickable);
      root.add(layer.points);
      if (layer.pickPoints) {
        // Into the picker's own root, which mirrors the display root's
        // transform -- the geometry is shared, the placement must be too.
        picker.root.add(layer.pickPoints);
      }
      slot.layers.push(layer);
    }

    slot.layers.forEach((layer, i) => {
      if (i >= n) {
        // Zero the count too: `applyVisibility` shows any layer whose count
        // is above zero, so a stale one would bring back the last frame's
        // points -- every point, when a filter leaves nothing to draw.
        layer.count = 0;
        layer.points.visible = false;
        if (layer.pickPoints) {
          layer.pickPoints.visible = false;
        }
      }
    });

    return slot;
  }

  function applyVisibility() {
    const hidden = state.hiddenKeys;

    if (slots[0]) {
      slots[0].layers.forEach((layer, index) => {
        layer.points.visible = layer.count > 0 && !hidden.has(`group:${index}`);
        if (layer.pickPoints) {
          layer.pickPoints.visible = layer.points.visible;
        }
      });
    }
    // The trail belongs to the same groups as the live frame, so a group
    // switched off disappears from its own history too.
    for (let s = 1; s < slots.length; s++) {
      slots[s].layers.forEach((layer, index) => {
        layer.points.visible = layer.count > 0 && !hidden.has(`group:${index}`);
      });
    }

    // Read from `hasData` rather than from the object's own `visible`, which
    // would latch off the first time the reference is toggled away.
    const refOn = !hidden.has("ref");
    meshLayer.mesh.visible = meshLayer.hasData && refOn;
    lineLayer.lines.visible = lineLayer.hasData && refOn;
    refMarker.points.visible = refMarker.count > 0 && refOn;

    if (cloudLayer) {
      cloudLayer.points.visible = cloudLayer.count > 0 && !hidden.has("cloud");
    }
  }

  /* ------------------------------------------------------------------- api */

  /**
   * Draw a frame.
   *
   * Takes either form the buffer can hold. `glBundles` is the packed binary
   * frame and is preferred; `bundles` is the Plotly figure the JSON buffer
   * carries, and is what a frame the packer could not write falls back to.
   * Both decode to the same shape, so nothing below here knows the difference.
   *
   * @param {Object} payload `glBundles` and/or `bundles` (newest first, one
   *     per decay step), `index`, `cloudBuffer` or `cloudTrace`, `colormap`,
   *     `sizeVary`, `paused`.
   */
  function setFrame(payload) {
    if (!state.mounted || !payload || !payload.frames || !payload.frames.length) {
      return;
    }

    // Kept so a control that changes how the frame is drawn -- size-vary, a
    // context restore -- can redraw it without the caller having to rebuild.
    state.payload = payload;

    state.colormap = payload.colormap || state.colormap;
    state.paused = payload.paused !== false;

    // Already in the shape the scene wants. There used to be two decoders here
    // -- one for Plotly trace dicts off the wire, one for a packed binary
    // frame -- because the data crossed a network boundary as JSON and the
    // hover text had to be kept out of it. The caller builds this directly
    // now, so the frame has one representation instead of four.
    const frames = payload.frames;
    const live = frames[0];
    state.frame = live;

    applyLayout(live.layout);

    const lut = live.cType === "numerical" ? lutTexture(state.colormap) : null;
    const pixelRatio = renderer.getPixelRatio();

    // Before the uploads: the pick colour is a vertex attribute, so it has to
    // exist on the group by the time its buffers go up.
    picker.prepare(live);

    frames.forEach((frame, s) => {
      // The ramp `retrieveBuffer` applies to the Plotly figure, reproduced so
      // the trail fades identically in both renderers.
      const opacity = frames.length > 1 ? 1 - (0.8 * s) / (frames.length - 1) : 1;
      const slot = ensureSlot(s, frame.groups.length, frame.cType, s === 0);

      frame.groups.forEach((group, index) => {
        const layer = slot.layers[index];
        // Size-vary widens the earlier groups, exactly as the Plotly path does
        // clientside -- the buffered figure is always built without it.
        const offset = payload.sizeVary ? frame.groups.length - 1 - index : 0;
        layer.upload(group, (frame.baseSize || 3) + offset);
        layer.setUniforms({
          opacity,
          pixelRatio,
          sizeScale: SIZE_SCALE,
          cRange: frame.cRange,
          lut,
          // A categorical group with no colour of its own takes the one the
          // legend already shows for it. Both read `categoryColor` at the same
          // index, so the swatch and the points cannot drift apart -- which
          // they did while this fell through to grey.
          rgb:
            group.rgb ||
            (frame.cType === "categorical" ? categoryColor(index) : [160, 160, 160]),
        });
      });
    });

    for (let s = frames.length; s < slots.length; s++) {
      slots[s].layers.forEach((layer) => {
        layer.points.visible = false;
        layer.count = 0;
      });
    }

    meshLayer.upload(live.ref.mesh);
    lineLayer.upload(live.ref.edges);
    if (live.ref.marker) {
      refMarker.upload(
        { position: live.ref.marker.position, count: live.ref.marker.count },
        live.ref.marker.size
      );
      refMarker.setUniforms({
        opacity: 1,
        pixelRatio,
        sizeScale: SIZE_SCALE,
        rgb: live.ref.marker.rgb,
      });
    } else {
      refMarker.upload({ position: new Float32Array(0), count: 0 }, 1);
    }

    if (live.cloud) {
      cloudLayer.upload(
        { position: live.cloud.position, count: live.cloud.count },
        live.cloud.size
      );
      cloudLayer.setUniforms({
        opacity: live.cloud.opacity,
        pixelRatio,
        sizeScale: SIZE_SCALE,
        rgb: live.cloud.rgb,
      });
    } else {
      cloudLayer.upload({ position: new Float32Array(0), count: 0 }, 1);
    }

    applyVisibility();
    hud.reflow();
    hud.setFrame(live, state.colormap);
    requestRender();
  }

  /**
   * Point the camera at the middle of what is visible.
   *
   * The stage is the whole window and the panels float over it, so the centre
   * of the canvas is somewhere behind the rail or under the dock. Without
   * this the data sits there: centred on the window, off-centre in the gap
   * the user is actually looking at.
   *
   * `setViewOffset` slides the frustum rather than the camera, so an orbit
   * still turns about the data and nothing downstream -- the picker, the
   * axis labels, a snapshot -- has to know this happened.
   *
   * @param {number} width Stage width in CSS pixels.
   * @param {number} height Stage height in CSS pixels.
   */
  function frame(width, height) {
    const { left, right, top, bottom } = hud.insets();
    const clearWidth = Math.max(width - left - right, 1);
    const clearHeight = Math.max(height - top - bottom, 1);

    // The box projects to `height * tan(theta) / tan(fov / 2)` pixels either
    // way round -- it is a sphere -- so both edges want the same relation,
    // and only the smaller gap decides. `theta` is the box's own half angle,
    // which is `FOV / 2` reduced by the margin the distance already carries.
    const open = Math.max(
      1,
      height / (FIT * GAP_FILL * clearWidth),
      height / (FIT * GAP_FILL * clearHeight)
    );
    const half = Math.atan(Math.tan((FOV / 2) * (Math.PI / 180)) * open);
    camera.fov = Math.min(FOV_MAX, (2 * half * 180) / Math.PI);
    // Shift the frustum by half the difference between the two edges, which
    // is how far the gap's centre is from the canvas's.
    camera.setViewOffset(width, height, (right - left) / 2, (bottom - top) / 2, width, height);
    camera.aspect = width / Math.max(height, 1);
    camera.updateProjectionMatrix();
  }

  function resize() {
    if (!state.mounted) {
      return;
    }
    // Before the size check, not after: a splitter drag moves the panels
    // without changing the stage, and the camera has to re-frame for that
    // too. `reflow` says whether anything actually moved, so a call that
    // changes nothing costs one `getBoundingClientRect` per panel and stops.
    const moved = hud.reflow();

    const width = stage.clientWidth || window.innerWidth;
    const height = stage.clientHeight || window.innerHeight;
    const sized = width !== state.width || height !== state.height;
    if (!moved && !sized) {
      return;
    }

    if (sized) {
      state.width = width;
      state.height = height;
      // Re-applied rather than set once at mount: a window dragged to a
      // monitor with a different scale factor changes this, and the scene
      // would stay at the old one and look soft.
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.setSize(width, height, false);
    }

    frame(width, height);
    requestRender();
  }

  /**
   * Take the scene's colours from the stylesheet.
   *
   * Nothing is hard-coded here: the custom properties are read back off the
   * document, so the scene and the chrome cannot drift apart and a change to
   * `app.css` and `hud.css` reach both.
   */
  function applyTheme() {
    if (!state.mounted) {
      return;
    }
    const style = getComputedStyle(document.documentElement);
    const read = (name, fallback) => {
      const value = style.getPropertyValue(name).trim();
      return value || fallback;
    };

    axes.setTheme({
      // The floor fades into whatever the page is painted with, so the
      // background colour has to be the real one rather than a stand-in --
      // this is the same token `body` uses.
      background: read("--sv-bg", "#0a0c0f"),
      ground: read("--sv-view-ground", "#111c21"),
      grid: read("--sv-view-grid", "#27474f"),
      axisX: read("--sv-ax-x", "#ff5f5f"),
      axisY: read("--sv-ax-y", "#4fd06a"),
      axisZ: read("--sv-ax-z", "#4e9eff"),
      // The labels lie in the floor as textures now, so their colour is
      // drawn in rather than inherited from a stylesheet. The faint one:
      // they are there to be read off when a coordinate is wanted, not to
      // be the second thing the eye lands on after the data.
      ink: read("--sv-text-faint", "#5d656f"),
    });
    requestRender();
  }

  /**
   * Park or resume the render loop.
   *
   * It does not hide anything: the host element belongs to whoever passed it
   * in, and a renderer reaching up to restyle its container is how a layout
   * ends up with two owners. Parking matters because the loop is on demand --
   * an inactive scene should cost nothing, not merely be invisible.
   */
  function setActive(on) {
    state.active = Boolean(on);
    if (state.active) {
      resize();
      requestRender();
    }
  }

  mount(host);

  return {
    setFrame,
    setActive,
    setTheme: applyTheme,
    setPalette: (palette) => {
      setPalette(palette);
      if (state.frame) {
        hud.setFrame(state.frame, state.colormap);
      }
      requestRender();
    },
    setColormap: (name) => {
      state.colormap = name || state.colormap;
      if (state.frame && state.frame.cType === "numerical") {
        const lut = lutTexture(state.colormap);
        slots.forEach((slot) => slot.layers.forEach((layer) => layer.setUniforms({ lut })));
        hud.setFrame(state.frame, state.colormap);
      }
      requestRender();
    },
    // Shown while a frame the renderer has been asked for is not buffered
    // yet. Plotly has a server-side fallback that draws one on demand; GL
    // waits for the buffer instead, and without this the wait looks like a
    // scene that simply failed to appear.
    setPending: (pending) => {
      if (state.mounted) {
        hud.setNotice(pending ? "Buffering frame …" : null);
      }
    },
    setSizeVary: (on) => {
      if (state.payload) {
        setFrame(Object.assign({}, state.payload, { sizeVary: Boolean(on) }));
      }
    },
    resize,
    preset: setPreset,
    /**
     * Let the next frame frame itself again.
     *
     * The camera is fitted once and then left alone, so that a frame arriving
     * does not throw away where the user has moved to. A new log is a new box
     * though, and keeping the old camera leaves its data off-screen. The flag
     * is cleared rather than the camera moved here, because the distance to
     * fit is computed from the layout that has not arrived yet.
     */
    reframe: () => {
      state.framed = false;
    },
    /**
     * A PNG data URL of the scene as it stands.
     *
     * Renders first, in the same turn. Without `preserveDrawingBuffer` the
     * colour buffer is thrown away once the browser composites, so reading
     * the canvas at any other moment gives a blank image -- and setting that
     * flag instead would cost a copy on every frame to serve an export taken
     * once a session.
     *
     * The axis labels lie in the floor as geometry, so unlike the old DOM
     * ones they are in it.
     *
     * @returns {string} `data:image/png;base64,...`
     */
    /** The canvas itself, for an animation recorder to capture a stream of. */
    canvas: () => canvas,
    snapshot: () => {
      if (!state.mounted) {
        return "";
      }
      renderer.render(scene, camera);

      // The canvas is transparent on purpose -- `--sv-bg` on the body is the
      // scene's background, so the theme reaches it with no GL work. That
      // makes a straight `toDataURL` a picture with no background at all,
      // which composites onto white wherever it is opened and turns the dark
      // theme's grid into black lines on paper. So the background is painted
      // in here, once, on the way out.
      const source = renderer.domElement;
      const flat = document.createElement("canvas");
      flat.width = source.width;
      flat.height = source.height;
      const paint = flat.getContext("2d");
      const style = getComputedStyle(document.documentElement);
      paint.fillStyle = (style.getPropertyValue("--sv-bg") || "#0a0c0f").trim();
      paint.fillRect(0, 0, flat.width, flat.height);
      paint.drawImage(source, 0, 0);
      return flat.toDataURL("image/png");
    },
    isMounted: () => state.mounted,
    isActive: () => state.active,
    /** Tear the scene down and give its GPU resources back. */
    dispose: () => {
      state.active = false;
      state.mounted = false;
      picker?.dispose();
      axes?.dispose();
      hud?.dispose();
      slots.forEach((slot) => slot.layers.forEach((layer) => layer.dispose()));
      slots.length = 0;
      cloudLayer?.dispose();
      meshLayer?.dispose();
      lineLayer?.dispose();
      refMarker?.dispose();
      renderer?.dispose();
      owned.forEach((element) => element.remove());
      owned = [];
    },
  };
}
