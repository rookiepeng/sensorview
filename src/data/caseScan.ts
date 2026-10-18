// What is in a case directory.
//
// A case is a folder of logs, and a log is a table file with sidecars
// associated by basename. Nothing is declared: adding a log is dropping files
// in the folder, so opening a case means reading the directory and asking the
// manifest which of what is there is a table.

import { promises as fs } from 'node:fs'
import { join } from 'node:path'

import { Manifest, tableSidecarSuffixes } from './manifest'

export interface LogSummary {
  /** Stem the sidecars are keyed on. */
  stem: string
  /** Table file, absolute. */
  file: string
  hasCloud: boolean
  hasCurve: boolean
  hasImage: boolean
  hasReference: boolean
}

export interface CaseSummary {
  dir: string
  name: string
  frameKey: string
  logs: LogSummary[]
  /** Column metadata driving the filters and hover text. */
  keys: Record<string, unknown>
}

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

/**
 * Read a case directory.
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

  const names = (await fs.readdir(dir)).sort()
  const logs: LogSummary[] = []

  for (const name of names) {
    const lower = name.toLowerCase()
    if (!lower.endsWith(suffix)) {
      continue
    }
    if (excluded.some((other) => lower.endsWith(other))) {
      continue
    }

    const file = join(dir, name)
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
    keys: manifest.keys
  }
}
