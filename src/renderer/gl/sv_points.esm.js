// Point layers for the GL renderer.
//
// One `PointLayer` is one drawn group: a colour category, a decay slot's worth
// of one, or the cloud backdrop. Each owns a BufferGeometry whose attributes
// are *pooled* -- allocated once at a capacity that only ever grows, and
// refilled in place. Playback steps frames several times a second and a frame
// can carry a hundred thousand points; reallocating per frame would hand the
// GPU a new buffer every tick and leave the driver collecting the old ones.
//
// `PointsMaterial` is not used. It cannot do a per-point size and a colormap
// lookup in the same draw call, and splitting that into two passes would double
// the draw count for every group.

import {
  BufferAttribute,
  BufferGeometry,
  Points,
  ShaderMaterial,
  Vector2,
  Color,
  DoubleSide,
  FrontSide,
  Mesh,
  MeshPhongMaterial,
  LineSegments,
  LineBasicMaterial,
  NormalBlending,
} from "three";

const VERTEX_SHADER = `
attribute float aSize;
uniform float uPixelRatio;
uniform float uSizeScale;

#ifdef NUMERICAL
attribute float aValue;
uniform vec2 uCRange;
varying float vT;
#endif

#ifdef PICKING
attribute vec3 aPick;
varying vec3 vPick;
#endif

void main() {
    #ifdef NUMERICAL
    // Normalized against the colour range the server fixed for the whole log,
    // not this frame's extent -- otherwise the colours would breathe as the
    // slider moves.
    vT = clamp((aValue - uCRange.x) / max(uCRange.y - uCRange.x, 1e-9), 0.0, 1.0);
    #endif

    #ifdef PICKING
    vPick = aPick;
    #endif

    // Screen-space, so the scene's data-to-world scaling never reaches it and a
    // point stays the size Plotly drew it whatever the axis ranges are.
    gl_PointSize = max(aSize * uSizeScale * uPixelRatio, 1.0);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const FRAGMENT_SHADER = `
uniform float uOpacity;

#ifdef NUMERICAL
uniform sampler2D uLUT;
varying float vT;
#else
uniform vec3 uColor;
#endif

#ifdef PICKING
varying vec3 vPick;
#endif

void main() {
    // A round sprite, and -- because the pick pass compiles this same source --
    // a pickable disc that is exactly the drawn disc.
    vec2 delta = gl_PointCoord - vec2(0.5);
    if (dot(delta, delta) > 0.25) discard;

    #ifdef PICKING
    gl_FragColor = vec4(vPick, 1.0);
    #else
        #ifdef NUMERICAL
        gl_FragColor = vec4(texture2D(uLUT, vec2(vT, 0.5)).rgb, uOpacity);
        #else
        gl_FragColor = vec4(uColor, uOpacity);
        #endif
    #endif
}
`;

/**
 * Grow a Float32 attribute to hold at least `count` items, by doubling.
 *
 * Returns the attribute to write into -- the same one when it was already big
 * enough, which is the common case once a log's busiest frame has been seen.
 *
 * @param {BufferGeometry} geometry Geometry owning the attribute.
 * @param {string} name Attribute name.
 * @param {number} itemSize Components per item.
 * @param {number} count Items needed.
 * @returns {BufferAttribute} An attribute with capacity for `count` items.
 */
function ensureCapacity(geometry, name, itemSize, count) {
  const existing = geometry.getAttribute(name);
  if (existing && existing.array.length >= count * itemSize) {
    return existing;
  }

  let capacity = Math.max(existing ? existing.array.length / itemSize : 256, 256);
  while (capacity < count) {
    capacity *= 2;
  }

  const attribute = new BufferAttribute(new Float32Array(capacity * itemSize), itemSize);
  attribute.setUsage(35048); // DynamicDrawUsage -- refilled every frame.
  geometry.setAttribute(name, attribute);
  return attribute;
}

/**
 * One drawn group of points.
 */
export class PointLayer {
  /**
   * @param {string} mode `"numerical"` (colormap lookup) or `"categorical"`
   *     (one flat colour).
   * @param {boolean} pickable Whether to carry a pick-id attribute.
   */
  constructor(mode, pickable = false) {
    this.mode = mode;
    this.pickable = pickable;
    this.count = 0;

    this.geometry = new BufferGeometry();
    this.material = new ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      defines: mode === "numerical" ? { NUMERICAL: "" } : {},
      uniforms: {
        uPixelRatio: { value: 1 },
        uSizeScale: { value: 1 },
        uOpacity: { value: 1 },
        uCRange: { value: new Vector2(0, 1) },
        uLUT: { value: null },
        uColor: { value: new Color(1, 1, 1) },
      },
      transparent: true,
      // The live frame writes depth so it occludes its own far side properly.
      // Decay slots do not: they are translucent, and depth-writing them makes
      // the trail punch holes in whatever is drawn after it.
      depthWrite: true,
      depthTest: true,
      blending: NormalBlending,
    });

    this.points = new Points(this.geometry, this.material);
    this.points.frustumCulled = false; // Ranges are fixed; culling buys nothing.
    this.points.visible = false;

    if (pickable) {
      this.pickMaterial = new ShaderMaterial({
        vertexShader: VERTEX_SHADER,
        fragmentShader: FRAGMENT_SHADER,
        defines:
          mode === "numerical" ? { NUMERICAL: "", PICKING: "" } : { PICKING: "" },
        uniforms: this.material.uniforms, // Shared: identical size and discard.
        transparent: false,
        depthWrite: true,
        depthTest: true,
      });
      this.pickPoints = new Points(this.geometry, this.pickMaterial);
      this.pickPoints.frustumCulled = false;
      this.pickPoints.visible = false;
    }
  }

  /**
   * Refill the layer from one group of a decoded frame.
   *
   * @param {Object} group Decoded group: `position` (Float32Array, xyz),
   *     `count`, optional `value` (Float32Array) and `pick` (Float32Array, rgb
   *     in 0-1).
   * @param {number} size Point diameter in pixels before the scale uniform.
   */
  upload(group, size) {
    const count = group.count | 0;
    this.count = count;

    if (count === 0) {
      this.geometry.setDrawRange(0, 0);
      this.points.visible = false;
      if (this.pickPoints) {
        this.pickPoints.visible = false;
      }
      return;
    }

    const position = ensureCapacity(this.geometry, "position", 3, count);
    position.array.set(group.position.subarray(0, count * 3));
    position.needsUpdate = true;

    const sizes = ensureCapacity(this.geometry, "aSize", 1, count);
    sizes.array.fill(size, 0, count);
    sizes.needsUpdate = true;

    if (this.mode === "numerical") {
      const values = ensureCapacity(this.geometry, "aValue", 1, count);
      if (group.value) {
        values.array.set(group.value.subarray(0, count));
      } else {
        values.array.fill(0, 0, count);
      }
      values.needsUpdate = true;
    }

    if (this.pickable) {
      const pick = ensureCapacity(this.geometry, "aPick", 3, count);
      if (group.pick) {
        pick.array.set(group.pick.subarray(0, count * 3));
      } else {
        pick.array.fill(0, 0, count * 3);
      }
      pick.needsUpdate = true;
    }

    this.geometry.setDrawRange(0, count);
    this.points.visible = true;
    if (this.pickPoints) {
      this.pickPoints.visible = true;
    }
  }

  /**
   * Set the per-draw uniforms.
   *
   * @param {Object} options `opacity`, `pixelRatio`, `sizeScale`, `cRange`
   *     (`[lo, hi]`), `lut` (DataTexture), `rgb` (`[r, g, b]` 0-255).
   */
  setUniforms(options) {
    const u = this.material.uniforms;
    if (options.opacity !== undefined) {
      u.uOpacity.value = options.opacity;
      // Opaque groups write depth; translucent ones must not, or the trail
      // occludes the live frame drawn behind it in the same pass.
      this.material.depthWrite = options.opacity >= 0.999;
    }
    if (options.pixelRatio !== undefined) {
      u.uPixelRatio.value = options.pixelRatio;
    }
    if (options.sizeScale !== undefined) {
      u.uSizeScale.value = options.sizeScale;
    }
    if (options.cRange) {
      u.uCRange.value.set(options.cRange[0], options.cRange[1]);
    }
    if (options.lut) {
      u.uLUT.value = options.lut;
    }
    if (options.rgb) {
      u.uColor.value.setRGB(
        options.rgb[0] / 255,
        options.rgb[1] / 255,
        options.rgb[2] / 255
      );
    }
  }

  /** Release GPU resources. */
  dispose() {
    this.geometry.dispose();
    this.material.dispose();
    if (this.pickMaterial) {
      this.pickMaterial.dispose();
    }
  }
}

/**
 * The reference body: a translucent mesh with its wireframe.
 *
 * Phong rather than basic shading so the shape reads as a body from any angle;
 * a flat fill of one colour would show only a silhouette, which is exactly the
 * information the mesh exists to add over a marker.
 */
export class MeshLayer {
  constructor() {
    this.hasData = false;
    this.geometry = new BufferGeometry();
    this.material = new MeshPhongMaterial({
      transparent: true,
      opacity: 0.35,
      flatShading: true,
      side: DoubleSide,
      depthWrite: false,
    });
    this.mesh = new Mesh(this.geometry, this.material);
    this.mesh.frustumCulled = false;
    this.mesh.visible = false;
  }

  /**
   * @param {Object|null} ref Decoded mesh: `position` (Float32Array),
   *     `index` (Uint32Array), `rgb`, `opacity`.
   */
  upload(ref) {
    this.hasData = Boolean(ref && ref.position && ref.position.length);
    if (!this.hasData) {
      this.mesh.visible = false;
      return;
    }

    this.geometry.dispose();
    this.geometry = new BufferGeometry();
    this.geometry.setAttribute("position", new BufferAttribute(ref.position, 3));
    if (ref.index && ref.index.length) {
      this.geometry.setIndex(new BufferAttribute(ref.index, 1));
    }
    this.geometry.computeVertexNormals();
    this.mesh.geometry = this.geometry;

    this.material.color.setRGB(ref.rgb[0] / 255, ref.rgb[1] / 255, ref.rgb[2] / 255);
    this.material.opacity = ref.opacity;
    this.material.side = ref.opacity < 0.999 ? DoubleSide : FrontSide;
    this.mesh.visible = true;
  }

  dispose() {
    this.geometry.dispose();
    this.material.dispose();
  }
}

/**
 * A set of line segments: the reference wireframe.
 *
 * Note that WebGL ignores `linewidth` above 1 on every major platform, so the
 * manifest's `edge_width` cannot be honoured. The outline still reads, because
 * it sits against a translucent fill rather than on its own.
 */
export class LineLayer {
  constructor() {
    this.hasData = false;
    this.geometry = new BufferGeometry();
    this.material = new LineBasicMaterial({ transparent: true, opacity: 0.9 });
    this.lines = new LineSegments(this.geometry, this.material);
    this.lines.frustumCulled = false;
    this.lines.visible = false;
  }

  /**
   * @param {Object|null} edges Decoded segments: `position` (Float32Array, two
   *     vertices per segment), `rgb`.
   */
  upload(edges) {
    this.hasData = Boolean(edges && edges.position && edges.position.length);
    if (!this.hasData) {
      this.lines.visible = false;
      return;
    }

    this.geometry.dispose();
    this.geometry = new BufferGeometry();
    this.geometry.setAttribute("position", new BufferAttribute(edges.position, 3));
    this.lines.geometry = this.geometry;

    this.material.color.setRGB(
      edges.rgb[0] / 255,
      edges.rgb[1] / 255,
      edges.rgb[2] / 255
    );
    this.lines.visible = true;
  }

  dispose() {
    this.geometry.dispose();
    this.material.dispose();
  }
}
