// `@types/plotly.js` describes the package's main entry, not the per-trace
// modules a custom bundle is assembled from. These say the modules exist and
// what `core` is; the registered traces are opaque by nature -- a trace module
// is a registration payload, not an API.

declare module 'plotly.js/lib/core' {
  import type * as Plotly from 'plotly.js'

  interface Core extends Omit<typeof Plotly, 'register'> {
    register(modules: unknown[]): void
  }

  const core: Core
  export default core
}

declare module 'plotly.js/lib/scatter' {
  const trace: unknown
  export default trace
}

declare module 'plotly.js/lib/histogram' {
  const trace: unknown
  export default trace
}

declare module 'plotly.js/lib/histogram2dcontour' {
  const trace: unknown
  export default trace
}

declare module 'plotly.js/lib/heatmap' {
  const trace: unknown
  export default trace
}

declare module 'plotly.js/lib/violin' {
  const trace: unknown
  export default trace
}

declare module 'plotly.js/lib/parcats' {
  const trace: unknown
  export default trace
}
