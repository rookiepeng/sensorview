// The Plotly bundle, built from only the traces this app draws.
//
// `plotly.js-dist-min` is ~3.5 MB because it carries every trace type Plotly
// has, including the WebGL 3D ones this app no longer has any use for -- the
// 3D view is three.js now. Registering traces against `lib/core` keeps the
// bundle to what is actually drawn, and makes adding a trace type a visible
// decision rather than a thing that was always there.
//
// Each of the analysis dock's views registers what it needs here as it lands.

import Plotly from 'plotly.js/lib/core'

import scatter from 'plotly.js/lib/scatter'

Plotly.register([scatter])

export default Plotly
