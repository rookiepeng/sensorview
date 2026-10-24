// The ground plane, its grid, and the range labels lying in it.
//
// Styled after movens-link's 3D view: a ground plane at zero height that fades
// into the page background toward its edges, a grid fading with it, and three
// short colored axes out of the origin. There is no box cage. A cage states
// the extent six times over and puts half of itself between the viewer and the
// data; a floor states it once, from underneath, and leaves the cloud in clear
// air. The fade is what replaces the far edge -- the plane stops being visible
// before it stops, so nothing has to be drawn to close it off.
//
// The range labels lie *in* that plane rather than floating beside the box, so
// reading a coordinate is reading the floor the points stand on.
//
// Built in data coordinates and parented to the same group as the points, so
// the scene's data-to-world scaling places both together. Ranges are never
// derived from the points: `get_scatter3d_layout` fixes them from the filter
// sliders with `autorange: False`, precisely so the floor does not resize as
// the slider moves.
//
// Labels are quads lying in the ground, textured with their own text. They
// used to be DOM through CSS2DRenderer, on the reasoning that a mesh under
// `root` would be stretched by an anisotropic scale -- "a long-range log is
// sixteen times wider than it is tall". That is not what `root` does:
// `aspectOf` returns the spans' own proportions, so the three scales are
// equal and a quad under it keeps its shape. Measured in the running app,
// 4.77818 px/m east against 4.77815 north.
//
// Being geometry rather than DOM is what lets them lie flat, and it buys two
// things besides: the cloud occludes them the way it occludes anything else
// at that height, and a snapshot contains them.

import {
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  DoubleSide,
  Group,
  LineBasicMaterial,
  LineSegments,
  LinearFilter,
  LinearMipmapLinearFilter,
  Mesh,
  MeshBasicMaterial,
  PlaneGeometry,
  Vector2,
  Vector3,
} from "three";


const AXES = ["x", "y", "z"];

// Where the fade starts and ends, as a fraction of the floor's radius.
// Solid through the middle, gone by the rim -- the floor in movens-link.
const FADE_FROM = 0.3;
const FADE_TO = 1.0;

// How big the lit floor is. It covers whichever is larger: the data the
// camera was last framed on, padded by `DATA_PAD`, or the view itself at the
// current zoom, padded by `VIEW_PAD` -- so zooming out widens the floor with
// the view rather than leaving a small disc in the middle of an empty window,
// and zooming in still keeps the data on lit ground.
const DATA_PAD = 1.25;
const VIEW_PAD = 0.75;

// The grid is built this far past the lit radius, so a pan or a zoom only
// rebuilds it once it has run off the edge of what is already there.
const GRID_SLACK = 1.6;

// Axis stubs out of the origin, in grid steps. The step is chosen to cover a
// fixed number of pixels, so the stubs keep one size on screen at any zoom.
// They used to be a fraction of each range's span, which made them as uneven
// as the ranges: a radar whose far detections reach 150 m up drew a 35 m
// "up" stub over data a metre off the ground.
const AXIS_LENGTH = 0.4;

// Roughly how far apart the grid lines should look, in pixels. The step is
// chosen to land near this at the camera's current distance and snapped to
// something a person would read -- 1, 2 or 5 times a power of ten -- so a
// zoom changes the spacing in jumps rather than sliding continuously.
const GRID_TARGET_PX = 96;

// However close the camera gets, the floor is only ever drawn with this many
// lines along its longer side. The step follows the zoom, and without this a
// close-up would ask for a step of centimetres across a five-hundred-metre
// floor -- tens of thousands of segments and a label on each.
const GRID_MAX_LINES = 160;

/**
 * Fade a basic material into the page background away from a centre.
 *
 * The fade used to be baked into vertex colors, which fixed it to a circle
 * chosen once per layout. Done per fragment it follows two uniforms instead,
 * so the lit floor can move with the camera's target and grow with the zoom
 * for the cost of setting a vector and a float.
 *
 * Patched into the stock basic shader rather than written as a ShaderMaterial,
 * so the color management and everything else the basic material does is
 * unchanged. `transformed` is the vertex in the floor's own (data) units,
 * which is what the centre and radius are given in.
 *
 * @param {Material} material A MeshBasicMaterial or LineBasicMaterial.
 * @param {Object} uniforms Shared `{uCentre, uRadius, uGround, uBackground, uGrid}`.
 * @param {boolean} lines Whether this is the grid, which tints over the floor
 *     and reads a per-vertex `aMajor`.
 */
function fadeFloor(material, uniforms, lines) {
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
varying vec2 vFloor;
${lines ? "attribute float aMajor;\nvarying float vMajor;" : ""}`
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
vFloor = transformed.xy;
${lines ? "vMajor = aMajor;" : ""}`
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
varying vec2 vFloor;
${lines ? "varying float vMajor;" : ""}
uniform vec2 uCentre;
uniform float uRadius;
uniform vec3 uGround;
uniform vec3 uBackground;
uniform vec3 uGrid;`
      )
      .replace(
        "vec4 diffuseColor = vec4( diffuse, opacity );",
        `float fade = smoothstep(${FADE_FROM.toFixed(3)}, ${FADE_TO.toFixed(3)},
  length(vFloor - uCentre) / max(uRadius, 1e-6));
vec3 floorColor = mix(uGround, uBackground, fade);
${lines ? "floorColor = mix(floorColor, uGrid, (1.0 - fade) * mix(0.55, 1.0, vMajor));" : ""}
vec4 diffuseColor = vec4(floorColor, opacity);`
      );
  };
  // Both materials patch the same chunks with the same closure source, which
  // three would otherwise take for one program.
  material.customProgramCacheKey = () => (lines ? "sv-floor-grid" : "sv-floor-ground");
}

/**
 * Tick positions at a round step covering a range.
 *
 * @param {number} lo Range minimum.
 * @param {number} hi Range maximum.
 * @param {number} target Roughly how many ticks are wanted.
 * @returns {number[]} Tick values, ascending.
 */
export function niceTicks(lo, hi, target = 6) {
  const span = hi - lo;
  if (!Number.isFinite(span) || span <= 0) {
    return [lo];
  }

  const raw = span / Math.max(target, 2);
  const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
  const normalized = raw / magnitude;
  const step =
    (normalized < 1.5 ? 1 : normalized < 3 ? 2 : normalized < 7 ? 5 : 10) * magnitude;

  const ticks = [];
  // The epsilon keeps a tick landing exactly on `hi` from being dropped by
  // floating-point drift in the accumulation.
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) {
    ticks.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  }
  return ticks;
}

/**
 * Snap a spacing to the nearest value a person would put on an axis.
 *
 * @param {number} raw The spacing wanted, in data units.
 * @returns {number} 1, 2 or 5 times a power of ten.
 */
export function niceStep(raw) {
  if (!Number.isFinite(raw) || raw <= 0) {
    return 1;
  }
  const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
  const normalized = raw / magnitude;
  return (normalized < 1.5 ? 1 : normalized < 3 ? 2 : normalized < 7 ? 5 : 10) * magnitude;
}

/**
 * Ticks at a given spacing, covering a range.
 *
 * @param {number} lo Range minimum.
 * @param {number} hi Range maximum.
 * @param {number} step Spacing, in data units.
 * @returns {number[]} Tick values, ascending.
 */
export function ticksAtStep(lo, hi, step) {
  const out = [];
  if (!(step > 0) || !Number.isFinite(hi - lo)) {
    return [lo];
  }
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) {
    out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  }
  return out.length > 0 ? out : [lo];
}

/**
 * Format a tick for display, at the precision its step warrants.
 *
 * @param {number} value Tick value.
 * @param {number} step Distance between ticks.
 * @returns {string} The label text.
 */
export function formatTick(value, step) {
  if (!Number.isFinite(value)) {
    return "";
  }
  const magnitude = Math.abs(value);
  if (magnitude >= 1e5 || (magnitude > 0 && magnitude < 1e-3)) {
    return value.toExponential(1);
  }
  const decimals = Math.max(0, Math.min(6, -Math.floor(Math.log10(Math.abs(step) || 1))));
  return value.toFixed(decimals);
}

// The text is drawn at this height in canvas pixels and the quad is scaled
// to whatever the world wants, so one setting governs how crisp it is.
const LABEL_PX = 48;

// How tall a label is as a fraction of the grid step. The step is already
// chosen to cover `GRID_TARGET_PX` on screen, so tying the text to it keeps
// it about the same size however far the camera is -- the one thing a quad
// lying in the floor does not get for free. At 0.14 of a 96-pixel cell that
// is around thirteen pixels, which is what the labels were as DOM and is
// the size at which a number is read when it is wanted and ignored when it
// is not.
const LABEL_OF_STEP = 0.14;

/**
 * A quad carrying one piece of text, to lie in the ground plane.
 *
 * `PlaneGeometry` is already in XY facing +Z, which is the ground with Z up,
 * so nothing has to be rotated to make it lie flat. Double-sided, because
 * the floor is visible from underneath and so is anything painted on it.
 *
 * @param {string} text What to draw.
 * @param {string} color Any CSS color.
 * @param {boolean} bold Titles are, ticks are not.
 * @returns {Mesh} A unit-height quad, its width set by the text.
 */
function makeTextPlane(text, color, bold) {
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  const font = `${bold ? "600 " : ""}${LABEL_PX}px system-ui, -apple-system, "Segoe UI", sans-serif`;
  context.font = font;
  // A little room either side of the glyphs, and enough above and below for
  // descenders; a texture clipped to the ink looks cramped against a grid.
  const width = Math.max(1, Math.ceil(context.measureText(text).width) + LABEL_PX * 0.5);
  const height = Math.ceil(LABEL_PX * 1.4);
  canvas.width = width;
  canvas.height = height;

  // Setting the size clears the context, so the font goes on again.
  context.font = font;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillStyle = color;
  context.fillText(text, width / 2, height / 2);

  const texture = new CanvasTexture(canvas);
  // Drawn at `LABEL_PX` and shown at about a quarter of it, so the chain is
  // the difference between a number and a shimmer. And these lie in the
  // floor, which means they are read at a grazing angle more often than
  // face on -- which is the one thing anisotropy is for.
  texture.generateMipmaps = true;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.magFilter = LinearFilter;
  texture.anisotropy = 8;

  const mesh = new Mesh(
    new PlaneGeometry(width / height, 1),
    new MeshBasicMaterial({
      map: texture,
      transparent: true,
      side: DoubleSide,
      // The floor and the grid are under it and the cloud is over it; it
      // only needs to test against them, not write into the buffer.
      depthWrite: false,
    })
  );
  mesh.renderOrder = 0;
  return mesh;
}

/** Give back a label's texture, geometry and material. */
function disposeLabel(mesh) {
  mesh.geometry.dispose();
  mesh.material.map?.dispose();
  mesh.material.dispose();
}

/**
 * The ground plane, its grid, the axis stubs, and the text in the plane.
 */
export class Axes {
  constructor() {
    this.group = new Group();
    this.ranges = { x: [-1, 1], y: [-1, 1], z: [-1, 1] };
    this.labels = { x: "", y: "", z: "" };
    this.ticks = { x: [0], y: [0], z: [0] };
    this.planeZ = 0;
    this.theme = {
      ground: new Color("#111c21"),
      background: new Color("#0a0c0f"),
      grid: new Color("#27474f"),
      axis: { x: new Color("#ff5f5f"), y: new Color("#4fd06a"), z: new Color("#4e9eff") },
    };

    // The fade is per fragment, from these. Shared by the floor and the grid,
    // so one write moves both.
    this.uniforms = {
      uCentre: { value: new Vector2(0, 0) },
      uRadius: { value: 1 },
      uGround: { value: this.theme.ground.clone() },
      uBackground: { value: this.theme.background.clone() },
      uGrid: { value: this.theme.grid.clone() },
    };
    /** How far the data reaches from where the camera was framed. */
    this.dataRadius = 1;
    /** The square the grid was last built over, and at what spacing. */
    this.gridBuilt = null;

    this.groundMesh = new Mesh(
      new BufferGeometry(),
      new MeshBasicMaterial({
        transparent: true,
        opacity: 1,
        depthWrite: false,
        // Both faces. The quads are wound anticlockwise about -Z, so with
        // the default `FrontSide` the floor drew only for a camera beneath
        // it -- which is the one place nobody looks from. Winding them the
        // other way would just move the problem: the z range runs below the
        // plane, so there is a camera under the floor to serve either way.
        side: DoubleSide,
        // The grid sits on the same plane; without this they fight for it.
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      })
    );
    fadeFloor(this.groundMesh.material, this.uniforms, false);
    this.groundMesh.frustumCulled = false;
    this.groundMesh.renderOrder = -2;
    this.group.add(this.groundMesh);

    this.gridLines = new LineSegments(
      new BufferGeometry(),
      new LineBasicMaterial({ transparent: true })
    );
    fadeFloor(this.gridLines.material, this.uniforms, true);
    this.gridLines.frustumCulled = false;
    this.gridLines.renderOrder = -1;
    this.group.add(this.gridLines);

    this.axisLines = new LineSegments(
      new BufferGeometry(),
      new LineBasicMaterial({ vertexColors: true, depthTest: false })
    );
    this.axisLines.frustumCulled = false;
    this.axisLines.renderOrder = 2;
    this.group.add(this.axisLines);

    this.tickLabels = [];
    this.titleLabels = {};
    /** The color the text is drawn with, read off the page with the rest. */
    this.ink = "#dfe4ea";
    /** Told how many tick labels there are, so the count stays observable. */
    this.onLabels = null;
  }

  /**
   * Rebuild for a new box.
   *
   * @param {Object} ranges `{x: [lo, hi], y: ..., z: ...}` in data units.
   * @param {Object} labels `{x, y, z}` axis titles.
   */
  setRanges(ranges, labels) {
    this.ranges = ranges;
    this.labels = labels || { x: "", y: "", z: "" };
    // A starting spacing for a camera that has not been placed yet; the
    // first `update` replaces it with one chosen for the distance.
    this.step = 0;
    this.ticks = {
      x: niceTicks(ranges.x[0], ranges.x[1]),
      y: niceTicks(ranges.y[0], ranges.y[1]),
      z: niceTicks(ranges.z[0], ranges.z[1]),
    };

    // Zero height, where the data has it. A log whose z range sits entirely
    // above or below zero has no such plane, so the floor goes to the nearer
    // bound rather than hanging outside the data.
    this.planeZ = Math.min(Math.max(0, ranges.z[0]), ranges.z[1]);
    this.floor = this._floorFrame();
    // Until the scene says where it framed the camera, the floor lights the
    // part of the box around the data's origin, as it always did.
    this.dataRadius = this.floor.radius;
    this.uniforms.uCentre.value.set(this.floor.centre.x, this.floor.centre.y);
    this.uniforms.uRadius.value = this.floor.radius;
    this.gridBuilt = null;

    this._buildGround();
    this._buildGrid(this.floor.centre, this.floor.radius * GRID_SLACK, this._fallbackStep());
    this._buildAxes();
    this._buildText();
  }

  /**
   * Say how far the data reaches from the point the camera was framed on.
   *
   * @param {number} radius In data units.
   */
  setDataRadius(radius) {
    if (radius > 0 && Number.isFinite(radius)) {
      this.dataRadius = radius;
    }
  }

  /** A spacing for before the camera has been placed. */
  _fallbackStep() {
    const ticks = this.ticks.x;
    return ticks.length > 1 ? ticks[1] - ticks[0] : 1;
  }

  /**
   * Where the tick labels are anchored, and the floor's starting extent.
   *
   * Centred on the data's own origin, not on the middle of the box. The box is
   * the filter sliders' extent and is routinely far off-centre -- a log that
   * drives north for 300 m has its sensor at one corner of it -- so the labels
   * run along the lines through where the sensor is.
   *
   * The radius is only where the floor starts: once the camera is placed,
   * `retick` centres the lit floor on what the camera is looking at and sizes
   * it from the data and the zoom.
   */
  _floorFrame() {
    const r = this.ranges;
    const centre = {
      x: Math.min(Math.max(0, r.x[0]), r.x[1]),
      y: Math.min(Math.max(0, r.y[0]), r.y[1]),
    };
    const reach = Math.min(
      Math.max(centre.x - r.x[0], r.x[1] - centre.x),
      Math.max(centre.y - r.y[0], r.y[1] - centre.y)
    );
    return { centre, radius: reach || 1 };
  }

  /**
   * The floor: one quad, as wide as the lit circle.
   *
   * The fade is per fragment now, so the quad needs no subdivision; it only
   * has to reach the rim, past which the floor is the background color and
   * might as well not be there.
   */
  _buildGround() {
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(new Float32Array(12), 3));
    geometry.setIndex([0, 2, 3, 0, 3, 1]);
    this.groundMesh.geometry.dispose();
    this.groundMesh.geometry = geometry;
    this._placeGround();
  }

  _placeGround() {
    const centre = this.uniforms.uCentre.value;
    const radius = this.uniforms.uRadius.value;
    const position = this.groundMesh.geometry.getAttribute("position");
    if (!position) {
      return;
    }
    const x0 = centre.x - radius;
    const x1 = centre.x + radius;
    const y0 = centre.y - radius;
    const y1 = centre.y + radius;
    position.setXYZ(0, x0, y0, this.planeZ);
    position.setXYZ(1, x1, y0, this.planeZ);
    position.setXYZ(2, x0, y1, this.planeZ);
    position.setXYZ(3, x1, y1, this.planeZ);
    position.needsUpdate = true;
  }

  /**
   * Grid lines over a square around `centre`, `half` out each way.
   *
   * Each line is one segment end to end -- the fade is per fragment, so it no
   * longer has to be cut at every crossing to fade along its length. Every
   * fifth line reads as major, counted from zero rather than from the edge so
   * the major lines stay put as the square moves.
   */
  _buildGrid(centre, half, step) {
    const span = {
      x: [centre.x - half, centre.x + half],
      y: [centre.y - half, centre.y + half],
    };
    const positions = [];
    const major = [];
    const isMajor = (value) => Math.round(value / step) % 5 === 0;

    for (const y of ticksAtStep(span.y[0], span.y[1], step)) {
      positions.push(span.x[0], y, this.planeZ, span.x[1], y, this.planeZ);
      const m = isMajor(y) ? 1 : 0;
      major.push(m, m);
    }
    for (const x of ticksAtStep(span.x[0], span.x[1], step)) {
      positions.push(x, span.y[0], this.planeZ, x, span.y[1], this.planeZ);
      const m = isMajor(x) ? 1 : 0;
      major.push(m, m);
    }

    this.gridLines.geometry.dispose();
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(new Float32Array(positions), 3));
    geometry.setAttribute("aMajor", new BufferAttribute(new Float32Array(major), 1));
    this.gridLines.geometry = geometry;
    this.gridBuilt = { span, step };
  }

  _buildAxes() {
    const r = this.ranges;
    const inside = (axis, value) => value >= r[axis][0] && value <= r[axis][1];

    // Only drawn where the data's own origin is in view. Pinning them to a
    // corner instead would make them decoration; here they mark where zero is.
    if (!inside("x", 0) || !inside("y", 0)) {
      this.axisLines.visible = false;
      return;
    }
    this.axisLines.visible = true;

    const length = (this.step || this._fallbackStep()) * AXIS_LENGTH;
    const span = { x: length, y: length, z: length };
    const origin = [0, 0, this.planeZ];
    const ends = {
      x: [span.x, 0, this.planeZ],
      y: [0, span.y, this.planeZ],
      z: [0, 0, this.planeZ + span.z],
    };

    const positions = [];
    const colors = [];
    AXES.forEach((axis) => {
      const c = this.theme.axis[axis];
      positions.push(...origin, ...ends[axis]);
      colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
    });

    this.axisLines.geometry.dispose();
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(new Float32Array(positions), 3));
    geometry.setAttribute("color", new BufferAttribute(new Float32Array(colors), 3));
    this.axisLines.geometry = geometry;
  }

  _buildText() {
    this.tickLabels.forEach((label) => {
      this.group.remove(label);
      disposeLabel(label);
    });
    this.tickLabels = [];
    Object.values(this.titleLabels).forEach((label) => {
      this.group.remove(label);
      disposeLabel(label);
    });
    this.titleLabels = {};

    // Only the two axes the plane spans get tick text, because only those have
    // a line in the plane to sit against. The height range is on the HUD
    // readout, which is where a number you cannot point at belongs.
    ["x", "y"].forEach((axis) => {
      const ticks = this.ticks[axis];
      const step = ticks.length > 1 ? ticks[1] - ticks[0] : 1;
      ticks.forEach((value) => {
        const label = makeTextPlane(formatTick(value, step), this.ink, false);
        label.userData = { axis, value };
        this.tickLabels.push(label);
        this.group.add(label);
      });
    });

    // Only the two axes the plane spans are named in the scene. The height
    // axis rises from the data's own origin, which is where the data is -- its
    // title would sit on the cloud wherever it was put. The blue stub says
    // which way is up, and the HUD readout carries the range.
    ["x", "y"].forEach((axis) => {
      const text = this.labels[axis];
      if (!text) {
        return;
      }
      const title = makeTextPlane(text, this.ink, true);
      title.userData = { axis, title: true };
      this.titleLabels[axis] = title;
      this.group.add(title);
    });

    this._placeText();
    this.onLabels?.(this.tickLabels.length);
  }

  /**
   * Follow the camera: light the floor around what it is looking at, and pick
   * a grid spacing for how close it is.
   *
   * The floor is drawn in data units, so the step has to be converted from
   * the pixels it should cover: one pixel is `2 * d * tan(fov / 2) / height`
   * world units at the target's distance, and the root's scale turns those
   * into the data's own. Snapped, so the spacing steps between readable values
   * instead of sliding, and floored so neither the grid nor the labels can ask
   * for thousands of lines.
   *
   * The lit radius is the larger of the data's reach and the view's own half
   * width at the target, so the floor fills the view when zoomed out and
   * still covers the data when zoomed in.
   *
   * @param {THREE.PerspectiveCamera} camera The scene camera.
   * @param {THREE.Object3D} root The data's transform.
   * @param {number} height Viewport height in pixels.
   * @param {THREE.Vector3} [target] What the camera orbits, in world space.
   * @returns {boolean} Whether the grid or the labels were rebuilt.
   */
  retick(camera, root, height, target) {
    const scale = root.scale.x;
    if (!(scale > 0) || !(height > 0)) {
      return false;
    }
    const aim = target || new Vector3();
    const distance = camera.position.distanceTo(aim);
    const worldPerPx = (2 * distance * Math.tan((camera.fov / 2) * (Math.PI / 180))) / height;
    const viewHalf = (worldPerPx * height * Math.max(camera.aspect || 1, 1)) / 2 / scale;

    root.updateMatrixWorld();
    const local = root.worldToLocal(aim.clone());
    const radius = Math.max(this.dataRadius * DATA_PAD, viewHalf * VIEW_PAD);
    this.uniforms.uCentre.value.set(local.x, local.y);
    this.uniforms.uRadius.value = radius;
    this._placeGround();

    const span = Math.max(
      this.ranges.x[1] - this.ranges.x[0],
      this.ranges.y[1] - this.ranges.y[0]
    );
    const half = radius * GRID_SLACK;
    const step = Math.max(
      niceStep((GRID_TARGET_PX * worldPerPx) / scale),
      niceStep(span / GRID_MAX_LINES),
      niceStep((2 * half) / GRID_MAX_LINES)
    );

    // Rebuilt when the spacing changes, or when the lit floor has run past
    // the square already built -- with slack, so a pan does not rebuild on
    // every frame.
    const built = this.gridBuilt;
    const covered =
      built &&
      built.step === step &&
      local.x - radius >= built.span.x[0] &&
      local.x + radius <= built.span.x[1] &&
      local.y - radius >= built.span.y[0] &&
      local.y + radius <= built.span.y[1];
    if (!covered) {
      this._buildGrid({ x: local.x, y: local.y }, half, step);
    }

    if (step === this.step) {
      return !covered;
    }
    this.step = step;
    this._buildAxes();
    // The labels stay over the data's box: they say where the data is, and
    // a number out on the faded floor is one nobody reads.
    this.ticks = {
      x: ticksAtStep(this.ranges.x[0], this.ranges.x[1], step),
      y: ticksAtStep(this.ranges.y[0], this.ranges.y[1], step),
      z: ticksAtStep(this.ranges.z[0], this.ranges.z[1], step),
    };
    this._buildText();
    return true;
  }

  /**
   * Place the text in the plane, along the lines through its centre.
   *
   * The numbers used to run along whichever edge of the floor was nearest
   * the camera, which kept them off the cloud but put them a long way from
   * the lines they label -- on a five-hundred-metre floor the reader is
   * matching a number at one rim to a line in the middle. They sit on the
   * centre lines now, the same two the colored axis stubs come out of, so
   * a tick is read against the grid line it names.
   *
   * Nothing here depends on where the camera is any more, so the quadrant
   * the view was in -- and the rebuild when it crossed an axis -- is gone
   * with it. Placement happens once per layout, in `_buildText`.
   */
  _placeText() {
    const r = this.ranges;
    const { centre } = this.floor || this._floorFrame();
    const span = { x: r.x[1] - r.x[0], y: r.y[1] - r.y[0] };

    // From the ticks rather than `this.step`, which is still zero on the
    // first build -- the spacing is chosen by the first `retick`, and the
    // layout has already drawn a set of labels by then.
    const ticksY = this.ticks.y;
    const near = (ticksY.length > 1 ? Math.abs(ticksY[1] - ticksY[0]) : 1) / 2;

    // Tied to the step, which is itself chosen to cover a fixed number of
    // pixels -- so the text stays about one size on screen even though it
    // is geometry lying in the floor.
    const size = (near * 2 || 1) * LABEL_OF_STEP;

    this.tickLabels.forEach((label) => {
      const { axis, value } = label.userData;
      // A hair above the floor: at exactly `planeZ` the quad and the ground
      // are coplanar and which one wins is up to the depth buffer.
      const lift = this.planeZ + size * 0.02;
      if (axis === "x") {
        label.position.set(value, centre.y - size * 0.9, lift);
        label.rotation.z = 0;
      } else {
        label.position.set(centre.x - size * 0.9, value, lift);
        // Turned to read along its own line rather than across it.
        label.rotation.z = Math.PI / 2;
      }
      label.scale.set(size, size, 1);
      // Where the two lines cross, both runs have a label on the same spot.
      // The one along x keeps it; the other would be the same point twice.
      label.visible = !(axis === "y" && Math.abs(value - centre.y) < near);
    });

    // At the far end of the line each one names, off to the side so it does
    // not land on the last tick: the title then reads as which way the
    // numbers are going.
    const titleSize = size * 1.15;
    if (this.titleLabels.x) {
      this.titleLabels.x.position.set(
        r.x[1] - span.x * 0.06,
        centre.y + titleSize * 1.1,
        this.planeZ + size * 0.02
      );
      this.titleLabels.x.rotation.z = 0;
      this.titleLabels.x.scale.set(titleSize, titleSize, 1);
    }
    if (this.titleLabels.y) {
      this.titleLabels.y.position.set(
        centre.x + titleSize * 1.1,
        r.y[1] - span.y * 0.06,
        this.planeZ + size * 0.02
      );
      this.titleLabels.y.rotation.z = Math.PI / 2;
      this.titleLabels.y.scale.set(titleSize, titleSize, 1);
    }
  }

  update(camera, root, height, target) {
    // The lit floor and the spacing follow the camera; the text does not.
    return this.retick(camera, root, height, target);
  }

  /**
   * Take the floor's colors from the stylesheet.
   *
   * The fade is baked into vertex colors, so a theme change rewrites those
   * two attributes rather than touching a material.
   *
   * @param {Object} theme `{ground, background, grid, axisX, axisY, axisZ}` as
   *     CSS color strings.
   */
  setTheme(theme) {
    this.theme = {
      ground: new Color(theme.ground),
      background: new Color(theme.background),
      grid: new Color(theme.grid),
      axis: {
        x: new Color(theme.axisX),
        y: new Color(theme.axisY),
        z: new Color(theme.axisZ),
      },
    };
    this.ink = theme.ink || this.ink;
    this.uniforms.uGround.value.copy(this.theme.ground);
    this.uniforms.uBackground.value.copy(this.theme.background);
    this.uniforms.uGrid.value.copy(this.theme.grid);
    this._buildAxes();
    // The text is baked into a texture, so a theme change redraws it.
    this._buildText();
  }

  dispose() {
    this.groundMesh.geometry.dispose();
    this.groundMesh.material.dispose();
    this.gridLines.geometry.dispose();
    this.gridLines.material.dispose();
    this.axisLines.geometry.dispose();
    this.axisLines.material.dispose();
    this.tickLabels.concat(Object.values(this.titleLabels)).forEach(disposeLabel);
  }
}
