// A case directory on disk.
//
// From tests/conftest.py, whose docstring makes the point: a manifest is only
// meaningful next to the files it describes. Sidecars are discovered rather
// than declared, so a test for discovery needs real files in a real folder,
// not a dict.

import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'

let counter = 0

/**
 * Build a case directory.
 *
 * @param manifest Written as `info.json`; null writes no manifest at all,
 *     which is its own case -- a folder with logs and no manifest has to
 *     degrade rather than throw.
 * @param files Sidecar names to create empty. Discovery reads the directory,
 *     not the files, so empty is enough.
 * @param name Directory name, when a test needs to compare two cases.
 * @returns Absolute path to the case directory.
 */
export function makeCase(
  manifest: object | null,
  files: string[] = [],
  name?: string
): string {
  counter += 1
  const root = mkdtempSync(join(tmpdir(), 'sv-case-'))
  const caseDir = name ? join(root, name) : join(root, `case_${counter}`)
  mkdirSync(caseDir, { recursive: true })

  if (manifest) {
    writeFileSync(join(caseDir, 'info.json'), JSON.stringify(manifest, null, 4), 'utf8')
  }
  for (const file of files) {
    const path = join(caseDir, file)
    mkdirSync(dirname(path), { recursive: true })
    writeFileSync(path, '', 'utf8')
  }
  return caseDir
}

/** The smallest v2 manifest that loads. */
export const V2_MANIFEST = {
  manifest_version: 2,
  table: { slider: 'Frame', keys: {} },
  cloud: { suffix: '.cloud.h5' },
  curve: { suffix: '.curve.h5' },
  image: {},
  reference: {}
}
