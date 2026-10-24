// What survives a restart, and what a hand-edited settings file cannot do.
//
// The store is the one piece of state that outlives the process, so the ways
// it goes wrong are the ways that cannot be noticed until the next launch: a
// window restored onto a monitor that is no longer there, a view entry that
// grew without bound, and -- the one this was written for -- two writers of
// the same case's view each saving the other's half away.
//
// `SettingsStore` is in src/main and imports nothing from electron, so it is
// testable here. `placement`, which is the part that does need the screen
// module, is not: its arithmetic is exercised by hand in `src/main/index.ts`.

import { mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { SettingsStore } from '../src/main/store'
import {
  DEFAULT_SETTINGS,
  MAX_VIEWS,
  sanitiseBounds,
  sanitiseView,
  sanitiseViews,
  type Settings
} from '../src/shared/types'

async function store(): Promise<{ store: SettingsStore; file: string }> {
  const dir = await mkdtemp(join(tmpdir(), 'sensorview-settings-'))
  return { store: new SettingsStore(dir), file: join(dir, 'settings.json') }
}

async function onDisk(file: string): Promise<Settings> {
  return JSON.parse(await readFile(file, 'utf8')) as Settings
}

describe('sanitiseBounds', () => {
  it('keeps a rectangle that could have come from a window', () => {
    expect(sanitiseBounds({ x: -1920, y: 40, width: 1600, height: 1000, maximized: true })).toEqual({
      x: -1920,
      y: 40,
      width: 1600,
      height: 1000,
      maximized: true
    })
  })

  it('refuses one that could not', () => {
    // A zero width is a window with nothing in it; a missing y is a file
    // written by something else. Either way the app opens where a first run
    // would, which is the only placement it can be sure of.
    expect(sanitiseBounds({ x: 0, y: 0, width: 0, height: 1000 })).toBeNull()
    expect(sanitiseBounds({ x: 0, width: 1600, height: 1000 })).toBeNull()
    expect(sanitiseBounds({ x: 'left', y: 0, width: 1600, height: 1000 })).toBeNull()
    expect(sanitiseBounds(null)).toBeNull()
  })

  it('rounds, because a window cannot be at half a pixel', () => {
    expect(sanitiseBounds({ x: 10.6, y: 0.2, width: 1600.5, height: 1000 })).toMatchObject({
      x: 11,
      y: 0,
      width: 1601
    })
  })
})

describe('sanitiseView', () => {
  it('keeps the fields that are the type they claim', () => {
    const view = sanitiseView({
      axes: { x: 'X', y: 'Y', z: 'Z', color: 'Speed' },
      colormap: 'Viridis',
      decay: 3,
      overlay: true,
      cloudOn: true,
      sizeVary: false,
      clickToHide: true
    })
    expect(view).toEqual({
      axes: { x: 'X', y: 'Y', z: 'Z', color: 'Speed' },
      colormap: 'Viridis',
      decay: 3,
      overlay: true,
      cloudOn: true,
      sizeVary: false,
      clickToHide: true
    })
  })

  it('reads axes saved under the old spelling of the color key', () => {
    // Settings written before the rename still restore their color column.
    const view = sanitiseView({ axes: { x: 'X', y: 'Y', z: 'Z', colour: 'Speed' } })
    expect(view.axes).toEqual({ x: 'X', y: 'Y', z: 'Z', color: 'Speed' })
  })

  it('drops a colormap the palette does not hold', () => {
    // Which would otherwise draw every point black, with a ramp in the rail
    // saying it was something else.
    expect(sanitiseView({ colormap: 'Chartreuse' }).colormap).toBeUndefined()
    expect(sanitiseView({ colormap: 'Portland' }).colormap).toBe('Portland')
  })

  it('drops a half-named set of axes rather than half-applying it', () => {
    expect(sanitiseView({ axes: { x: 'X', y: 'Y' } }).axes).toBeUndefined()
  })

  it('clamps a decay that would cost a frame build each', () => {
    expect(sanitiseView({ decay: -4 }).decay).toBe(0)
    expect(sanitiseView({ decay: 2.7 }).decay).toBe(3)
    expect(sanitiseView({ decay: Number.NaN }).decay).toBeUndefined()
  })

  it('keeps two panes, and only two', () => {
    expect(sanitiseView({ slots: [{ view: 'violin' }, {}] }).slots).toEqual([
      { view: 'violin' },
      {}
    ])
    expect(sanitiseView({ slots: [{}] }).slots).toBeUndefined()
    expect(sanitiseView({ slots: ['histogram', 'scatter'] }).slots).toBeUndefined()
  })
})

describe('sanitiseViews', () => {
  it('keeps the newest entries when a file has grown past the cap', () => {
    const raw: Record<string, unknown> = {}
    for (let i = 0; i < MAX_VIEWS + 5; i++) {
      raw[`/case/${i}`] = { decay: i }
    }
    const views = sanitiseViews(raw)
    expect(Object.keys(views)).toHaveLength(MAX_VIEWS)
    expect(views['/case/4']).toBeUndefined()
    expect(views[`/case/${MAX_VIEWS + 4}`]).toBeDefined()
  })

  it('answers with nothing for a file that has no map there', () => {
    expect(sanitiseViews(undefined)).toEqual({})
    expect(sanitiseViews(['/case/a'])).toEqual({})
  })
})

describe('SettingsStore', () => {
  it('answers with the defaults on a first run', async () => {
    const { store: settings } = await store()
    expect(await settings.get()).toEqual(DEFAULT_SETTINGS)
  })

  it('reads back what a previous session wrote', async () => {
    const { store: settings, file } = await store()
    await settings.set({ theme: 'light', bounds: sanitiseBounds({ x: 2, y: 3, width: 800, height: 600 }) })
    const next = new SettingsStore(join(file, '..'))
    const stored = await next.get()
    expect(stored.theme).toBe('light')
    expect(stored.bounds).toMatchObject({ x: 2, width: 800, maximized: false })
  })

  it('survives a file somebody edited into nonsense', async () => {
    const { store: settings, file } = await store()
    await writeFile(file, '{ "theme": "light", "bounds": 7, "views": "none", "recent": 3 }', 'utf8')
    expect(await settings.get()).toMatchObject({
      theme: 'light',
      bounds: null,
      views: {},
      recent: []
    })
  })

  it('lets the two writers of one view keep their own halves', async () => {
    // The display panel and the analysis dock each patch a case's entry. Done
    // with `set`, which merges only the top level, the second writer would
    // write the whole map back and take the first's fields with it.
    const { store: settings } = await store()
    await settings.rememberView('/case/a', { colormap: 'Jet', decay: 2 })
    await settings.rememberView('/case/a', { slots: [{ view: 'violin' }, { view: 'scatter' }] })
    const stored = await settings.get()
    expect(stored.views['/case/a']).toEqual({
      colormap: 'Jet',
      decay: 2,
      slots: [{ view: 'violin' }, { view: 'scatter' }]
    })
  })

  it('keeps one case apiece and drops the least recently written', async () => {
    const { store: settings } = await store()
    for (let i = 0; i < MAX_VIEWS; i++) {
      await settings.rememberView(`/case/${i}`, { decay: i })
    }
    // Touching the oldest again moves it to the back of the queue, so the
    // next case in pushes out the one after it instead.
    await settings.rememberView('/case/0', { decay: 9 })
    await settings.rememberView('/case/new', { decay: 1 })
    const stored = await settings.get()
    expect(Object.keys(stored.views)).toHaveLength(MAX_VIEWS)
    expect(stored.views['/case/0']).toEqual({ decay: 9 })
    expect(stored.views['/case/1']).toBeUndefined()
    expect(stored.views['/case/new']).toBeDefined()
  })

  it('forgets a case that is no longer there, view and all', async () => {
    const { store: settings } = await store()
    await settings.remember('/case/gone')
    await settings.remember('/case/here')
    await settings.rememberView('/case/gone', { decay: 4 })
    const stored = await settings.forget(['/case/gone'])
    expect(stored.recent).toEqual(['/case/here'])
    expect(stored.views['/case/gone']).toBeUndefined()
  })

  it('writes without awaiting, for a window that is closing', async () => {
    const { store: settings, file } = await store()
    await settings.set({ theme: 'light' })
    settings.setNow({ bounds: sanitiseBounds({ x: 1, y: 2, width: 900, height: 700 }) })
    // On disk by the time the call returns, which is the whole point of it:
    // the process may be gone a tick later.
    const written = await onDisk(file)
    expect(written.bounds).toMatchObject({ x: 1, width: 900 })
    expect(written.theme).toBe('light')
  })
})
