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

import { useEffect, useMemo, useRef, useState } from 'react'

import { positionsOf, stemRuns } from '@shared/logs'
import type { CurvePlot, ImageStream } from '@shared/types'

import { CameraPanel, type ClipSource } from './CameraPanel'
import { Group, IconButton, SelectMenu } from './Controls'
import {
  Group as Panes,
  Panel,
  Separator,
  type PanelImperativeHandle
} from 'react-resizable-panels'
import { CurvePanel, growYRanges } from './CurvePanel'
import { pixelsOf, useLayout, type Presence } from '../layout'
import { useStore } from '../store'
import { useTheme } from '../useTheme'

/**
 * The floor for either card, which is also the other one's ceiling.
 *
 * Both are "a picture or a plot still worth looking at", which is what the
 * pair of bounds in `layout.ts` used to say -- one of them by measuring the
 * stack and subtracting. Two floors say it without measuring anything.
 */
const CARD_MIN = 140

export function Inspector({
  onPresence
}: {
  /** Told which of its three shapes the column is in, whenever that changes. */
  onPresence?: (presence: Presence) => void
} = {}) {
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
  const camera = useRef<PanelImperativeHandle | null>(null)
  // The split's own box, for turning its layout back into pixels.
  const split = useRef<HTMLDivElement | null>(null)
  const cameraH = useLayout((s) => s.cameraH)
  // Read once, on purpose. `defaultSize` is where the panel starts, and
  // feeding the stored height back into it closes a loop: the drag writes
  // the store, the store re-renders this with a new `defaultSize`, the group
  // lays out again and writes the store again. React calls that "maximum
  // update depth exceeded" and the error boundary takes the window.
  const startAt = useRef(cameraH)
  const setSize = useLayout((s) => s.setSize)
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

  // Which shape the column takes, for the panel holding it to size itself
  // to. Reported rather than worked out by the shell, because whether there
  // is anything to show depends on reads only this component makes -- and
  // reported from here, above the early return, because that is the case
  // the shell most needs to hear about.
  const presence: Presence =
    clips.length === 0 && plots.length === 0 && !broken
      ? 'none'
      : broken ||
          (clips.length > 0 && !hidden.includes('camera')) ||
          (plots.length > 0 && !hidden.includes('curves'))
        ? 'cards'
        : 'tray'
  useEffect(() => {
    onPresence?.(presence)
  }, [presence, onPresence])

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
  const showCamera = clips.length > 0 && !hidden.includes('camera')
  const showCurves = plots.length > 0 && !hidden.includes('curves')
  // Both cards, so there is a division to make and a handle to make it with.
  const dividing = showCamera && showCurves

  return (
    <aside className="sv-inspector">
      <div className="sv-stack">
      {/* A read that failed, rather than a log that carries nothing. It gets
          a plate of its own, because the column behind it is the scene. */}
      {broken && (
        <div className="sv-group sv-note">
          <p className="sv-rail-note sv-rail-note-bad">{broken}</p>
        </div>
      )}

      {/* One group whatever is showing, each card in a panel of its own that
          comes and goes with it. It used to be a group for two cards and a
          bare card for one, which put a card under a different parent the
          moment the other was hidden -- so React threw it away and built it
          again: hiding the camera rebuilt every curve plot, dropped any zoom on
          them, and left Plotly a redraw to run against a figure that no longer
          existed. A group of one panel is allowed; it simply has no handle. */}
      {(showCamera || showCurves) && (
        <Panes
          orientation="vertical"
          className="sv-inspector-split"
          elementRef={split}
          // `height: 100%` is the library's own, and against a stack whose
          // height is its content that resolves to nothing useful. These
          // three say "take what the column has left", as the two cards
          // used to say for themselves.
          style={{ height: 'auto', flex: '1 1 auto', minHeight: 0 }}
          onLayoutChanged={(layout, meta) => {
            // Only what a person did. Every layout reaches this -- mount and
            // the double-click reset included -- and only a drag or a key on
            // the handle is a height someone chose.
            if (!meta.isUserInteraction) {
              return
            }
            // From the layout, not the handle, which is a step behind here.
            const tall = pixelsOf(layout, 'camera', split.current, 'height')
            if (tall === null) {
              return
            }
            // And only on a real change, so a layout that rounds to the
            // height already stored writes nothing.
            const px = Math.round(tall)
            if (px !== cameraH) {
              setSize('cameraH', px)
            }
          }}
        >
          {showCamera && (
            <Panel
              key="camera"
              id="camera"
              panelRef={camera}
              className="sv-inspector-pane"
              // The library gives every panel `overflow: auto`. These hold a
              // 16:9 still and a stack of plots, both of which size themselves
              // against their box, so a scrollbar here is the box giving up.
              style={{ overflow: 'visible' }}
              defaultSize={startAt.current ?? '50'}
              minSize={CARD_MIN}
            >
            {showCamera && (
              <Group
                className="sv-card-camera"
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
                    <SelectMenu
                      value={oneStream}
                      label="Camera stream"
                      choices={[
                        { value: '', label: 'All streams' },
                        ...streamChoices.map(([id, label]) => ({ value: id, label }))
                      ]}
                      onChange={setOneStream}
                    />
                  </div>
                )}
                <CameraPanel clips={clips} />
              </Group>
            )}

            </Panel>
          )}

          {/* Double-click is the library's, but what it restores is the
              `defaultSize` -- which is the dragged height, so it would
              restore nothing. Ours clears the stored number instead, which
              is what "back to the stylesheet's own answer" meant. */}
          {dividing && (
            <Separator
              className="sv-splitter sv-splitter-row"
              disableDoubleClick
              onDoubleClick={() => {
                camera.current?.resize('50')
                setSize('cameraH', null)
              }}
            />
          )}

          {showCurves && (
            <Panel
              key="curves"
              id="curves"
              className="sv-inspector-pane"
              style={{ overflow: 'visible' }}
              minSize={CARD_MIN}
            >
            {showCurves && (
              <Group
                className="sv-card-curves"
                icon="graph-up"
                title="Curves"
                reading={`${shownPlots.length} ${shownPlots.length === 1 ? 'plot' : 'plots'}`}
                onHide={() => toggleHidden('curves')}
              >
                {(plotChoices.length > 1 || sources.length > 1) && (
                  <div className="sv-group-controls">
                    {plotChoices.length > 1 && (
                      <SelectMenu
                        value={onePlot}
                        label="Curve plot"
                        choices={[
                          { value: '', label: 'All plots' },
                          ...plotChoices.map(([id, label]) => ({ value: id, label }))
                        ]}
                        onChange={setOnePlot}
                      />
                    )}
                    {/* Only when there is a choice: one sidecar needs no picker,
                        and a select with a single option is furniture. */}
                    {sources.length > 1 && (
                      <SelectMenu
                        value={source ?? ''}
                        label="Curve source"
                        choices={sources.map((entry) => ({ value: entry.id, label: entry.label }))}
                        onChange={setSource}
                      />
                    )}
                  </div>
                )}
                <CurvePanel plots={shownPlots} yRanges={yRanges} theme={theme} />
              </Group>
            )}
            </Panel>
          )}
        </Panes>
      )}
      </div>

      {/* Beside the cards, not above them: an icon stacked on top pushes
          the panel down and reads as part of it. On the edge facing the
          scene it is a tab on the panel's side, which is what it is. */}
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
    </aside>
  )
}
