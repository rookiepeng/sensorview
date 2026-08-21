// Point-cloud backdrop frames, keyed "<session>/<log>/<frame index>". The cloud is
// display-only and identical every time a frame is revisited, so an in-memory cache
// makes scrubbing back over visited frames free. Bounded so long sessions cannot grow
// it without limit.
//
// The log has to be part of the key. A session outlives the log selected in it, and
// two logs in one case folder share frame indices -- so keying on the session alone
// serves the previous log's backdrop for every frame the user had already visited,
// while the radar traces around it come from the new one.
const CLOUD_CACHE = new Map();
const CLOUD_CACHE_LIMIT = 240;

async function getCloudTrace(session, logFile, frameIndex) {
  if (session == null || frameIndex == null) {
    return null;
  }

  const key = `${session}/${logFile ?? ""}/${frameIndex}`;
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

    storeBuffer: async function (n_intervals, local_index, session, max_val) {
      if (!n_intervals)
        return [0, dash_clientside.no_update, dash_clientside.no_update];

      try {
        const response = await fetch(`/api/data/${session}/${local_index}`);
        const dataArray = await response.json();

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

    retrieveBuffer: async function (
      slider_arg,
      stop_clicks,
      decay,
      enable_size_vary,
      session,
      ispaused,
      colormap,
      c_picker,
      darkmode,
      key_dict,
      dark_template,
      light_template,
      local_index,
      remote_trigger,
      log_file
    ) {
      // Check if triggered by play-stop button while playing
      const triggered = dash_clientside.callback_context.triggered.map(
        (t) => t.prop_id
      );
      if (triggered.length > 0 && triggered[0].includes("play-stop-button") && !ispaused) {
        ispaused = true;
      }

      if (slider_arg > local_index) {
        return [dash_clientside.no_update, remote_trigger + 1];
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
        const cloudTrace = await getCloudTrace(session, log_file, slider_arg);
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
