// The window before a case is open.
//
// Which used to be a black rectangle with the top bar floating in it: every
// panel hides itself when there is nothing to report -- see `.sv-no-case` in
// app.css -- and what was left said "No case" in a breadcrumb eleven pixels
// tall. A first run has to say what this is and how to get started, and the
// app already knows the one thing that makes that quick: where the user had
// a case last time.
//
// Rendered by `TopBar`, which owns the reading of a case and therefore the
// two things this can do.

/** The folder's own name, which is what the user called the case. */
export function nameOf(dir: string): string {
  return dir.split(/[\\/]/).filter(Boolean).pop() ?? dir
}

/** Everything above it, dimmed: the same path, minus what is already said. */
function parentOf(dir: string): string {
  const parts = dir.split(/[\\/]/).filter(Boolean)
  return parts.slice(0, -1).join('\\')
}

export function Welcome({
  recent,
  busy,
  opening,
  onOpen,
  onPick
}: {
  /** Case directories, newest first, as the settings file has them. */
  recent: string[]
  busy: boolean
  /** The directory being read, while one is. */
  opening: string | null
  onOpen: () => void
  onPick: (dir: string) => void
}) {
  // The shortcut as this platform writes it, since the File menu offers the
  // same command and the two must not disagree.
  const shortcut = window.sensorview.platform === 'darwin' ? '⌘O' : 'Ctrl+O'

  // Reading a case is up to three round trips and a whole-table build. The
  // plate says which one rather than going blank, because the window behind
  // it stays empty until the first frame is drawn.
  if (busy) {
    return (
      <div className="sv-welcome" role="status">
        <div className="sv-welcome-plate sv-hud">
          <i className="bi bi-arrow-repeat sv-spin sv-welcome-mark" aria-hidden="true" />
          <p className="sv-welcome-busy">
            Opening{opening ? <b> {nameOf(opening)}</b> : null} …
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="sv-welcome">
      <div className="sv-welcome-plate sv-hud">
        <i className="bi bi-box sv-welcome-mark" aria-hidden="true" />
        <h1 className="sv-welcome-title">Open a case</h1>
        <p className="sv-welcome-sub">
          A case is a folder of logs and an <code>info.json</code> beside them. Each log
          brings its table, and whatever it has to go with it — point cloud, camera,
          curves, a reference pose.
        </p>

        <button type="button" className="sv-welcome-open" onClick={onOpen}>
          <i className="bi bi-folder2-open" aria-hidden="true" />
          <span>Open case …</span>
          <kbd className="sv-welcome-key">{shortcut}</kbd>
        </button>

        {recent.length > 0 && (
          <div className="sv-welcome-recent">
            <span className="sv-section-label">Recent</span>
            {/* The whole row is the target, and the path under the name is
                what tells two cases of the same name apart -- which is the
                usual shape of these, since a case is named by its folder. */}
            {recent.map((dir) => (
              <button
                key={dir}
                type="button"
                className="sv-welcome-case"
                onClick={() => onPick(dir)}
                title={dir}
              >
                <i className="bi bi-folder" aria-hidden="true" />
                <span className="sv-welcome-case-text">
                  <span className="sv-welcome-case-name">{nameOf(dir)}</span>
                  <span className="sv-welcome-case-path">{parentOf(dir)}</span>
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
