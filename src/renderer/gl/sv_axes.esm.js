// The ground plane, its grid, and the range labels lying in it.
//
// Styled after movens-link's 3D view: a ground plane at zero height that fades
// into the page background toward its edges, a grid fading with it, and three
// short coloured axes out of the origin. There is no box cage. A cage states
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
// Labels stay DOM elements through CSS2DRenderer. Sprites would be the obvious
// alternative and are wrong here: that scaling is strongly anisotropic -- a
// long-range log is sixteen times wider than it is tall -- and a sprite
// inherits it, so the text would be stretched by whatever the axis ranges
// happen to be. A projected DOM element cannot be.

import {
  BufferAttribute,
  BufferGeometry,
  Color,
  DoubleSide,
  Group,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
} from "three";
import { CSS2DObject } from "three/examples/jsm/renderers/CSS2DRenderer.js";

const AXES = ["x", "y", "z"];

// Subdivision of the ground plane. The fade is per-vertex, so this is what
// decides how smooth it looks; 24 is past the point where more shows.
const PLANE_STEPS = 24;

// Where the fade starts and ends, as a fraction of the floor's radius.
// Solid through the middle, gone by the rim -- the floor in movens-link.
const FADE_FROM = 0.3;
const FADE_TO = 1.0;

// Axis stubs out of the origin, as a fraction of each range's span.
const AXIS_LENGTH = 0.12;

function smoothstep(value, from, to) {
  const t = Math.min(1, Math.max(0, (value - from) / (to - from)));
  return t * t * (3 - 2 * t);
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

function makeLabel(className) {
  const element = document.createElement("div");
  element.className = className;
  const object = new CSS2DObject(element);
  // A CSS2DObject keeps drawing its element wherever it sits, so parking it
  // off-plane is not enough; visibility is driven explicitly.
  object.visible = false;
  return object;
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
    this.edge = "";
    this.theme = {
      ground: new Color("#111c21"),
      background: new Color("#0a0c0f"),
      grid: new Color("#27474f"),
      axis: { x: new Color("#ff5f5f"), y: new Color("#4fd06a"), z: new Color("#4e9eff") },
    };

    // `vertexColors` everywhere: the fade is baked into the geometry rather
    // than done in a shader, which keeps these ordinary materials and lets a
    // theme change rewrite one attribute instead of recompiling anything.
    this.groundMesh = new Mesh(
      new BufferGeometry(),
      new MeshBasicMaterial({
        vertexColors: true,
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
    this.groundMesh.frustumCulled = false;
    this.groundMesh.renderOrder = -2;
    this.group.add(this.groundMesh);

    this.gridLines = new LineSegments(
      new BufferGeometry(),
      new LineBasicMaterial({ vertexColors: true, transparent: true })
    );
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
    AXES.forEach((axis) => {
      const label = makeLabel("sv-gl-axis-title");
      this.titleLabels[axis] = label;
      this.group.add(label);
    });
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

    this._buildGround();
    this._buildGrid();
    this._buildAxes();
    this._buildText();
    this.edge = ""; // Force the next update() to place the text.
  }

  /**
   * Where the floor is centred, and how far it reaches before it is gone.
   *
   * Centred on the data's own origin, not on the middle of the box. The box is
   * the filter sliders' extent and is routinely far off-centre -- a log that
   * drives north for 300 m has its sensor at one corner of it -- so fading
   * from the box centre would thin the floor out exactly where the sensor,
   * and therefore the data, actually is. Centring on the origin is what makes
   * it read as ground around the vehicle rather than a rectangle around the
   * numbers, which is the same thing movens-link does by centring its floor on
   * the robot's base.
   *
   * The radius is isotropic, so the fade is a circle on the ground rather than
   * an ellipse stretched by whatever the two ranges happen to be.
   *
   * `span` is the rectangle the floor is actually drawn over, and it is not
   * the data's ranges. The radius reaches the *longer* half of each axis, so
   * on the side where the box is shorter than that the rim of the box sits at
   * a falloff well under 1 -- a log running from -252 to 204 east fades to
   * 0.81 at its east edge, which is a fifth of the ground colour still there
   * when the geometry stops. That is a hard line across the floor, which is
   * the one thing the fade exists to avoid. The span is the box widened to
   * hold the whole circle, so every point on its boundary is at falloff 1 or
   * past it and the plane ends where it has already gone.
   */
  _floorFrame() {
    const r = this.ranges;
    const centre = {
      x: Math.min(Math.max(0, r.x[0]), r.x[1]),
      y: Math.min(Math.max(0, r.y[0]), r.y[1]),
    };
    // Far enough to cover the shorter half of the box from wherever the origin
    // sits in it; the corners beyond that are the part meant to fade away.
    const reach = Math.min(
      Math.max(centre.x - r.x[0], r.x[1] - centre.x),
      Math.max(centre.y - r.y[0], r.y[1] - centre.y)
    );
    const radius = reach || 1;
    return {
      centre,
      radius,
      span: {
        x: [Math.min(r.x[0], centre.x - radius), Math.max(r.x[1], centre.x + radius)],
        y: [Math.min(r.y[0], centre.y - radius), Math.max(r.y[1], centre.y + radius)],
      },
    };
  }

  /**
   * How far out a point on the plane is, 0 at the centre and 1 at the rim.
   */
  _falloff(x, y) {
    const { centre, radius } = this.floor || this._floorFrame();
    return Math.hypot(x - centre.x, y - centre.y) / radius;
  }

  _groundColor(x, y) {
    return this.theme.ground
      .clone()
      .lerp(this.theme.background, smoothstep(this._falloff(x, y), FADE_FROM, FADE_TO));
  }

  _gridColor(x, y, major) {
    // The line is tinted over the floor beneath it and fades out with it, so a
    // line never outlives the ground it is drawn on.
    const strength = (1 - smoothstep(this._falloff(x, y), FADE_FROM, FADE_TO)) *
      (major ? 1 : 0.55);
    return this._groundColor(x, y).lerp(this.theme.grid, strength);
  }

  _buildGround() {
    // The floor's own span, not the data's ranges: the fade has to finish
    // inside the geometry or it ends in a line.
    const r = (this.floor || this._floorFrame()).span;
    const count = PLANE_STEPS;
    const positions = new Float32Array((count + 1) * (count + 1) * 3);
    const index = [];

    for (let iy = 0; iy <= count; iy++) {
      const y = r.y[0] + ((r.y[1] - r.y[0]) * iy) / count;
      for (let ix = 0; ix <= count; ix++) {
        const x = r.x[0] + ((r.x[1] - r.x[0]) * ix) / count;
        const o = (iy * (count + 1) + ix) * 3;
        positions[o] = x;
        positions[o + 1] = y;
        positions[o + 2] = this.planeZ;
      }
    }
    for (let iy = 0; iy < count; iy++) {
      for (let ix = 0; ix < count; ix++) {
        const a = iy * (count + 1) + ix;
        const b = a + 1;
        const c = a + count + 1;
        const d = c + 1;
        index.push(a, c, d, a, d, b);
      }
    }

    this.groundMesh.geometry.dispose();
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(positions, 3));
    geometry.setAttribute(
      "color",
      new BufferAttribute(new Float32Array(positions.length), 3)
    );
    geometry.setIndex(index);
    this.groundMesh.geometry = geometry;
    this._colorGround();
  }

  _colorGround() {
    const geometry = this.groundMesh.geometry;
    const position = geometry.getAttribute("position");
    const color = geometry.getAttribute("color");
    if (!position || !color) {
      return;
    }
    for (let i = 0; i < position.count; i++) {
      const c = this._groundColor(position.getX(i), position.getY(i));
      color.setXYZ(i, c.r, c.g, c.b);
    }
    color.needsUpdate = true;
  }

  _buildGrid() {
    // Over the floor's span too, so a line never outlives the ground under
    // it by stopping where the ground is still visible.
    const r = (this.floor || this._floorFrame()).span;
    const positions = [];
    this.gridMajor = [];

    // Each line is cut at every crossing tick rather than drawn end to end, so
    // it can fade along its own length the way the floor does under it. A
    // single long segment could only take one colour at each end.
    const run = (alongAxis, acrossValue, major) => {
      const ticks = this.ticks[alongAxis];
      const bounds = r[alongAxis];
      const stops = [bounds[0], ...ticks.filter((t) => t > bounds[0] && t < bounds[1]), bounds[1]];
      for (let i = 0; i < stops.length - 1; i++) {
        for (const value of [stops[i], stops[i + 1]]) {
          if (alongAxis === "x") {
            positions.push(value, acrossValue, this.planeZ);
          } else {
            positions.push(acrossValue, value, this.planeZ);
          }
          this.gridMajor.push(major ? 1 : 0);
        }
      }
    };

    // Every fifth tick reads as major, which is what gives the floor a sense
    // of scale without labelling every line.
    this.ticks.y.forEach((y, i) => run("x", y, i % 5 === 0));
    this.ticks.x.forEach((x, i) => run("y", x, i % 5 === 0));

    this.gridLines.geometry.dispose();
    const geometry = new BufferGeometry();
    geometry.setAttribute(
      "position",
      new BufferAttribute(new Float32Array(positions), 3)
    );
    geometry.setAttribute(
      "color",
      new BufferAttribute(new Float32Array(positions.length), 3)
    );
    this.gridLines.geometry = geometry;
    this._colorGrid();
  }

  _colorGrid() {
    const geometry = this.gridLines.geometry;
    const position = geometry.getAttribute("position");
    const color = geometry.getAttribute("color");
    if (!position || !color || !this.gridMajor) {
      return;
    }
    for (let i = 0; i < position.count; i++) {
      const c = this._gridColor(
        position.getX(i),
        position.getY(i),
        this.gridMajor[i] === 1
      );
      color.setXYZ(i, c.r, c.g, c.b);
    }
    color.needsUpdate = true;
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

    const span = {
      x: (r.x[1] - r.x[0]) * AXIS_LENGTH,
      y: (r.y[1] - r.y[0]) * AXIS_LENGTH,
      z: (r.z[1] - r.z[0]) * AXIS_LENGTH,
    };
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
      if (label.element && label.element.parentNode) {
        label.element.parentNode.removeChild(label.element);
      }
    });
    this.tickLabels = [];

    // Only the two axes the plane spans get tick text, because only those have
    // a line in the plane to sit against. The height range is on the HUD
    // readout, which is where a number you cannot point at belongs.
    ["x", "y"].forEach((axis) => {
      const ticks = this.ticks[axis];
      const step = ticks.length > 1 ? ticks[1] - ticks[0] : 1;
      ticks.forEach((value) => {
        const label = makeLabel("sv-gl-tick sv-gl-tick-ground");
        label.element.textContent = formatTick(value, step);
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
      const title = this.titleLabels[axis];
      title.element.textContent = this.labels[axis] || "";
      title.visible = Boolean(this.labels[axis]);
    });
    this.titleLabels.z.element.textContent = "";
    this.titleLabels.z.visible = false;
  }

  /**
   * Re-place the text for the camera's current position.
   *
   * With no cage there is nothing to show or hide as the view swings round --
   * only which edge of the floor the numbers sit along, so they stay on the
   * side nearest the viewer instead of being read through the cloud. Driven by
   * which quadrant the camera is in, so the work is skipped until it crosses
   * an axis rather than run every frame.
   *
   * @param {Object} camera The scene camera.
   * @param {Object} root The group carrying the data-to-world transform.
   * @returns {boolean} Whether anything moved.
   */
  update(camera, root) {
    const local = root.worldToLocal(camera.position.clone());
    const r = this.ranges;
    const mid = (axis) => (r[axis][0] + r[axis][1]) / 2;

    const side = { x: local.x >= mid("x") ? 1 : 0, y: local.y >= mid("y") ? 1 : 0 };
    const edge = `${side.x}${side.y}`;
    if (edge === this.edge) {
      return false;
    }
    this.edge = edge;

    const span = { x: r.x[1] - r.x[0], y: r.y[1] - r.y[0], z: r.z[1] - r.z[0] };
    // Just outside the floor on the near side, so the numbers sit on the apron
    // rather than on top of the grid they label.
    const nearY = r.y[side.y] + (side.y === 1 ? 1 : -1) * span.y * 0.035;
    const nearX = r.x[side.x] + (side.x === 1 ? 1 : -1) * span.x * 0.035;

    this.tickLabels.forEach((label) => {
      const { axis, value } = label.userData;
      if (axis === "x") {
        label.position.set(value, nearY, this.planeZ);
      } else {
        label.position.set(nearX, value, this.planeZ);
      }
      label.visible = true;
    });

    this.titleLabels.x.position.set(
      mid("x"),
      r.y[side.y] + (side.y === 1 ? 1 : -1) * span.y * 0.1,
      this.planeZ
    );
    this.titleLabels.y.position.set(
      r.x[side.x] + (side.x === 1 ? 1 : -1) * span.x * 0.1,
      mid("y"),
      this.planeZ
    );
    return true;
  }

  /**
   * Take the floor's colours from the stylesheet.
   *
   * The fade is baked into vertex colours, so a theme change rewrites those
   * two attributes rather than touching a material.
   *
   * @param {Object} theme `{ground, background, grid, axisX, axisY, axisZ}` as
   *     CSS colour strings.
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
    this._colorGround();
    this._colorGrid();
    this._buildAxes();
  }

  dispose() {
    this.groundMesh.geometry.dispose();
    this.groundMesh.material.dispose();
    this.gridLines.geometry.dispose();
    this.gridLines.material.dispose();
    this.axisLines.geometry.dispose();
    this.axisLines.material.dispose();
    this.tickLabels
      .concat(Object.values(this.titleLabels))
      .forEach((label) => {
        if (label.element && label.element.parentNode) {
          label.element.parentNode.removeChild(label.element);
        }
      });
  }
}
