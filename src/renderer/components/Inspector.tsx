// The right-hand dock: what the open frame looks like, beside what it is.
//
// Two sections, each present only when something fills it. A section with an
// empty body is worse than no section: it says the log has a camera that is
// not working, rather than that it has none.
//
// These are the two panels that show every log that recorded a position
// rather than only the one that leads it. Combining logs collapses shared
// frame ids onto one slider position, and the whole point of keeping the
// owner set rather than a single stem is that these two can draw all of them;
// the cloud, the pose and the exports have room for one answer and take the
// head of the set.

import { useEffect, useMemo, useState } from 'react'

import { positionsOf, stemRuns } from '@shared/logs'
import type { CurvePlot, ImageStream } from '@shared/types'

import { CameraPanel, type ClipSource } from './CameraPanel'
import { PanelHead } from './Controls'
import { CurvePanel, growYRanges } from './CurvePanel'
import { useLayout } from '../layout'
import { useStore } from '../store'
import { useTheme } from '../useTheme'

export function Inspector() {
  const dir = useStore((s) => s.dir)
  const stems = useStore((s) => s.stems)
  const ownerSets = useStore((s) => s.ownerSets)
  const table = useStore((s) => s.table)
  const frame = useStore((s) => s.frame)

  const [streams, setStreams] = useState<Record<string, ImageStream[]>>({})
  const [sources, setSources] = useState<Array<{ id: string; label: string }>>([])
  const [source, setSource] = useState<string | null>(null)
  const [plots, setPlots] = useState<CurvePlot[]>([])
  const [yRanges, setYRanges] = useState<Record<string, [number, number]>>({})
  const collapsed = useLayout((s) => s.inspectorCollapsed)
  const toggle = useLayout((s) => s.toggle)
  const theme = useTheme()

  // Which slider positions each log owns, compressed into runs. Derived once
  // per load rather than per frame: a long log has thousands of positions and
  // the only question asked of them is which of its own frames this is.
  const runs = useMemo(() => {
    const out: Record<string, ReturnType<typeof stemRuns>> = {}
    for (const stem of stems) {
      out[stem] = stemRuns(positionsOf(ownerSets, stem))
    }
    return out
  }, [stems, ownerSets])

  // Recordings are resolved once per log, not per frame: resolving can
  // transcode, and the result is a property of the file.
  useEffect(() => {
    setStreams({})
    if (!dir || stems.length === 0) {
      return
    }
    let current = true
    void Promise.all(
      stems.map(async (stem) => {
        const result = await window.sensorview.data('logImageStreams', { dir, stem })
        return [stem, result.ok && result.data ? result.data : []] as const
      })
    ).then((pairs) => {
      if (current) {
        setStreams(Object.fromEntries(pairs))
      }
    })
    return () => {
      current = false
    }
  }, [dir, stems])

  // Which curve sidecars the open logs carry, as a union: combined logs need
  // not carry the same sensors, and listing only the primary's would hide a
  // sidecar the second log was combined in for.
  useEffect(() => {
    setSources([])
    setSource(null)
    if (!dir || stems.length === 0) {
      return
    }
    let current = true
    void window.sensorview
      .data('logCurveSources', { dir, stems })
      .then((result) => {
        if (current && result.ok && result.data) {
          setSources(result.data)
          setSource(result.data[0]?.id ?? null)
        }
      })
    return () => {
      current = false
    }
  }, [dir, stems])

  // Ranges reset with the load and with the sensor, because a different
  // sidecar's values have nothing to do with the last one's.
  useEffect(() => {
    setYRanges({})
    setPlots([])
  }, [dir, stems, source])

  // Curves are per frame, and per log that recorded it.
  useEffect(() => {
    const frameId = table?.frameIds[frame]
    const owners = ownerSets[frame] ?? stems
    if (!dir || owners.length === 0 || frameId === undefined) {
      return
    }
    let current = true
    void Promise.all(
      owners.map(async (stem) => {
        const result = await window.sensorview.data('logCurves', {
          dir,
          stem,
          sourceId: source ?? undefined,
          frameId
        })
        const found = result.ok && result.data ? result.data : []
        // Named by their log whenever more than one is loaded -- not only
        // when two share this position. Scrubbing across the boundary
        // between two logs otherwise changes which log is on screen with
        // nothing on screen saying so.
        return stems.length > 1
          ? found.map((plot) => ({
              ...plot,
              id: `${stem}:${plot.id}`,
              // `rangeKey` deliberately left as the plot's own id, so every
              // log's band of a plot shares one y range.
              label: `${stem} · ${plot.label}`
            }))
          : found
      })
    ).then((perLog) => {
      if (!current) {
        return
      }
      const all = perLog.flat()
      setPlots(all)
      setYRanges((ranges) => growYRanges(ranges, all))
    })
    return () => {
      // Scrubbing starts a read per position; only the newest may land.
      current = false
    }
  }, [dir, stems, ownerSets, table, frame, source])

  // One clip per log that recorded this position, each carrying its own frame
  // number within its own recording. A log that recorded nothing here is
  // absent rather than seeked somewhere arbitrary.
  const clips = useMemo<ClipSource[]>(() => {
    const owners = ownerSets[frame] ?? stems
    const out: ClipSource[] = []
    for (const stem of owners) {
      const own = runs[stem]
      if (!own) {
        continue
      }
      const positions = own.reduce((total, run) => total + run.count, 0)
      let local: number | null = null
      for (const run of own) {
        if (frame >= run.start && frame < run.start + run.count) {
          local = run.localStart + (frame - run.start)
          break
        }
      }
      if (local === null) {
        continue
      }
      for (const stream of streams[stem] ?? []) {
        out.push({
          key: `${stem}:${stream.id}`,
          // Named by the log whenever several are loaded, by the camera
          // when one is: that is the thing that tells the pictures apart,
          // and it is what says which log a position belongs to.
          label: stems.length > 1 ? `${stem} · ${stream.label}` : stream.label,
          stream,
          local,
          localTotal: positions
        })
      }
    }
    return out
  }, [ownerSets, frame, stems, runs, streams])

  if (clips.length === 0 && plots.length === 0) {
    return null
  }

  return (
    <aside className={`sv-inspector${collapsed ? ' sv-collapsed' : ''}`}>
      <PanelHead
        icon="binoculars"
        title="Inspector"
        collapse={{
          collapsed,
          onToggle: () => toggle('inspectorCollapsed'),
          subject: 'inspector',
          edge: 'right'
        }}
      />

      <div className="sv-inspector-body">
        {clips.length > 0 && (
          <section className="sv-subsection" id="subview-camera-section">
            <div className="sv-subsection-head">
              <span className="sv-section-label">Camera</span>
            </div>
            <div className="sv-subsection-body">
              <CameraPanel clips={clips} />
            </div>
          </section>
        )}

        {plots.length > 0 && (
          <section className="sv-subsection sv-subsection--grow">
            <div className="sv-subsection-head">
              <span className="sv-section-label">Curves</span>
              {/* Only when there is a choice: one sidecar needs no picker,
                  and a select with a single option is furniture. */}
              {sources.length > 1 && (
                <select
                  value={source ?? ''}
                  aria-label="Curve source"
                  onChange={(event) => setSource(event.target.value)}
                >
                  {sources.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.label}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="sv-subsection-body">
              <CurvePanel plots={plots} yRanges={yRanges} theme={theme} />
            </div>
          </section>
        )}
      </div>
    </aside>
  )
}
