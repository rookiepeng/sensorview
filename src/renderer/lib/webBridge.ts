// `window.sensorview` for a plain browser tab.
//
// The same interface the preload exposes, backed by browser primitives: the
// settings store becomes localStorage, the native folder dialog becomes a
// prompt, and the data layer answers from a fixture instead of a forked
// process. App code cannot tell the difference, which is the point -- there is
// no `if (electron)` anywhere in the renderer.
//
// A no-op inside Electron, where the preload got there first.

import type { DataMethod, DataParams, DataResult, Result, SensorViewBridge, Settings } from '@shared/types'
import { DEFAULT_SETTINGS, fail, ok } from '@shared/types'

const KEY = 'sensorview.settings'

function readSettings(): Settings {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<Settings>) } : { ...DEFAULT_SETTINGS }
  } catch {
    // Private browsing, or a value someone edited by hand. Neither is worth
    // failing over; the defaults are a working app.
    return { ...DEFAULT_SETTINGS }
  }
}

function writeSettings(next: Settings): Settings {
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    // Not persisting is a smaller problem than not running.
  }
  return next
}

/**
 * Answer a data call without a data process.
 *
 * Only what the browser target can honestly serve. A reader that needs the
 * filesystem answers 501 rather than inventing data, so a panel built against
 * a fixture cannot quietly depend on something that is not there.
 */
async function fixtureData<M extends DataMethod>(
  method: M,
  _params: DataParams<M>
): Promise<Result<DataResult<M>>> {
  if (method === 'ping') {
    return ok({ pid: 0 }) as Result<DataResult<M>>
  }
  return fail(501, `${method} needs the data process; run the app in Electron`)
}

/** Install the browser-side bridge. Does nothing inside Electron. */
export function installWebBridge(): void {
  if (window.sensorview) {
    return
  }

  const bridge: SensorViewBridge = {
    data: fixtureData,
    openCase: async () => {
      const dir = window.prompt('Case directory (browser mode has no native dialog)')
      return ok(dir && dir.trim() ? dir.trim() : null)
    },
    settings: {
      get: async () => ok(readSettings()),
      set: async (patch) => ok(writeSettings({ ...readSettings(), ...patch }))
    },
    // A browser tab has no native save dialog, so an export falls back to
    // the download the page can do for itself.
    saveFile: async ({ suggestedName, data, encoding }) => {
      const blob =
        encoding === 'base64'
          ? await (await fetch(`data:application/octet-stream;base64,${data}`)).blob()
          : new Blob([data], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = suggestedName
      link.click()
      URL.revokeObjectURL(url)
      return { ok: true, status: 200, data: suggestedName }
    },

    // No protocol handler in a browser tab, so a media path is not
    // addressable there. The inspector shows nothing rather than a
    // broken element.
    mediaUrl: () => '',
    initialCase: null,
    platform: 'browser'
  }

  window.sensorview = bridge
}
