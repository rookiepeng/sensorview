from dash import Dash, html, dcc, Input, Output, State, ctx
import time

app = Dash(__name__)

app.layout = html.Div([
    html.H1("IndexedDB Worker Test with Async Callbacks"),
    
    # Worker initialization
    html.Button("Initialize Worker", id="init-worker-btn"),
    html.Div(id="worker-status"),
    
    # Test controls
    html.Div([
        html.H3("Test Actions"),
        html.Button("Store Test Data", id="store-btn"),
        html.Button("Get All Data", id="get-all-btn"),
        html.Div([
            html.Label("Get by ID:"),
            dcc.Input(id="get-id-input", type="text", placeholder="Enter ID"),
            html.Button("Get", id="get-by-id-btn")
        ])
    ]),
    
    # Results display
    html.Div([
        html.H3("Test Results"),
        html.Pre(id="test-results")
    ]),
    
    # Hidden component for state management
    dcc.Store(id="worker-initialized", data=False)
])

# Initialize worker
app.clientside_callback(
    """
    function(n_clicks, currently_initialized) {
        if (!n_clicks) return [currently_initialized, "Click to initialize worker"];
        
        try {
            if (!window.dbWorker) {
                window.dbWorker = new Worker('/assets/worker.js');
            }
            
            return [true, "Worker initialized successfully"];
        } catch (error) {
            console.error("Worker initialization error:", error);
            return [false, "Error: " + error.message];
        }
    }
    """,
    [Output("worker-initialized", "data"),
     Output("worker-status", "children")],
    Input("init-worker-btn", "n_clicks"),
    State("worker-initialized", "data"),
    prevent_initial_call=True
)

# Store data test - using async callback
app.clientside_callback(
    """
    async function(n_clicks, is_initialized) {
        if (!n_clicks) return dash_clientside.no_update;
        if (!is_initialized) return "Worker not initialized. Click 'Initialize Worker' first.";
        
        const testData = {
            name: `Test Item ${Date.now()}`,
            value: `Value ${Math.floor(Math.random() * 1000)}`,
            category: 'test',
            timestamp: Date.now()
        };
        
        // Create a promise that resolves when the worker responds
        const response = await new Promise((resolve) => {
            // Set up a one-time message handler
            const messageHandler = (e) => {
                window.dbWorker.removeEventListener('message', messageHandler);
                resolve(e.data);
            };
            
            window.dbWorker.addEventListener('message', messageHandler);
            
            // Send the message to the worker
            window.dbWorker.postMessage({
                action: 'store',
                payload: testData
            });
        });
        
        // Return the formatted response
        return JSON.stringify(response, null, 2);
    }
    """,
    Output("test-results", "children"),
    Input("store-btn", "n_clicks"),
    State("worker-initialized", "data"),
    prevent_initial_call=True
)

# Get all data test - using async callback
app.clientside_callback(
    """
    async function(n_clicks, is_initialized) {
        if (!n_clicks) return dash_clientside.no_update;
        if (!is_initialized) return "Worker not initialized. Click 'Initialize Worker' first.";
        
        // Create a promise that resolves when the worker responds
        const response = await new Promise((resolve) => {
            // Set up a one-time message handler
            const messageHandler = (e) => {
                window.dbWorker.removeEventListener('message', messageHandler);
                resolve(e.data);
            };
            
            window.dbWorker.addEventListener('message', messageHandler);
            
            // Send the message to the worker
            window.dbWorker.postMessage({
                action: 'getAll',
                payload: null
            });
        });
        
        // Return the formatted response
        return JSON.stringify(response, null, 2);
    }
    """,
    Output("test-results", "children", allow_duplicate=True),
    Input("get-all-btn", "n_clicks"),
    State("worker-initialized", "data"),
    prevent_initial_call=True
)

# Get by ID test - using async callback
app.clientside_callback(
    """
    async function(n_clicks, is_initialized, id_value) {
        if (!n_clicks) return dash_clientside.no_update;
        if (!is_initialized) return "Worker not initialized. Click 'Initialize Worker' first.";
        if (!id_value) return "Please enter an ID to retrieve";
        
        // Create a promise that resolves when the worker responds
        const response = await new Promise((resolve) => {
            // Set up a one-time message handler
            const messageHandler = (e) => {
                window.dbWorker.removeEventListener('message', messageHandler);
                resolve(e.data);
            };
            
            window.dbWorker.addEventListener('message', messageHandler);
            
            // Send the message to the worker
            window.dbWorker.postMessage({
                action: 'getById',
                payload: id_value
            });
        });
        
        // Return the formatted response
        return JSON.stringify(response, null, 2);
    }
    """,
    Output("test-results", "children", allow_duplicate=True),
    Input("get-by-id-btn", "n_clicks"),
    State("worker-initialized", "data"),
    State("get-id-input", "value"),
    prevent_initial_call=True
)

if __name__ == '__main__':
    app.run(debug=True)
    