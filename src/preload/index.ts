// The whole privileged surface of the renderer.
//
// Annotated `: SensorViewBridge` on purpose: that annotation is what makes
// `npm run typecheck` fail if this and the renderer ever disagree about a
// channel's shape. Nothing else enforces it.

import { contextBridge, ipcRenderer } from 'electron'

import { mediaUrl } from '../shared/media'
import type { SensorViewBridge } from '../shared/types'

const bridge: SensorViewBridge = {
  data: (method, params) => ipcRenderer.invoke('data:call', method, params),
  openCase: () => ipcRenderer.invoke('case:open'),
  saveFile: (request) => ipcRenderer.invoke('file:save', request),
  mediaUrl,
  settings: {
    get: () => ipcRenderer.invoke('settings:get'),
    set: (patch) => ipcRenderer.invoke('settings:set', patch),
    rememberView: (dir, patch) => ipcRenderer.invoke('settings:view', dir, patch)
  },
  initialCase: () => ipcRenderer.invoke('case:initial'),
  platform: process.platform
}

contextBridge.exposeInMainWorld('sensorview', bridge)
