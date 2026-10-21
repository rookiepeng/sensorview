// The main process: one window, the IPC handlers behind it, and the lockdown.
//
// During the migration this window points at the Dash dev server, which the
// developer starts separately (`SENSORVIEW_DASH=1 python main.py --debug`).
// That is deliberate and temporary: packaging Python inside Electron would
// mean a PyInstaller bundle as an extraResource, a spawned child, a port
// handshake and orphan cleanup -- all of it thrown away once the renderer is
// native. So this configuration is never packaged; `npm run dist` builds the
// real renderer, which is empty until then.

import { writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from 'electron'

import { DataClient, dataEntry } from './dataClient'
import { allowRoot, registerHandler, registerScheme } from './protocol'
import { videoCacheDir } from '../data/video'
import { SettingsStore } from './store'
import { fail, ok, type Result, type Settings } from '../shared/types'

const here = dirname(fileURLToPath(import.meta.url))

// Where the window points while the UI is still Dash. Unset once the renderer
// is native; `npm run dev` then serves it the usual way.
const DASH_URL = process.env.SENSORVIEW_DASH_URL ?? 'http://127.0.0.1:8050'
const USE_DASH = process.env.SENSORVIEW_DASH === '1'

// Must run before the app is ready.
registerScheme()

const settings = new SettingsStore(app.getPath('userData'))
const data = new DataClient(dataEntry(here))

let win: BrowserWindow | null = null

/** `--sv-bg` for each theme, so the pre-paint surface is the one the
 * renderer is about to draw. Kept in step with `styles/app.css` by hand:
 * main cannot read a stylesheet it never loads. */
const BACKGROUND: Record<string, string> = { dark: '#0a0c0f', light: '#eceef1' }

function createWindow(theme: string): void {
  win = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 960,
    minHeight: 600,
    show: false,
    backgroundColor: BACKGROUND[theme] ?? BACKGROUND.dark,
    title: app.getName(),
    webPreferences: {
      preload: join(here, '../preload/index.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      // The transport plays frames, and a throttled renderer stops advancing
      // them the moment the window is covered by another.
      backgroundThrottling: false
    }
  })

  win.once('ready-to-show', () => win?.show())

  // Nothing in this app navigates. A link goes to the user's browser; an
  // in-window navigation is a bug or an attack, and either way is refused.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) {
      void shell.openExternal(url)
    }
    return { action: 'deny' }
  })
  win.webContents.on('will-navigate', (event, url) => {
    // The Dash shell is a real page load, so it is the one exception, and only
    // while that mode is on.
    if (USE_DASH && url.startsWith(DASH_URL)) {
      return
    }
    event.preventDefault()
  })

  if (USE_DASH) {
    void win.loadURL(DASH_URL)
  } else if (process.env.ELECTRON_RENDERER_URL) {
    void win.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    void win.loadFile(join(here, '../renderer/index.html'))
  }

  win.on('closed', () => {
    win = null
  })
}

function buildMenu(): void {
  const isMac = process.platform === 'darwin'
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      ...(isMac ? [{ role: 'appMenu' as const }] : []),
      {
        label: '&File',
        submenu: [
          {
            label: 'Open Case…',
            accelerator: 'CmdOrCtrl+O',
            click: () => void openCase()
          },
          { type: 'separator' as const },
          isMac ? { role: 'close' as const } : { role: 'quit' as const }
        ]
      },
      { role: 'editMenu' as const },
      { role: 'viewMenu' as const },
      { role: 'windowMenu' as const }
    ])
  )
}

/**
 * Ask for a case directory, and authorise it.
 *
 * Opening is the only thing that widens what `sv://` can read, which is how
 * the Python routes' property survives: a path is reachable because the user
 * chose its directory, never because the renderer named it.
 */
async function openCase() {
  if (!win) {
    return fail(0, 'no window')
  }

  const current = await settings.get()
  const result = await dialog.showOpenDialog(win, {
    title: 'Open case',
    properties: ['openDirectory'],
    defaultPath: current.dataPath || undefined
  })

  if (result.canceled || result.filePaths.length === 0) {
    return ok(null)
  }

  const dir = result.filePaths[0]!
  allowRoot(dir)
  await settings.remember(dir)
  app.addRecentDocument(dir)
  win.setTitle(`${app.getName()} — ${dir}`)
  win.webContents.send('case:opened', dir)
  return ok(dir)
}

/**
 * Write an export where the user says.
 *
 * The renderer builds the bytes and this chooses the destination, so an
 * export can only ever land somewhere the user picked in a native dialog --
 * the same shape as `sv://`, where the renderer may ask for any path and
 * main decides which ones exist.
 */
async function saveFile(request: {
  suggestedName: string
  data: string
  encoding: 'utf8' | 'base64'
  filters?: Array<{ name: string; extensions: string[] }>
}): Promise<Result<string | null>> {
  // The end-to-end check cannot click a native dialog, and mocking this in
  // the renderer would leave main's writer -- the part that actually touches
  // the disk -- unchecked. So the check names a directory and the dialog is
  // skipped. Only ever set by `scripts/smoke.mjs`; the app never sets it.
  const smokeDir = process.env.SENSORVIEW_SMOKE_SAVE_DIR
  if (smokeDir) {
    const target = join(smokeDir, request.suggestedName)
    try {
      await writeFile(target, Buffer.from(request.data, request.encoding))
    } catch (problem) {
      return fail(500, String(problem))
    }
    return ok(target)
  }

  const win = BrowserWindow.getAllWindows()[0]
  const result = win
    ? await dialog.showSaveDialog(win, {
        defaultPath: request.suggestedName,
        filters: request.filters
      })
    : await dialog.showSaveDialog({ defaultPath: request.suggestedName })

  if (result.canceled || !result.filePath) {
    return ok(null)
  }

  try {
    await writeFile(result.filePath, Buffer.from(request.data, request.encoding))
  } catch (problem) {
    return fail(500, String(problem))
  }
  return ok(result.filePath)
}

function registerIpc(): void {
  ipcMain.handle('data:call', (_event, method, params) => data.call(method, params))
  ipcMain.handle('case:open', () => openCase())
  ipcMain.handle('file:save', (_event, request) => saveFile(request))
  ipcMain.handle('settings:get', async () => ok(await settings.get()))
  ipcMain.handle('settings:set', async (_event, patch: Partial<Settings>) =>
    ok(await settings.set(patch))
  )
}

// A second launch should raise the window that is already open, not start a
// second copy pointed at the same cache directory. The end-to-end check is
// not a launch and must never defer to one: it opens no window a user would
// see, and quitting instead would have it exit 0 having run nothing -- which
// reads as a pass, and did, until a stale process from an earlier run made it
// happen.
if (!process.env.SENSORVIEW_SMOKE && !app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) {
        win.restore()
      }
      win.focus()
    }
  })

  void app.whenReady().then(async () => {
    registerHandler()
    // Transcodes are written outside any case folder, so the cache is a root
    // of its own. Narrow on purpose: the directory this app writes into, not
    // the temp directory it sits in.
    allowRoot(videoCacheDir())
    registerIpc()

    // Headless end-to-end check of the protocol and the data process. Runs
    // against this exact build, which is the only way the packaged-only
    // failures show up before a user finds them.
    const smokeFile = process.env.SENSORVIEW_SMOKE
    if (smokeFile) {
      const { runSmoke } = await import('./smoke')
      app.exit(
        await runSmoke(
          smokeFile,
          data,
          join(here, '../renderer/index.html'),
          process.env.SENSORVIEW_SMOKE_URL
        )
      )
      return
    }

    buildMenu()
    // Read before the window exists: the renderer only learns the theme after
    // it has mounted and asked over IPC, which is several frames too late to
    // choose what the empty window is painted with.
    createWindow((await settings.get()).theme)

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        void settings.get().then((stored) => createWindow(stored.theme))
      }
    })
  })

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit()
    }
  })

  app.on('will-quit', () => data.stop())
}
