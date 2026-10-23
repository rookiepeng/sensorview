// Settings, as one JSON file in the app's user-data directory.
//
// Deliberately not a database. The whole of it is three fields, it is written
// when the user changes one, and a corrupt file is recoverable by deleting it.

import { promises as fs, renameSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import {
  DEFAULT_SETTINGS,
  MAX_VIEWS,
  sanitiseBounds,
  sanitiseLayout,
  sanitiseView,
  sanitiseViews,
  type CaseView,
  type Settings
} from '../shared/types'

const MAX_RECENT = 10

export class SettingsStore {
  private readonly file: string
  private cached: Settings | null = null

  constructor(userData: string) {
    this.file = join(userData, 'settings.json')
  }

  /**
   * Read the stored settings, merged over the defaults.
   *
   * A missing or unreadable file is not an error: it is a first run, or a file
   * the user deleted to get back to a working state. Either way the answer is
   * the defaults.
   */
  async get(): Promise<Settings> {
    if (this.cached) {
      return this.cached
    }
    try {
      const raw = JSON.parse(await fs.readFile(this.file, 'utf8')) as Partial<Settings>
      this.cached = {
        ...DEFAULT_SETTINGS,
        ...raw,
        // Never trust the shape of a file a user can edit. Spreading `raw`
        // over the defaults is only right for flat fields: a `layout` from an
        // older file, or a hand-edited one, arrives partial.
        recent: Array.isArray(raw.recent) ? raw.recent.filter((p) => typeof p === 'string') : [],
        layout: sanitiseLayout(raw.layout),
        bounds: sanitiseBounds(raw.bounds),
        views: sanitiseViews(raw.views)
      }
    } catch {
      this.cached = { ...DEFAULT_SETTINGS }
    }
    return this.cached
  }

  async set(patch: Partial<Settings>): Promise<Settings> {
    const next = { ...(await this.get()), ...patch }
    this.cached = next
    await this.write(next)
    return next
  }

  /**
   * Write without awaiting, for a caller that cannot.
   *
   * A window's `close` handler is sync and the process may be gone a tick
   * later, so the last bounds of a session -- a drag to the other monitor,
   * then quit -- would be the one change that never reached the disk.
   */
  setNow(patch: Partial<Settings>): void {
    const next = { ...(this.cached ?? DEFAULT_SETTINGS), ...patch }
    this.cached = next
    const tmp = this.file + '.tmp'
    try {
      writeFileSync(tmp, JSON.stringify(next, null, 2), 'utf8')
      renameSync(tmp, this.file)
    } catch {
      // The window is closing. There is nobody left to tell, and a settings
      // file that kept its previous contents is a working app.
    }
  }

  /** Move a case directory to the front of the recent list. */
  async remember(dir: string): Promise<Settings> {
    const current = await this.get()
    const recent = [dir, ...current.recent.filter((p) => p !== dir)].slice(0, MAX_RECENT)
    return this.set({ recent, dataPath: dir })
  }

  /** Drop case directories from the recent list -- the ones that are gone. */
  async forget(dirs: string[]): Promise<Settings> {
    const current = await this.get()
    const views = { ...current.views }
    for (const dir of dirs) {
      delete views[dir]
    }
    return this.set({ recent: current.recent.filter((p) => !dirs.includes(p)), views })
  }

  /**
   * Merge a patch into one case's view settings.
   *
   * Merged a level deeper than `set` goes, because the two writers of this --
   * the display panel and the analysis dock -- own different fields of the
   * same entry and would otherwise each write the other's away.
   *
   * Capped at `MAX_VIEWS` entries, oldest dropped: this is the one field that
   * grows with use, and a case opened once in a year is not worth a kilobyte
   * of axes forever.
   */
  async rememberView(dir: string, patch: CaseView): Promise<Settings> {
    const current = await this.get()
    const views: Record<string, CaseView> = {}
    // Re-inserted at the end, so insertion order is least-recent first and
    // the slice below drops the cases nobody has opened in a while.
    for (const [key, view] of Object.entries(current.views)) {
      if (key !== dir) {
        views[key] = view
      }
    }
    views[dir] = sanitiseView({ ...current.views[dir], ...patch })
    const entries = Object.entries(views).slice(-MAX_VIEWS)
    return this.set({ views: Object.fromEntries(entries) })
  }

  /**
   * Write via a temporary file and a rename.
   *
   * A rename is atomic on both platforms this ships to, so a crash mid-write
   * leaves the previous settings rather than a truncated file.
   */
  private async write(data: Settings): Promise<void> {
    const tmp = this.file + '.tmp'
    await fs.writeFile(tmp, JSON.stringify(data, null, 2), 'utf8')
    await fs.rename(tmp, this.file)
  }
}
