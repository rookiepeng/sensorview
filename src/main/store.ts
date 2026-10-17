// Settings, as one JSON file in the app's user-data directory.
//
// Deliberately not a database. The whole of it is three fields, it is written
// when the user changes one, and a corrupt file is recoverable by deleting it.

import { promises as fs } from 'node:fs'
import { join } from 'node:path'

import { DEFAULT_SETTINGS, type Settings } from '../shared/types'

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
        // Never trust the shape of a file a user can edit.
        recent: Array.isArray(raw.recent) ? raw.recent.filter((p) => typeof p === 'string') : []
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

  /** Move a case directory to the front of the recent list. */
  async remember(dir: string): Promise<Settings> {
    const current = await this.get()
    const recent = [dir, ...current.recent.filter((p) => p !== dir)].slice(0, MAX_RECENT)
    return this.set({ recent, dataPath: dir })
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
