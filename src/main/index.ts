// The main process: one window, the IPC handlers behind it, and the lockdown.
//
// During the migration this window points at the Dash dev server, which the
// developer starts separately (`SENSORVIEW_DASH=1 python main.py --debug`).
// That is deliberate and temporary: packaging Python inside Electron would
// mean a PyInstaller bundle as an extraResource, a spawned child, a port
// handshake and orphan cleanup -- all of it thrown away once the renderer is
// native. So this configuration is never packaged; `npm run dist` builds the
// real renderer, which is empty until then.

import { rm, stat, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { app, BrowserWindow, dialog, ipcMain, Menu, screen, shell } from 'electron'

import { DataClient, dataEntry } from './dataClient'
import { allowRoot, registerHandler, registerScheme } from './protocol'
import { videoCacheDir } from '../data/video'
import { SettingsStore } from './store'
import {
  fail,
  ok,
  type CaseView,
  type Result,
  type Settings,
  type WindowBounds
} from '../shared/types'

const here = dirname(fileURLToPath(import.meta.url))

// Where the window points while the UI is still Dash. Unset once the renderer
// is native; `npm run dev` then serves it the usual way.
const DASH_URL = process.env.SENSORVIEW_DASH_URL ?? 'http://127.0.0.1:8050'
const USE_DASH = process.env.SENSORVIEW_DASH === '1'

// Must run before the app is ready.
registerScheme()

// The end-to-end check runs the real app, settings store included, so without
// this it writes to the user's own `settings.json`: a probe that hides a panel
// leaves it hidden for the next real launch, and a probe that opens a case
// leaves that case to be reopened at startup.
if (process.env.SENSORVIEW_SMOKE) {
  app.setPath('userData', join(app.getPath('temp'), 'sensorview-smoke'))
}

const settings = new SettingsStore(app.getPath('userData'))
const data = new DataClient(dataEntry(here))

let win: BrowserWindow | null = null

/** `--sv-bg` for each theme, so the pre-paint surface is the one the
 * renderer is about to draw. Kept in step with `styles/app.css` by hand:
 * main cannot read a stylesheet it never loads. */
const BACKGROUND: Record<string, string> = { dark: '#0a0c0f', light: '#eceef1' }

/** The size a window opens at before it has ever been moved. */
const DEFAULT_SIZE = { width: 1600, height: 1000 }

/**
 * Where to open, given what was stored.
 *
 * A stored rectangle is only honoured if some display still shows enough of
 * it to grab. The laptop case is the one that matters: a window left on a
 * second monitor is at an x no remaining display covers, and restoring it
 * there opens the app somewhere the user cannot see, with no way back but
 * deleting the settings file.
 */
function placement(stored: WindowBounds | null): Electron.Rectangle | typeof DEFAULT_SIZE {
  if (!stored) {
    return DEFAULT_SIZE
  }
  const { x, y, width, height } = stored
  const reachable = screen.getAllDisplays().some((display) => {
    const area = display.workArea
    const across = Math.min(x + width, area.x + area.width) - Math.max(x, area.x)
    const down = Math.min(y + height, area.y + area.height) - Math.max(y, area.y)
    // Enough to see and to drag: a title bar's worth of window, not one
    // pixel of its corner.
    return across > 120 && down > 60
  })
  return reachable ? { x, y, width, height } : DEFAULT_SIZE
}

/** Remember where the window is, debounced: a drag is one write, not sixty. */
function watchBounds(target: BrowserWindow): void {
  let timer: ReturnType<typeof setTimeout> | undefined
  const boundsOf = (): WindowBounds => ({
    // Normal bounds, not current: a maximised window reports the screen, and
    // storing that would make un-maximising a restored window a no-op.
    ...target.getNormalBounds(),
    maximized: target.isMaximized()
  })

  const later = () => {
    clearTimeout(timer)
    timer = setTimeout(() => void settings.set({ bounds: boundsOf() }), 400)
  }

  target.on('resize', later)
  target.on('move', later)
  target.on('maximize', later)
  target.on('unmaximize', later)

  // The last move of a session is the one a debounce loses, because quitting
  // is what follows it. Sync, since nothing here can await.
  target.on('close', () => {
    clearTimeout(timer)
    settings.setNow({ bounds: boundsOf() })
  })
}

function createWindow(theme: string, bounds: WindowBounds | null): void {
  win = new BrowserWindow({
    ...placement(bounds),
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

  if (bounds?.maximized) {
    win.maximize()
  }

  win.once('ready-to-show', () => win?.show())
  watchBounds(win)

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
 * The case the app comes up on.
 *
 * `SENSORVIEW_OPEN_CASE` first -- it is how the end-to-end check drives a real
 * case without a dialog, and how an "open this folder" argument would arrive.
 * Otherwise the most recent case that is still there, which is what makes a
 * relaunch continue where the last session stopped rather than greet the user
 * with an empty window and a file dialog.
 *
 * Resolved here rather than in the renderer because authorising the directory
 * for `sv://` is main's to do: the renderer asking for a case would otherwise
 * be a renderer widening its own read access.
 *
 * Directories that have been moved or deleted are dropped from the recent
 * list on the way past, so a case that no longer exists is asked about once.
 */
async function initialCase(): Promise<Result<string | null>> {
  const named = process.env.SENSORVIEW_OPEN_CASE
  if (named) {
    allowRoot(named)
    return ok(named)
  }

  const stored = await settings.get()
  // `dataPath` is the fallback for a settings file written before there was a
  // recent list.
  const candidates = stored.recent.length > 0 ? stored.recent : [stored.dataPath]
  const gone: string[] = []
  let found: string | null = null
  for (const dir of candidates.filter(Boolean)) {
    if (!(await isDirectory(dir))) {
      gone.push(dir)
      continue
    }
    // A folder that is still there but is no longer a case is passed over
    // rather than forgotten: opening it would come up on an error about a
    // missing manifest, which is a poor thing to greet someone with, but it
    // is still somewhere they were working and the empty window offers it.
    if (await exists(join(dir, 'info.json'))) {
      found = dir
      break
    }
  }

  // Only the ones that are gone, and only once: a case that has been moved
  // should be asked about on one launch, not every launch.
  if (gone.length > 0) {
    await settings.forget(gone)
  }
  if (!found) {
    return ok(null)
  }

  allowRoot(found)
  win?.setTitle(`${app.getName()} — ${found}`)
  return ok(found)
}

async function isDirectory(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isDirectory()
  } catch {
    return false
  }
}

async function exists(path: string): Promise<boolean> {
  try {
    await stat(path)
    return true
  } catch {
    return false
  }
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
  ipcMain.handle('case:initial', () => initialCase())
  ipcMain.handle('file:save', (_event, request) => saveFile(request))
  ipcMain.handle('settings:get', async () => ok(await settings.get()))
  ipcMain.handle('settings:set', async (_event, patch: Partial<Settings>) =>
    ok(await settings.set(patch))
  )
  ipcMain.handle('settings:view', async (_event, dir: string, patch: CaseView) =>
    ok(await settings.rememberView(dir, patch))
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
      // From the defaults every time. The checks leave settings behind -- a
      // cloud switched on, a case in the recent list -- and a run that
      // inherited them would start with the state the next check is about to
      // prove it can reach.
      await rm(join(app.getPath('userData'), 'settings.json'), { force: true })
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
    const stored = await settings.get()
    createWindow(stored.theme, stored.bounds)

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        void settings.get().then((it) => createWindow(it.theme, it.bounds))
      }
    })
  })

  app.on('window-all-closed', () => {
    // Not during the end-to-end check, which opens and closes a probe window
    // per check: the gap between two of them is every window closed, and
    // quitting there takes the run with it -- the next window's load fails
    // with ERR_FAILED, which reads as a broken renderer. The check exits on
    // its own count when it is done.
    if (process.platform !== 'darwin' && !process.env.SENSORVIEW_SMOKE) {
      app.quit()
    }
  })

  app.on('will-quit', () => data.stop())
}
