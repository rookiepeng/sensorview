// The main process: one window, the IPC handlers behind it, and the lockdown.
//
// During the migration this window points at the Dash dev server, which the
// developer starts separately (`SENSORVIEW_DASH=1 python main.py --debug`).
// That is deliberate and temporary: packaging Python inside Electron would
// mean a PyInstaller bundle as an extraResource, a spawned child, a port
// handshake and orphan cleanup -- all of it thrown away once the renderer is
// native. So this configuration is never packaged; `npm run dist` builds the
// real renderer, which is empty until then.

import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from 'electron'

import { DataClient, dataEntry } from './dataClient'
import { allowRoot, registerHandler, registerScheme } from './protocol'
import { SettingsStore } from './store'
import { fail, ok, type Settings } from '../shared/types'

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

function createWindow(): void {
  win = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 960,
    minHeight: 600,
    show: false,
    backgroundColor: '#0a0c0f',
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

function registerIpc(): void {
  ipcMain.handle('data:call', (_event, method, params) => data.call(method, params))
  ipcMain.handle('case:open', () => openCase())
  ipcMain.handle('settings:get', async () => ok(await settings.get()))
  ipcMain.handle('settings:set', async (_event, patch: Partial<Settings>) =>
    ok(await settings.set(patch))
  )
}

// A second launch should raise the window that is already open, not start a
// second copy pointed at the same cache directory.
if (!app.requestSingleInstanceLock()) {
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
    createWindow()

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow()
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
