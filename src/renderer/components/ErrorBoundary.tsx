// A white screen is the one failure mode with nothing to say for itself.
//
// `GlStage` calls `create()` inside an effect with no guard, so a WebGL
// context this machine cannot give -- a remote session, a locked-down driver,
// a GPU reset -- threw out of the effect and took the whole tree down to a
// blank window. There was no boundary anywhere in the app.
//
// This catches the render, not the reads: a failed read is a `Result` with
// `ok: false` and belongs to the panel that asked for it.

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  problem: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  override state: State = { problem: null }

  static getDerivedStateFromError(problem: Error): State {
    return { problem }
  }

  override componentDidCatch(problem: Error, info: ErrorInfo): void {
    // The stack is the useful half and it is not on screen, so it goes where
    // a developer will actually look.
    console.error('SensorView could not render', problem, info.componentStack)
  }

  override render(): ReactNode {
    const { problem } = this.state
    if (!problem) {
      return this.props.children
    }
    return (
      <div className="sv-crash" role="alert">
        <h1>SensorView stopped drawing</h1>
        <p>{problem.message}</p>
        <p className="sv-crash-hint">
          The console holds the stack. If this is a WebGL failure, the scene is the
          likeliest cause — a remote session or a driver without hardware
          acceleration will do it.
        </p>
        <button type="button" className="sv-text-btn" onClick={() => location.reload()}>
          Reload
        </button>
      </div>
    )
  }
}
