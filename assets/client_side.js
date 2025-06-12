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
          console.log("Reset signal received");
          return [0, "Reset signal received", -1];
        }

        // console.log(`Fetched data array starting from index ${local_index}:`, dataArray);

        let lastValidIndex = local_index;

        for (const item of dataArray) {
          // Check if any required field is null or undefined
          if (
            !item.fig ||
            !item.hover_strings ||
            !item.ref_fig ||
            !item.fig_layout
          ) {
            // console.log(`Invalid data at index ${item.index}, stopping storage`);

            return [
              (lastValidIndex / max_val) * 100,
              `Stored items up to index ${lastValidIndex} (stopped due to invalid data)`,
              lastValidIndex,
            ];
          }

          // Store valid item
          try {
            await new Promise((resolve, reject) => {
              const messageHandler = (e) => {
                window.dbWorker.removeEventListener("message", messageHandler);
                if (e.data.status === "success") {
                  resolve(e.data);
                } else {
                  reject(new Error(e.data.message));
                }
              };

              window.dbWorker.addEventListener("message", messageHandler);
              window.dbWorker.postMessage({
                action: "store",
                payload: {
                  id: `${session}_${item.index}`,
                  data: item,
                  timestamp: Date.now(),
                },
              });
            });
            lastValidIndex = item.index;
          } catch (error) {
            console.error(`Error storing item ${item.index}:`, error);
            return [
              dash_clientside.no_update,
              `Error storing data: ${error.message}`,
              lastValidIndex,
            ];
          }
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
      session,
      ispaused,
      colormap,
      c_picker,
      darkmode,
      key_dict,
      dark_template,
      light_template,
      local_index,
      remote_trigger
    ) {
      // Check if triggered by stop button
      const triggered = dash_clientside.callback_context.triggered.map(
        (t) => t.prop_id
      );
      if (triggered.length > 0 && triggered[0].includes("stop-button")) {
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
              const response = await new Promise((resolve, reject) => {
                const messageHandler = (e) => {
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
                });
              });

              // Validate response structure
              if (!response || !response.result) {
                throw new Error("Invalid response structure");
              }

              // Validate required data fields
              const data = response.result;
              if (
                !data.data ||
                !data.data.fig ||
                !data.data.ref_fig ||
                !data.data.fig_layout
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

        let allData = [data];
        // Get previous figures if decay > 0
        if (decay > 0) {
          for (let i = 1; i <= decay; i++) {
            const prevIndex = slider_arg - i;
            if (prevIndex >= 0) {
              try {
                const prevData = await getDataWithRetry(prevIndex);
                if (prevData) {
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

        // Apply opacity to each trace group
        allData.forEach((d, groupIndex) => {
          const startIdx = groupIndex * d.data.fig.length;
          d.data.fig.forEach((_, idx) => {
            if (fig.data[startIdx + idx]?.marker) {
              fig.data[startIdx + idx].marker.opacity =
                opacityValues[groupIndex];
            }
          });
        });

        if (ispaused) {
          allData.forEach((d, dataIndex) => {
            if (d.data.hover_strings) {
              const startIdx = dataIndex * d.data.fig.length;
              d.data.hover_strings.forEach((hover_str, idx) => {
                if (fig.data[startIdx + idx]) {
                  fig.data[startIdx + idx].text = hover_str;
                  fig.data[startIdx + idx].hovertemplate = "%{text}";
                }
              });
            }
          });
        }

        fig.data = [...fig.data, ...allData[0].data.ref_fig];

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
