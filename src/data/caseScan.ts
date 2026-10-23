// What is in a case directory.
//
// A case is a folder of logs, and a log is a table file with sidecars
// associated by basename. Nothing is declared: adding a log is dropping files
// in the folder (or in any subfolder under it), so opening a case means walking
// the directory tree and asking the manifest which of what is there is a table.

import { promises as fs } from 'node:fs'
import { join, relative, sep } from 'node:path'

import type { CaseSummary, CloudDisplay, LogSummary } from '../shared/types'

import { Manifest, tableSidecarSuffixes } from './manifest'

async function exists(path: string | null): Promise<boolean> {
  if (!path) {
    return false
  }
  try {
    await fs.access(path)
    return true
  } catch {
    return false
  }
}

/** How deep below the case folder to look for logs. */
const MAX_DEPTH = 8

/**
 * Every file under `dir`, depth first, sorted by path relative to `dir`.
 *
 * Hidden folders (`.git`, `.cache`, ...) are skipped, and symlinked folders are
 * not followed, so a link back up the tree cannot loop.
 */
async function listFiles(dir: string, depth = 0): Promise<string[]> {
  let entries
  try {
    entries = await fs.readdir(dir, { withFileTypes: true })
  } catch {
    // An unreadable subfolder hides its own logs, not the rest of the case.
    return []
  }

  const files: string[] = []
  for (const entry of entries) {
    const path = join(dir, entry.name)
    if (entry.isFile()) {
      files.push(path)
    } else if (entry.isDirectory() && !entry.name.startsWith('.') && depth < MAX_DEPTH) {
      files.push(...(await listFiles(path, depth + 1)))
    }
  }
  return files
}

/**
 * Read a case directory.
 *
 * Tables are found anywhere under the case folder. A table in a subfolder gets
 * that folder as a stem prefix (`run_1/radar`), so runs that reuse the same
 * file names stay apart and each finds the sidecars beside it.
 *
 * Logs are found by extension and then filtered: the reference pose is Parquet
 * like the table, so without that step it would be offered as a log -- one
 * with none of the columns the manifest describes.
 *
 * @throws ManifestError if the directory has no readable manifest.
 */
export async function scanCase(dir: string): Promise<CaseSummary> {
  const manifest = await Manifest.load(dir)
  const suffix = manifest.tableSuffix.toLowerCase()
  const excluded = await tableSidecarSuffixes(dir)

  const files = await listFiles(dir)
  const byPath = (file: string): string => relative(dir, file).split(sep).join('/')
  files.sort((a, b) => (byPath(a) < byPath(b) ? -1 : byPath(a) > byPath(b) ? 1 : 0))
  const logs: LogSummary[] = []

  for (const file of files) {
    const lower = file.toLowerCase()
    if (!lower.endsWith(suffix)) {
      continue
    }
    if (excluded.some((other) => lower.endsWith(other))) {
      continue
    }

    const stem = manifest.stemOf(file)
    logs.push({
      stem,
      file,
      hasCloud: await exists(manifest.cloudPath(stem)),
      hasCurve: await manifest.hasCurve(stem),
      hasImage: await manifest.hasImage(stem),
      hasReference: await exists(manifest.referencePath(stem))
    })
  }

  return {
    dir,
    name: manifest.name,
    frameKey: manifest.frameKey,
    logs,
    keys: manifest.keys,
    cloud: manifest.cloud ? (manifest.cloudDisplay() as unknown as CloudDisplay) : null
  }
}
