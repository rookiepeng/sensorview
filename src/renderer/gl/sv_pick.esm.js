// Finding the point under the cursor, at a hundred thousand points.
//
// Raycasting a `Points` cloud means a distance test per vertex on the CPU, per
// pointer move. GPU colour picking instead renders the scene once into a
// one-by-one target with each point's id as its colour, and reads that single
// pixel back -- so the cost is one tiny draw regardless of how many points are
// in it, and the answer is exactly what the user sees because the pick shader
// is the display shader with a different output.
//
// Ids are *draw-order ordinals*, not the DataFrame index. The index is int64
// and can exceed the 2^24 a 24-bit colour carries; the ordinal is bounded by
// the points actually on screen. A side table maps back.
//
// Only the live frame is pickable. The decay trail and the cloud backdrop are
// not, which matches the Plotly figure: the cloud sets `hoverinfo: "skip"` and
// the trail's hover text is never attached.

import { Group, Scene, WebGLRenderTarget } from "three";

// How far the pointer may travel between press and release and still count as
// a click rather than the end of an orbit drag.
const CLICK_SLOP = 4;

// Below this, a move is not worth a pick.
const MOVE_SLOP = 2;

export class Picker {
  /**
   * @param {Object} options `renderer`, `camera`, `canvas`, `hud`,
   *     `getFrame()`, `isPaused()`, `requestRender()`, and `onPick({id, n})`
   *     to be told which row was clicked.
   */
  constructor(options) {
    this.renderer = options.renderer;
    this.camera = options.camera;
    this.canvas = options.canvas;
    this.hud = options.hud;
    this.getFrame = options.getFrame;
    this.isPaused = options.isPaused;
    this.requestRender = options.requestRender;
    this.onPick = options.onPick;

    this.scene = new Scene();
    this.root = new Group();
    this.scene.add(this.root);

    this.target = new WebGLRenderTarget(1, 1);
    this.buffer = new Uint8Array(4);

    // ordinal -> where it came from. Rebuilt per frame.
    this.ids = new Float64Array(0);
    this.groupOf = new Uint16Array(0);
    this.rowOf = new Uint32Array(0);
    this.count = 0;

    this.pointer = { x: 0, y: 0, inside: false };
    this.down = null;
    this.queued = false;
    this.lastOrdinal = -1;

    this._bind();
  }

  /**
   * Keep the pick scene's transform in step with the display scene's.
   *
   * The pickable objects share geometry with the drawn ones but live in their
   * own scene, so the data-to-world placement has to be copied across or the
   * pick would be taken against unscaled coordinates.
   *
   * @param {Group} root The display scene's root group.
   */
  syncTransform(root) {
    this.root.scale.copy(root.scale);
    this.root.position.copy(root.position);
    this.root.quaternion.copy(root.quaternion);
    this.root.updateMatrixWorld(true);
  }

  /**
   * Assign pick colours for a frame and build the lookup tables.
   *
   * Called before the layers upload, because the colour is a vertex attribute
   * that goes up with the positions.
   *
   * @param {Object} frame The decoded live frame.
   */
  prepare(frame) {
    let total = 0;
    frame.groups.forEach((group) => (total += group.count));

    if (this.ids.length < total) {
      this.ids = new Float64Array(total);
      this.groupOf = new Uint16Array(total);
      this.rowOf = new Uint32Array(total);
    }
    this.count = total;

    let ordinal = 0;
    frame.groups.forEach((group, groupIndex) => {
      const pick = new Float32Array(group.count * 3);
      for (let i = 0; i < group.count; i++) {
        // 0 is reserved for "nothing here", so ids start at 1.
        const id = ordinal + 1;
        pick[i * 3] = ((id >> 16) & 255) / 255;
        pick[i * 3 + 1] = ((id >> 8) & 255) / 255;
        pick[i * 3 + 2] = (id & 255) / 255;

        this.ids[ordinal] = group.ids ? group.ids[i] : -1;
        this.groupOf[ordinal] = groupIndex;
        this.rowOf[ordinal] = i;
        ordinal++;
      }
      group.pick = pick;
    });
  }

  /**
   * Render one pixel of the pick scene and read the id back.
   *
   * `setViewOffset` narrows the projection to the pixel under the cursor, so
   * the target stays one by one however large the canvas is.
   *
   * @param {number} px Pointer x in CSS pixels, canvas-relative.
   * @param {number} py Pointer y in CSS pixels, canvas-relative.
   * @returns {number} Ordinal, or -1 for a miss.
   */
  pick(px, py) {
    if (this.count === 0) {
      return -1;
    }

    const ratio = this.renderer.getPixelRatio();
    const width = Math.max(Math.round(this.canvas.clientWidth * ratio), 1);
    const height = Math.max(Math.round(this.canvas.clientHeight * ratio), 1);
    const x = Math.min(Math.max(Math.round(px * ratio), 0), width - 1);
    const y = Math.min(Math.max(Math.round(py * ratio), 0), height - 1);

    const previousTarget = this.renderer.getRenderTarget();
    this.camera.setViewOffset(width, height, x, y, 1, 1);
    this.renderer.setRenderTarget(this.target);
    this.renderer.setClearColor(0x000000, 1);
    this.renderer.clear();
    this.renderer.render(this.scene, this.camera);
    this.renderer.readRenderTargetPixels(this.target, 0, 0, 1, 1, this.buffer);
    this.renderer.setRenderTarget(previousTarget);
    this.renderer.setClearColor(0x000000, 0);
    this.camera.clearViewOffset();

    const id = (this.buffer[0] << 16) | (this.buffer[1] << 8) | this.buffer[2];
    const ordinal = id - 1;
    return ordinal >= 0 && ordinal < this.count ? ordinal : -1;
  }

  /**
   * The hover text for an ordinal, as plain text.
   *
   * @param {number} ordinal Pick result.
   * @returns {string|null} Hover text with line breaks, or null.
   */
  hoverText(ordinal) {
    const frame = this.getFrame();
    if (!frame || ordinal < 0) {
      return null;
    }
    const group = frame.groups[this.groupOf[ordinal]];
    if (!group || typeof group.hover !== "function") {
      return null;
    }
    const raw = group.hover(this.rowOf[ordinal]);
    if (!raw) {
      return null;
    }
    // The strings are built for Plotly, which renders `<br>`. Turned into real
    // newlines so the tooltip can set them as text rather than as markup.
    return String(raw).replace(/<br\s*\/?>/gi, "\n").replace(/\n+$/, "");
  }

  _bind() {
    const canvas = this.canvas;

    canvas.addEventListener("pointermove", (event) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;

      if (
        this.pointer.inside &&
        Math.abs(x - this.pointer.x) < MOVE_SLOP &&
        Math.abs(y - this.pointer.y) < MOVE_SLOP
      ) {
        return;
      }

      this.pointer = { x, y, inside: true, clientX: event.clientX, clientY: event.clientY };
      this._schedule();
    });

    canvas.addEventListener("pointerleave", () => {
      this.pointer.inside = false;
      this.lastOrdinal = -1;
      this.hud.setTooltip(null);
    });

    canvas.addEventListener("pointerdown", (event) => {
      this.down = { x: event.clientX, y: event.clientY };
      this.hud.setTooltip(null);
    });

    canvas.addEventListener("pointerup", (event) => {
      const down = this.down;
      this.down = null;
      if (!down) {
        return;
      }
      // An orbit ends in a pointerup too; only a press that barely moved is a
      // click on a point.
      if (
        Math.abs(event.clientX - down.x) > CLICK_SLOP ||
        Math.abs(event.clientY - down.y) > CLICK_SLOP
      ) {
        return;
      }

      const rect = canvas.getBoundingClientRect();
      const ordinal = this.pick(event.clientX - rect.left, event.clientY - rect.top);
      if (ordinal < 0) {
        return;
      }
      this._emitClick(ordinal);
    });
  }

  _schedule() {
    // Hover text only exists on a paused frame -- the buffered bundles carry it
    // only then -- and picking during an orbit drag would fight the render loop
    // for the same context.
    if (this.queued || this.down || !this.isPaused()) {
      return;
    }
    this.queued = true;
    requestAnimationFrame(() => {
      this.queued = false;
      if (!this.pointer.inside) {
        return;
      }
      const ordinal = this.pick(this.pointer.x, this.pointer.y);
      if (ordinal === this.lastOrdinal && ordinal < 0) {
        return;
      }
      this.lastOrdinal = ordinal;
      this.hud.setTooltip(
        this.hoverText(ordinal),
        this.pointer.clientX,
        this.pointer.clientY
      );
    });
  }

  _emitClick(ordinal) {
    const id = this.ids[ordinal];
    if (!Number.isFinite(id) || id < 0) {
      return;
    }
    if (typeof this.onPick !== "function") {
      return;
    }

    this.clicks = (this.clicks || 0) + 1;
    // The counter is what makes two clicks on the same point two events: the
    // id alone would look unchanged to anything comparing by value.
    this.onPick({ id, n: this.clicks });
  }

  dispose() {
    this.target.dispose();
  }
}
