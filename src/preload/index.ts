// The whole privileged surface of the renderer.
//
// Annotated `: SensorViewBridge` on purpose: that annotation is what makes
// `npm run typecheck` fail if this and the renderer ever disagree about a
// channel's shape. Nothing else enforces it.

import { contextBridge, ipcRenderer } from 'electron'

import type { SensorViewBridge } from '../shared/types'

const bridge: SensorViewBridge = {
  data: (method, params) => ipcRenderer.invoke('data:call', method, params),
  openCase: () => ipcRenderer.invoke('case:open'),
  settings: {
    get: () => ipcRenderer.invoke('settings:get'),
    set: (patch) => ipcRenderer.invoke('settings:set', patch)
  },
  platform: process.platform
}

contextBridge.exposeInMainWorld('sensorview', bridge)
