// The part of an export every menu shares: the save, and what it says after.
//
// The top bar's menu and the figure menus on the dock and the curves each
// hold their own, so a note says which export it is about by where it is.

import { useEffect, useState } from 'react'

/** Long enough to read a filename, short enough not to outlive its moment. */
const NOTE_MS = 6000

export type SaveFilters = Array<{ name: string; extensions: string[] }>

export function useExport() {
  const [busy, setBusy] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  // "Saved foo.csv" used to sit in the top bar until the next export, which
  // made a stale success look like a live one.
  useEffect(() => {
    if (!note) {
      return
    }
    const timer = setTimeout(() => setNote(null), NOTE_MS)
    return () => clearTimeout(timer)
  }, [note])

  async function save(
    name: string,
    data: string,
    encoding: 'utf8' | 'base64',
    filters?: SaveFilters
  ) {
    const result = await window.sensorview.saveFile({
      suggestedName: name,
      data,
      encoding,
      filters
    })
    if (!result.ok) {
      setNote(result.error ?? 'could not write the file')
      return
    }
    // A dismissed dialog is not a failure, and saying "cancelled" where the
    // user cancelled is noise.
    setNote(result.data ? `Saved ${name}` : null)
  }

  async function run(label: string, job: () => Promise<void>) {
    setBusy(label)
    setNote(null)
    try {
      await job()
    } catch (problem) {
      setNote(problem instanceof Error ? problem.message : String(problem))
    } finally {
      setBusy(null)
    }
  }

  return { busy, setBusy, note, save, run }
}
