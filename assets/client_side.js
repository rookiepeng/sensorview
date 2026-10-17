// Point-cloud backdrop frames, keyed "<session>/<load>/<log>/<frame index>". The
// cloud is display-only and identical every time a frame is revisited, so an
// in-memory cache makes scrubbing back over visited frames free. Bounded so long
// sessions cannot grow it without limit.
//
// The log has to be part of the key. A session outlives the log selected in it, and
// two logs in one case folder share frame indices -- so keying on the session alone
// serves the previous log's backdrop for every frame the user had already visited,
// while the radar traces around it come from the new one.
//
// The load counter has to be part of it too, and the log name alone is not enough to
// stand in for it. Combining logs leaves the primary selection untouched but rebuilds
// the frame list around it, so a slider position that meant one frame id before the
// combine means another one after: cached under the log name alone, index 0 of
// "0796 combined with 0103" is served 0796's backdrop while the detections around it
// are 0103's. `file-loaded-trigger` counts loads, so it changes whenever the frame
// list can, and entries from earlier loads are dropped outright rather than left to
// age out of a cache the new load is competing for.
// Which slider position the GL renderer currently has on screen. The buffer
// fills behind the user, so the callback below re-fires as it advances; this is
// what keeps that from redrawing the same frame once a second.
// Each packed frame is sliced out as its own ArrayBuffer before going into
// IndexedDB, so a frame can be read back on its own rather than dragging the
// whole batch with it. The copy happens once, here; everything downstream is
// views onto what this produced.
function splitGLBatch(buffer) {
  if (!buffer || buffer.byteLength < 8) return [];
  const view = new DataView(buffer);
  const magic = String.fromCharCode(
    view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3)
  );
  if (magic !== "SVB1") return [];

  const count = view.getUint32(4, true);
  if (count === 0xffffffff) return null; // reset sentinel
  if (count === 0) return [];

  const parts = [];
  let cursor = 8 + count * 4;
  for (let i = 0; i < count; i++) {
    const length = view.getUint32(8 + i * 4, true);
    parts.push(buffer.slice(cursor, cursor + length));
    cursor += length;
  }
  return parts;
}

// One batched IndexedDB write, awaited. Both buffer branches go through it so
// there is a single place that knows the worker's message shape.
function storeItems(items) {
  return new Promise((resolve, reject) => {
    const requestId = `store_${Date.now()}_${Math.random()}`;
    const onMessage = (event) => {
      if (event.data.requestId !== requestId) return;
      window.dbWorker.removeEventListener("message", onMessage);
      if (event.data.status === "success") {
        resolve(event.data);
      } else {
        reject(new Error(event.data.message));
      }
    };
    window.dbWorker.addEventListener("message", onMessage);
    window.dbWorker.postMessage({
      action: "storeBatch",
      payload: items,
      requestId: requestId,
    });
  });
}

const GL_DRAWN = { index: null };
const GL_REDRAW = { n: 0 };

const CLOUD_CACHE = new Map();
const CLOUD_CACHE_LIMIT = 240;
let CLOUD_CACHE_LOAD = null;

async function getCloudTrace(session, loadCount, logFile, frameIndex) {
  if (session == null || frameIndex == null) {
    return null;
  }

  if (CLOUD_CACHE_LOAD !== loadCount) {
    CLOUD_CACHE.clear();
    CLOUD_CACHE_LOAD = loadCount;
  }

  const key = `${session}/${loadCount ?? ""}/${logFile ?? ""}/${frameIndex}`;
  if (CLOUD_CACHE.has(key)) {
    return CLOUD_CACHE.get(key);
  }

  let trace = null;
  try {
    const response = await fetch(`/api/cloud/${session}/${frameIndex}`);
    if (response.ok) {
      trace = (await response.json()).trace ?? null;
    }
  } catch (error) {
    // A missing backdrop must never block the radar figure from rendering.
    console.warn(`Cloud frame ${frameIndex} unavailable:`, error);
    return null;
  }

  if (CLOUD_CACHE.size >= CLOUD_CACHE_LIMIT) {
    CLOUD_CACHE.delete(CLOUD_CACHE.keys().next().value);
  }
  CLOUD_CACHE.set(key, trace);
  return trace;
}

// One request to the IndexedDB worker, as a promise. The worker answers every
// request on the same port, so the id is what keeps two in-flight reads from
// taking each other's reply -- which is exactly what happened before request
// ids existed here.
function workerRequest(action, payload, timeoutMs) {
  return new Promise((resolve, reject) => {
    if (!window.dbWorker) {
      reject(new Error("worker not started"));
      return;
    }
    const requestId = `${action}_${Date.now()}_${Math.random()}`;
    const timer = setTimeout(() => {
      window.dbWorker.removeEventListener("message", onMessage);
      reject(new Error(`${action} timed out`));
    }, timeoutMs || 4000);

    const onMessage = (event) => {
      if (event.data.requestId !== requestId) return;
      clearTimeout(timer);
      window.dbWorker.removeEventListener("message", onMessage);
      if (event.data.status === "success") {
        resolve(event.data.result);
      } else {
        reject(new Error(event.data.message || "worker error"));
      }
    };

    window.dbWorker.addEventListener("message", onMessage);
    window.dbWorker.postMessage({ action, payload, requestId });
  });
}

// A packed frame out of the buffer. Returns the shape `svGL.setFrame` wants --
// the buffer plus where the frame starts in it, which is zero here because
// `storeGLBatch` already sliced each frame into its own buffer.
async function getGLFrame(session, index) {
  if (index < 0) {
    return null;
  }
  try {
    const record = await workerRequest("getById", `${session}_gl_${index}`);
    const buffer = record && record.data;
    if (!buffer || !(buffer instanceof ArrayBuffer) || buffer.byteLength < 8) {
      return null;
    }
    return { buffer, base: 0 };
  } catch (error) {
    return null;
  }
}

// The packed backdrop, cached exactly as the JSON one is -- same key, same
// bound, same clear on a new load. Only the wire format differs, so the two
// never need to be held at once.
async function getCloudBuffer(session, loadCount, logFile, frameIndex) {
  if (session == null || frameIndex == null) {
    return null;
  }

  if (CLOUD_CACHE_LOAD !== loadCount) {
    CLOUD_CACHE.clear();
    CLOUD_CACHE_LOAD = loadCount;
  }

  const key = `bin/${session}/${loadCount ?? ""}/${logFile ?? ""}/${frameIndex}`;
  if (CLOUD_CACHE.has(key)) {
    return CLOUD_CACHE.get(key);
  }

  let buffer = null;
  try {
    const response = await fetch(`/api/cloud3d/${session}/${frameIndex}`);
    if (response.ok) {
      buffer = await response.arrayBuffer();
    }
  } catch (error) {
    console.warn(`Cloud frame ${frameIndex} unavailable:`, error);
    return null;
  }

  if (CLOUD_CACHE.size >= CLOUD_CACHE_LIMIT) {
    CLOUD_CACHE.delete(CLOUD_CACHE.keys().next().value);
  }
  CLOUD_CACHE.set(key, buffer);
  return buffer;
}

// Plotly holds a record of the camera in the figure's own layout and restores it
// whenever the plot is redrawn. In the OS webview the desktop build runs in that
// record is not kept up: a rotation reaches the scene and nowhere else, so what
// the record holds is an angle the viewer left some time ago -- and a redraw
// then puts the view back there. Dropping the record as the viewer moves leaves
// a redraw with nothing to restore, which is what keeps the scene where they
// put it. Note that replacing the record instead of dropping it is not the same
// thing: a redraw would still restore it, and during a wheel zoom, where the
// redraw lands several notches behind the viewer, restoring it eats the zoom.
function trackCamera(graphDiv) {
  if (graphDiv.__cameraTracked || typeof graphDiv.on !== "function") {
    return true;
  }

  graphDiv.on("plotly_relayout", (event) => {
    if (!event || !event["scene.camera"] || !graphDiv.layout.scene) {
      return;
    }
    delete graphDiv.layout.scene.camera;
  });
  graphDiv.__cameraTracked = true;

  return true;
}

// Dash draws the plot after this file runs, and replaces it whenever the layout
// re-renders, so keep looking rather than binding once at load.
(function watchForPlot() {
  const attach = () => {
    const graphDiv = document.querySelector("#scatter3d .js-plotly-plot");
    return graphDiv ? trackCamera(graphDiv) : false;
  };

  if (attach()) {
    return;
  }

  const observer = new MutationObserver(attach);
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();

window.dash_clientside = Object.assign({}, window.dash_clientside, {
  clientside_callback: {
    initWorker: function (n_clicks) {
      try {
        if (!window.dbWorker) {
          window.dbWorker = new Worker("/assets/worker.js");

          // Clean up old data
          window.dbWorker.postMessage({
            action: "cleanup",
            payload: 2, // 2 days
          });
          console.log(
            "IndexedDB worker initialized, and starts to clean old cached data."
          );
        }

        return "Worker initialized successfully";
      } catch (error) {
        console.error("Worker initialization error:", error);
        return "Error: " + error.message;
      }
    },

    storeBuffer: async function (
      n_intervals,
      local_index,
      session,
      max_val,
      renderer_mode
    ) {
      if (!n_intervals)
        return [0, dash_clientside.no_update, dash_clientside.no_update];

      try {
        // Only the format the active renderer reads. Both forms of a frame
        // are roughly the same size -- the hover text dominates either way --
        // so fetching both would double the buffering a session pays for, to
        // keep a fallback warm that is rarely switched to. Toggling instead
        // rewinds `local-buffer-index`, and the other format fills in.
        const wantGL = renderer_mode === "gl" && window.svGLAvailable === true;

        const response = await fetch(
          wantGL
            ? `/api/data3d/${session}/${local_index}`
            : `/api/data/${session}/${local_index}`
        );

        const glBuffer = wantGL ? await response.arrayBuffer() : null;
        const dataArray = wantGL ? null : await response.json();

        if (wantGL) {
          const parts = splitGLBatch(glBuffer);
          if (parts === null) {
            // Reset sentinel: the server's buffer restarted under us.
            console.log("Reset signal received, clearing IndexedDB session data");
            window.dbWorker.postMessage({ action: "clearSession", payload: session });
            return [0, "Reset signal received", -1];
          }
          if (parts.length === 0) {
            return [dash_clientside.no_update, "No new data available", local_index];
          }

          const firstIndex = local_index + 1;
          const items = parts.map((part, offset) => ({
            // The same `${session}_` prefix the JSON frames use, so the
            // worker's session sweep and two-day cleanup cover these unchanged.
            id: `${session}_gl_${firstIndex + offset}`,
            data: part,
            timestamp: Date.now(),
          }));

          try {
            await storeItems(items);
          } catch (error) {
            console.error("Error storing GL frames:", error);
            return [dash_clientside.no_update, `Error: ${error.message}`, local_index];
          }

          const lastIndex = firstIndex + parts.length - 1;
          return [
            (lastIndex / max_val) * 100,
            `Stored ${parts.length} GL frames up to index ${lastIndex}`,
            lastIndex,
          ];
        }

        if (!dataArray || dataArray.length === 0) {
          // console.log('No new data available');
          return [
            dash_clientside.no_update,
            "No new data available",
            local_index,
          ];
        }

        // Check for reset signal
        if (dataArray[0].index === -1) {
          console.log("Reset signal received, clearing IndexedDB session data");
          // Clear all stale IndexedDB entries for this session to free browser memory
          window.dbWorker.postMessage({
            action: "clearSession",
            payload: session,
          });
          return [0, "Reset signal received", -1];
        }

        // console.log(`Fetched data array starting from index ${local_index}:`, dataArray);

        let lastValidIndex = local_index;

        // Validate all items first, then batch-store
        // Note: hover_strings and ref_fig may be empty arrays ([]) for empty frames,
        // so we check for null/undefined explicitly rather than falsy to avoid breaking
        // the loop when a filtered frame has no data points.
        const validItems = [];
        for (const item of dataArray) {
          if (
            item.fig == null ||
            item.hover_strings == null ||
            item.ref_fig == null ||
            item.fig_layout == null
          ) {
            break;
          }
          validItems.push({
            id: `${session}_${item.index}`,
            data: item,
            timestamp: Date.now(),
          });
          lastValidIndex = item.index;
        }


        if (validItems.length === 0) {
          return [
            dash_clientside.no_update,
            "No valid data to store",
            local_index,
          ];
        }

        // Batch store all valid items in a single IndexedDB transaction
        try {
          const storeRequestId = `store_${Date.now()}_${Math.random()}`;
          await new Promise((resolve, reject) => {
            const messageHandler = (e) => {
              // Only handle responses matching our requestId
              if (e.data.requestId !== storeRequestId) return;
              window.dbWorker.removeEventListener("message", messageHandler);
              if (e.data.status === "success") {
                resolve(e.data);
              } else {
                reject(new Error(e.data.message));
              }
            };

            window.dbWorker.addEventListener("message", messageHandler);
            window.dbWorker.postMessage({
              action: "storeBatch",
              payload: validItems,
              requestId: storeRequestId,
            });
          });
        } catch (error) {
          console.error("Error batch storing items:", error);
          return [
            dash_clientside.no_update,
            `Error storing data: ${error.message}`,
            local_index,
          ];
        }

        return [
          (lastValidIndex / max_val) * 100,
          `Stored ${dataArray.length} items up to index ${lastValidIndex}`,
          lastValidIndex,
        ];
      } catch (error) {
        console.error("Error processing data:", error);
        return [
          dash_clientside.no_update,
          `Error: ${error.message}`,
          local_index,
        ];
      }
    },

    // The palette is resolved server-side (layouts/app_layout.py) so the two
    // renderers colour a point identically. Handed over once, as soon as both
    // the store and the scene exist.
    glPalette: function (palette) {
      if (palette && window.svGLReady) {
        window.svGLReady.then(function (gl) {
          if (gl) {
            gl.setPalette(palette);
          }
        });
      }
      return window.dash_clientside.no_update;
    },

    // In GL mode the colormap is a uniform swap, so it never leaves the
    // browser; the server-side patch callback stands down (see
    // view_callbacks/scatter_3d_view.py).
    glColormap: function (colormap, mode) {
      if (mode === "gl" && window.svGL) {
        window.svGL.setColormap(colormap);
      }
      return window.dash_clientside.no_update;
    },

    // Size-vary does not change the buffered frame, only how it is drawn, so
    // in GL mode it redraws from the frame already in hand.
    glSizeVary: function (size_vary, mode) {
      if (mode === "gl" && window.svGL) {
        window.svGL.setSizeVary(Array.isArray(size_vary) && size_vary.length > 0);
      }
      return window.dash_clientside.no_update;
    },

    // Flips the stylesheet into HUD mode and parks the scene when it is not
    // the renderer in use. CSS does all the showing and hiding.
    glRendererMode: function (n_clicks, mode) {
      const ctx = window.dash_clientside.callback_context;
      const clicked =
        ctx.triggered.length > 0 && ctx.triggered[0].prop_id.includes("renderer-toggle");

      let next = mode === "plotly" ? "plotly" : "gl";
      if (clicked && n_clicks > 0) {
        next = next === "gl" ? "plotly" : "gl";
      }

      // The store holds what the user asked for; availability only decides
      // what is actually applied. Writing the fallback back into the store
      // would turn one load without a GL context -- a driver reset, a machine
      // they opened it on once -- into a permanent silent downgrade.
      const gl = next === "gl" && window.svGLAvailable === true;
      const root = document.documentElement;
      root.classList.toggle("sv-renderer-gl", gl);
      root.classList.toggle("sv-renderer-plotly", !gl);

      if (window.svGLReady) {
        window.svGLReady.then(function (handle) {
          if (!handle) {
            return;
          }
          handle.setActive(gl);
          if (gl) {
            // Nothing the renderer has drawn survives a spell as the inactive
            // one, and the buffer may have stopped advancing long ago, so ask
            // for the current frame rather than waiting to be pushed one.
            GL_DRAWN.index = null;
            const clientside = window.dash_clientside;
            if (clientside && typeof clientside.set_props === "function") {
              GL_REDRAW.n += 1;
              clientside.set_props("gl-redraw", { data: GL_REDRAW.n });
            }
          }
        });
      }
      // Plotly only resizes on a window resize, so the fallback needs one when
      // it comes back from being display:none with no size.
      window.dispatchEvent(new Event("resize"));

      // The buffer holds the format the previous renderer read. Rewinding it
      // makes `storeBuffer` refill in the new one; re-storing a frame is
      // idempotent, so nothing is lost by doing it on every toggle.
      if (clicked && n_clicks > 0) {
        const clientside = window.dash_clientside;
        if (clientside && typeof clientside.set_props === "function") {
          clientside.set_props("local-buffer-index", { data: -1 });
        }
      }

      return next;
    },

    // Argument order follows the registration in server/clientside.py: every
    // Input in declaration order, then every State. `local_index` moved from
    // State to Input so the buffer advancing can drive a redraw, which moves it
    // up here with the other inputs.
    retrieveBuffer: async function (
      slider_arg,
      stop_clicks,
      decay,
      local_index,
      gl_redraw,
      enable_size_vary,
      session,
      ispaused,
      colormap,
      c_picker,
      darkmode,
      key_dict,
      dark_template,
      light_template,
      remote_trigger,
      log_file,
      load_count,
      renderer_mode
    ) {
      // Check if triggered by play-stop button while playing
      const triggered = dash_clientside.callback_context.triggered.map(
        (t) => t.prop_id
      );
      if (triggered.length > 0 && triggered[0].includes("play-stop-button") && !ispaused) {
        ispaused = true;
      }

      // One callback drives both renderers rather than two racing to read the
      // same buffer: the fetch below is the expensive part and neither needs
      // it twice. `svGLAvailable` has the last word, so a machine without
      // WebGL keeps drawing even with "gl" left in local storage.
      const useGL =
        renderer_mode === "gl" && window.svGLAvailable === true && window.svGL;

      // A filter or axis change resets the buffer to -1 and refills it. The
      // frame at a given slider position is then a different frame, so what GL
      // has already drawn stops counting as drawn.
      if (local_index === -1) {
        GL_DRAWN.index = null;
      }

      if (slider_arg > local_index) {
        // Not buffered yet. Plotly has a server-side fallback that rebuilds the
        // figure for exactly this case; GL does not, and does not need one --
        // `local-buffer-index` is an input here, so this fires again the moment
        // the buffer reaches this frame. Until then the scene says so, rather
        // than staying blank with nothing to explain it.
        if (useGL) {
          window.svGL.setPending(true);
          return [dash_clientside.no_update, dash_clientside.no_update];
        }
        return [dash_clientside.no_update, remote_trigger + 1];
      }

      // Driven by the buffer advancing rather than by the user: only act if it
      // has brought a frame GL has not drawn yet, or this would redraw on every
      // poll while the buffer fills.
      if (
        triggered.length > 0 &&
        triggered[0].includes("local-buffer-index") &&
        (!useGL || GL_DRAWN.index === slider_arg)
      ) {
        return [dash_clientside.no_update, dash_clientside.no_update];
      }

      if (useGL) {
        // Self-contained: the buffer now holds one format at a time, so this
        // must not reach for the JSON bundles -- in GL mode they were never
        // stored. Everything the scene needs is in the packed frames.
        const packed = [];
        for (let i = 0; i <= Math.max(decay, 0); i++) {
          const part = await getGLFrame(session, slider_arg - i);
          if (!part) {
            break;
          }
          packed.push(part);
        }

        if (!packed.length) {
          // The index says the frame is buffered but it is not readable yet --
          // the worker's write may still be settling. Say so and wait; the
          // next buffer tick fires this again.
          window.svGL.setPending(true);
          return [dash_clientside.no_update, dash_clientside.no_update];
        }

        const glCloud = await getCloudBuffer(
          session,
          load_count,
          log_file,
          slider_arg
        );

        GL_DRAWN.index = slider_arg;
        window.svGL.setPending(false);
        window.svGL.setFrame({
          index: slider_arg,
          glBundles: packed,
          cloudBuffer: glCloud,
          colormap: colormap,
          sizeVary: Array.isArray(enable_size_vary) && enable_size_vary.length > 0,
          // Hover text is only in the frame when the view is paused, which is
          // the same contract the Plotly path has always had.
          paused: ispaused,
        });

        // The Plotly figure is not touched: it is hidden in this mode, and the
        // exports rebuild from the dataset rather than reading it back.
        return [dash_clientside.no_update, dash_clientside.no_update];
      }

      try {
        // Helper function for data retrieval with retries
        const getDataWithRetry = async (
          sliderArg,
          maxRetries = 3,
          delayMs = 60
        ) => {
          for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
              const reqId = `get_${sliderArg}_${Date.now()}_${Math.random()}`;
              const response = await new Promise((resolve, reject) => {
                const messageHandler = (e) => {
                  // Only handle responses matching our requestId —
                  // prevents storeBuffer's response from being consumed here
                  if (e.data.requestId !== reqId) return;
                  window.dbWorker.removeEventListener(
                    "message",
                    messageHandler
                  );
                  if (e.data.status === "success") {
                    resolve(e.data);
                  } else {
                    reject(new Error(e.data.message || "Unknown error"));
                  }
                };

                window.dbWorker.addEventListener("message", messageHandler);
                window.dbWorker.postMessage({
                  action: "getById",
                  payload: `${session}_${sliderArg}`,
                  requestId: reqId,
                });
              });

              // Validate response structure
              if (!response || !response.result) {
                throw new Error("Invalid response structure");
              }

              // Validate required data fields
              // fig and ref_fig may be empty arrays for empty frames — check for null/undefined only
              const data = response.result;
              if (
                !data.data ||
                data.data.fig == null ||
                data.data.ref_fig == null ||
                data.data.fig_layout == null
              ) {
                throw new Error("Missing required data fields");
              }

              return data;
            } catch (error) {
              console.warn(`Attempt ${attempt}/${maxRetries} failed:`, error);
              if (attempt === maxRetries) throw error;
              await new Promise((resolve) => setTimeout(resolve, delayMs));
            }
          }
        };

        const data = await getDataWithRetry(slider_arg);
        if (!data) {
          // console.log(`No data found for index ${slider_arg}`);
          return [dash_clientside.no_update, remote_trigger + 1];
        }

        // Add size offset to data.fig: offset = length - 1 - i
        if (data.data && data.data.fig && enable_size_vary && enable_size_vary.length > 0) {
          data.data.fig.forEach((trace, idx) => {
            if (trace?.marker?.size) {
              const figLength = data.data.fig.length;
              const offset = figLength - 1 - idx;
              if (Array.isArray(trace.marker.size)) {
                trace.marker.size = trace.marker.size.map(
                  (size) => 3 + offset
                );
              } else {
                trace.marker.size = 3 + offset;
              }
            }
          });
        }

        let allData = [data];
        // Get previous figures if decay > 0
        if (decay > 0) {
          for (let i = 1; i <= decay; i++) {
            const prevIndex = slider_arg - i;
            if (prevIndex >= 0) {
              try {
                const prevData = await getDataWithRetry(prevIndex);
                if (prevData) {
                  if (prevData.data && prevData.data.fig && enable_size_vary && enable_size_vary.length > 0) {
                    prevData.data.fig.forEach((trace, idx) => {
                      if (trace?.marker?.size) {
                        const figLength = prevData.data.fig.length;
                        const offset = figLength - 1 - idx;
                        if (Array.isArray(trace.marker.size)) {
                          trace.marker.size = trace.marker.size.map(
                            (size) => 3 + offset
                          );
                        } else {
                          trace.marker.size = 3 + offset;
                        }
                      }
                    });
                  }
                  allData.push(prevData);
                }
              } catch (error) {
                console.warn(`Failed to get data for index ${prevIndex}`);
              }
            }
          }
        }

        // console.log(`Retrieved ${allData.length} figures`);
        const fig = {
          data: allData.flatMap((d) => d.data.fig),
          layout: data.data.fig_layout,
        };

        // Create opacity array
        const opacityValues = Array.from(
          { length: allData.length },
          (_, i) => 1 - (0.8 * i) / (allData.length - 1 || 1)
        );

        // Apply opacity to each trace group using a cumulative offset.
        // Using `groupIndex * d.data.fig.length` was wrong when fig is an empty array
        // (e.g. a filtered-out frame), which caused startIdx to be 0 for all groups
        // and overwrote/leaked traces from earlier groups.
        let traceOffset = 0;
        allData.forEach((d, groupIndex) => {
          const groupLen = d.data.fig.length;
          d.data.fig.forEach((_, idx) => {
            if (fig.data[traceOffset + idx]?.marker) {
              fig.data[traceOffset + idx].marker.opacity =
                opacityValues[groupIndex];
            }
          });
          traceOffset += groupLen;
        });

        if (ispaused) {
          let hoverOffset = 0;
          allData.forEach((d) => {
            const groupLen = d.data.fig.length;
            if (d.data.hover_strings && d.data.hover_strings.length > 0) {
              d.data.hover_strings.forEach((hover_str, idx) => {
                if (fig.data[hoverOffset + idx]) {
                  fig.data[hoverOffset + idx].text = hover_str;
                  fig.data[hoverOffset + idx].hovertemplate = "%{text}";
                }
              });
            }
            hoverOffset += groupLen;
          });
        }

        fig.data = [...fig.data, ...allData[0].data.ref_fig];

        // Point-cloud backdrop. Appended after the opacity/hover loops above so the
        // decay-opacity ramp applied to radar trace groups never touches it —
        // cloud has no decay and no controls, its styling is fixed.
        const cloudTrace = await getCloudTrace(
          session,
          load_count,
          log_file,
          slider_arg
        );
        if (cloudTrace) {
          fig.data = [...fig.data, cloudTrace];
        }

        const c_type = key_dict[c_picker]?.type || "numerical";
        if (c_type === "numerical") {
          fig.data.forEach((trace) => {
            if (trace?.marker) {
              trace.marker.colorscale = colormap;
            }
          });
        }

        if (Array.isArray(darkmode) && darkmode.length > 0) {
          fig.layout.template = dark_template;
        } else {
          fig.layout.template = light_template;
        }

        return [fig, dash_clientside.no_update];
      } catch (error) {
        console.error("Error retrieving data:", error);
        return [dash_clientside.no_update, remote_trigger + 1];
      }
    },
  },
});
