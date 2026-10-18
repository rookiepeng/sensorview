// The right-hand dock: what the open frame looks like, beside what it is.
//
// Two sections, each present only when the log has something to fill it. A
// section with an empty body is worse than no section: it says the log has a
// camera that is not working, rather than that it has none.

import { useEffect, useState } from 'react'

import type { CurvePlot, ImageStream } from '@shared/types'

import { CameraPanel } from './CameraPanel'
import { CurvePanel, growYRanges } from './CurvePanel'
import { useStore } from '../store'

export function Inspector() {
  const dir = useStore((s) => s.dir)
  const stem = useStore((s) => s.stem)
  const table = useStore((s) => s.table)
  const frame = useStore((s) => s.frame)
  const frameCount = useStore((s) => s.frameCount)

  const [streams, setStreams] = useState<ImageStream[]>([])
  const [plots, setPlots] = useState<CurvePlot[]>([])
  const [yRanges, setYRanges] = useState<Record<string, [number, number]>>({})
  const [collapsed, setCollapsed] = useState(false)
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')

  // Recordings are resolved once per log, not per frame: resolving can
  // transcode, and the result is a property of the file.
  useEffect(() => {
    setStreams([])
    if (!dir || !stem) {
      return
    }
    let current = true
    void window.sensorview.data('logImageStreams', { dir, stem }).then((result) => {
      if (current && result.ok && result.data) {
        setStreams(result.data)
      }
    })
    return () => {
      current = false
    }
  }, [dir, stem])

  // The curves are per frame. Ranges reset with the log, because a new log's
  // values have nothing to do with the last one's.
  useEffect(() => {
    setYRanges({})
    setPlots([])
  }, [dir, stem])

  useEffect(() => {
    const frameId = table?.frameIds[frame]
    if (!dir || !stem || frameId === undefined) {
      return
    }
    let current = true
    void window.sensorview
      .data('logCurves', { dir, stem, frameId })
      .then((result) => {
        if (!current || !result.ok || !result.data) {
          return
        }
        setPlots(result.data)
        setYRanges((ranges) => growYRanges(ranges, result.data!))
      })
    return () => {
      // Scrubbing starts a read per position; only the newest may land.
      current = false
    }
  }, [dir, stem, table, frame])

  useEffect(() => {
    const read = () =>
      setTheme(
        document.documentElement.getAttribute('data-bs-theme') === 'light' ? 'light' : 'dark'
      )
    read()
    const observer = new MutationObserver(read)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-bs-theme']
    })
    return () => observer.disconnect()
  }, [])

  // Nothing to inspect: no dock at all, rather than an empty one taking 380px
  // from the scene.
  if (streams.length === 0 && plots.length === 0) {
    return null
  }

  return (
    <aside className={`sv-inspector${collapsed ? ' sv-collapsed' : ''}`}>
      <div className="sv-panel-head">
        <span className="sv-panel-title">
          <i className="bi bi-binoculars" /> Inspector
        </span>
        <button
          type="button"
          className="sv-icon-btn"
          onClick={() => setCollapsed((on) => !on)}
          aria-label={collapsed ? 'Expand the inspector' : 'Collapse the inspector'}
          title={collapsed ? 'Expand' : 'Collapse'}
        >
          <i className={`bi bi-chevron-${collapsed ? 'left' : 'right'}`} />
        </button>
      </div>

      <div className="sv-inspector-body">
        {streams.length > 0 && (
          <section className="sv-subsection" id="subview-camera-section">
            <div className="sv-subsection-head">
              <span className="sv-section-label">Camera</span>
            </div>
            <div className="sv-subsection-body">
              <CameraPanel streams={streams} frame={frame} frameCount={frameCount} />
            </div>
          </section>
        )}

        {plots.length > 0 && (
          <section className="sv-subsection sv-subsection--grow">
            <div className="sv-subsection-head">
              <span className="sv-section-label">Curves</span>
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
