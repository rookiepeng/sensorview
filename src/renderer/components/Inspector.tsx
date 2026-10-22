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
import { Group, IconButton } from './Controls'
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
  // Why a section is empty, when the reason is not "this log has none".
  const [failed, setFailed] = useState<{ camera?: string; curves?: string }>({})
  // Which one to show, or "" for all of them. A log here carries six curve
  // sidecars and two cameras, so "all" stacks into a long scroll -- the
  // picker is what makes one of them the subject.
  const [oneStream, setOneStream] = useState('')
  const [onePlot, setOnePlot] = useState('')
  // Minimized sections live with the rest of the layout rather than in local
  // state: which panels are away is a property of the window, and a case
  // being opened is the moment a user is least expecting them to come back.
  // The same list the left-hand overlays use -- away is away.
  const hidden = useLayout((s) => s.hidden)
  const toggleHidden = useLayout((s) => s.toggleHidden)
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
    const problems: string[] = []
    void Promise.all(
      stems.map(async (stem) => {
        const result = await window.sensorview.data('logImageStreams', { dir, stem })
        if (!result.ok) {
          problems.push(`${stem}: ${result.error ?? 'could not read the recordings'}`)
        }
        return [stem, result.ok && result.data ? result.data : []] as const
      })
    ).then((pairs) => {
      if (current) {
        setStreams(Object.fromEntries(pairs))
        setFailed((was) => ({ ...was, camera: problems[0] }))
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
        if (!current) {
          return
        }
        if (result.ok && result.data) {
          setSources(result.data)
          setSource(result.data[0]?.id ?? null)
        }
        setFailed((was) => ({
          ...was,
          curves: result.ok ? undefined : (result.error ?? 'could not list the curve sources')
        }))
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
    const trouble: string[] = []
    void Promise.all(
      owners.map(async (stem) => {
        const result = await window.sensorview.data('logCurves', {
          dir,
          stem,
          sourceId: source ?? undefined,
          frameId
        })
        if (!result.ok) {
          trouble.push(`${stem}: ${result.error ?? 'could not read the curves'}`)
        }
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
      setFailed((was) => ({ ...was, curves: trouble[0] ?? was.curves }))
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
    return oneStream ? out.filter((clip) => clip.stream.id === oneStream) : out
  }, [ownerSets, frame, stems, runs, streams, oneStream])

  /** Every stream id the open logs carry, for the picker. */
  const streamChoices = useMemo(() => {
    const seen = new Map<string, string>()
    for (const list of Object.values(streams)) {
      for (const stream of list) {
        if (!seen.has(stream.id)) {
          seen.set(stream.id, stream.label)
        }
      }
    }
    return [...seen.entries()]
  }, [streams])

  /** Plot ids, by the manifest's own id rather than the per-log copy. */
  const plotChoices = useMemo(() => {
    const seen = new Map<string, string>()
    for (const plot of plots) {
      const label = plot.label.includes(' \u00b7 ')
        ? plot.label.slice(plot.label.indexOf(' \u00b7 ') + 3)
        : plot.label
      if (!seen.has(plot.rangeKey)) {
        seen.set(plot.rangeKey, label)
      }
    }
    return [...seen.entries()]
  }, [plots])

  const shownPlots = onePlot ? plots.filter((plot) => plot.rangeKey === onePlot) : plots

  // A section with an empty body says the log has a camera that is not
  // working, rather than that it has none -- which is why this draws nothing
  // when there is nothing. A read that *failed* is the other case, and used
  // to be indistinguishable from it: the panel simply never appeared.
  const broken = failed.camera ?? failed.curves
  if (clips.length === 0 && plots.length === 0 && !broken) {
    return null
  }

  // Each panel is here only if the log has something for it, so the tray
  // offers a way back only to one that went away rather than to one that
  // never existed.
  const panels = [
    { id: 'camera', icon: 'camera-video', title: 'Camera', has: clips.length > 0 },
    { id: 'curves', icon: 'graph-up', title: 'Curves', has: plots.length > 0 }
  ] as const
  const away = panels.filter((panel) => panel.has && hidden.includes(panel.id))

  return (
    <aside className="sv-inspector">
      {/* The same bargain as the rail: each overlay is taken away on its own
          and leaves its icon at the head of the column it came from. */}
      {away.length > 0 && (
        <div className="sv-tray" role="group" aria-label="Hidden panels">
          {away.map((panel) => (
            <IconButton
              key={panel.id}
              icon={panel.icon}
              title={`Show ${panel.title}`}
              onClick={() => toggleHidden(panel.id)}
            />
          ))}
        </div>
      )}

      {/* A read that failed, rather than a log that carries nothing. It gets
          a plate of its own, because the column behind it is the scene. */}
      {broken && (
        <div className="sv-group sv-note">
          <p className="sv-rail-note sv-rail-note-bad">{broken}</p>
        </div>
      )}

      {clips.length > 0 && !hidden.includes('camera') && (
        <Group
          icon="camera-video"
          title="Camera"
          reading={`${clips.length} ${clips.length === 1 ? 'view' : 'views'}`}
          onHide={() => toggleHidden('camera')}
        >
          {/* The pickers sit in the body rather than the head. At 380px a
              head carrying a title, a reading, two selects and a close is
              a row of ellipses. */}
          {streamChoices.length > 1 && (
            <div className="sv-group-controls">
              <select
                value={oneStream}
                aria-label="Camera stream"
                onChange={(event) => setOneStream(event.target.value)}
              >
                <option value="">All streams</option>
                {streamChoices.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          )}
          <CameraPanel clips={clips} />
        </Group>
      )}

      {plots.length > 0 && !hidden.includes('curves') && (
        <Group
          icon="graph-up"
          title="Curves"
          reading={`${shownPlots.length} ${shownPlots.length === 1 ? 'plot' : 'plots'}`}
          onHide={() => toggleHidden('curves')}
        >
          {(plotChoices.length > 1 || sources.length > 1) && (
            <div className="sv-group-controls">
              {plotChoices.length > 1 && (
                <select
                  value={onePlot}
                  aria-label="Curve plot"
                  onChange={(event) => setOnePlot(event.target.value)}
                >
                  <option value="">All plots</option>
                  {plotChoices.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              )}
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
          )}
          <CurvePanel plots={shownPlots} yRanges={yRanges} theme={theme} />
        </Group>
      )}
    </aside>
  )
}
