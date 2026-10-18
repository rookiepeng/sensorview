// Combining logs, and what that does to a slider position.
//
// Several logs can be open at once, and combining them concatenates their
// rows. A frame id is then the only thing tying a slider position back to the
// log whose sidecars hold its cloud, pose, curves and video -- and logs are
// free to number their frames the same way, so two of them can land on one
// position.
//
// An id two logs claim collects both rather than resolving to one: the camera
// and curve panels draw a subplot per log, and only the views with room for a
// single answer fall back to the primary. That ordering rule is load-bearing,
// not cosmetic, which is why it is here with tests rather than inline
// wherever it happened to be needed.

/** One unbroken stretch of slider positions a log owns. */
export interface StemRun {
  /** First slider position of the run. */
  start: number
  /** How many positions it covers. */
  count: number
  /**
   * How many of that log's own frames precede the run.
   *
   * This is what makes an interleaved log map onto its own recording end to
   * end. Get it wrong and the video seeks to the wrong moment for every frame
   * after the first gap -- silently, with a picture that still looks
   * plausible.
   */
  localStart: number
}

/**
 * Which logs own each slider position.
 *
 * @param frameIds Frame ids in slider order.
 * @param owners `{frameId: [stem, …]}` read off the selected tables, or null
 *     when a single log is loaded.
 * @param primary The primary log's stem.
 * @returns `ownerSets` -- every log that recorded each position, the primary
 *     first -- and `frameStems`, the head of each set. A position no table
 *     claims falls back to the primary alone: better its sidecars than none.
 */
export function buildFrameOwners(
  frameIds: ArrayLike<number>,
  owners: Record<string, string[]> | null,
  primary: string
): { ownerSets: string[][]; frameStems: string[] } {
  const ownerSets: string[][] = []
  for (let i = 0; i < frameIds.length; i++) {
    const found = owners?.[String(frameIds[i])] ?? null
    let set = found ? [...found] : [primary]
    if (set.includes(primary)) {
      // The primary leads wherever the scan happened to put it, so the head
      // of every set still names the log it named before positions could be
      // shared. Everything keyed on a single owner reads that head.
      set = [primary, ...set.filter((stem) => stem !== primary)]
    }
    ownerSets.push(set)
  }
  return { ownerSets, frameStems: ownerSets.map((set) => set[0]!) }
}

/**
 * Compress one log's slider positions into runs.
 *
 * Runs rather than the raw list because a long log has thousands of
 * positions, and the only question asked of them is which of the log's own
 * frames a slider position is.
 *
 * @param positions Slider positions the log recorded, ascending.
 */
export function stemRuns(positions: ArrayLike<number>): StemRun[] {
  const runs: StemRun[] = []
  let index = 0
  while (index < positions.length) {
    let end = index
    while (end + 1 < positions.length && positions[end + 1] === positions[end]! + 1) {
      end++
    }
    runs.push({
      start: positions[index]!,
      count: end - index + 1,
      localStart: index
    })
    index = end + 1
  }
  return runs
}

/**
 * A slider position as one log's own frame number.
 *
 * @returns The log's frame ordinal, or null when it recorded nothing there --
 *     which is what hides a video rather than seeking it somewhere arbitrary.
 */
export function localFrameFor(runs: StemRun[], position: number): number | null {
  for (const run of runs) {
    if (position >= run.start && position < run.start + run.count) {
      return run.localStart + (position - run.start)
    }
  }
  return null
}

/**
 * The slider positions one log owns, from the owner sets.
 *
 * Every position the log recorded, not only the ones it leads -- a log that
 * shares every id with the primary still has a video of its own to seek.
 */
export function positionsOf(ownerSets: string[][], stem: string): number[] {
  const positions: number[] = []
  for (let i = 0; i < ownerSets.length; i++) {
    if (ownerSets[i]!.includes(stem)) {
      positions.push(i)
    }
  }
  return positions
}
