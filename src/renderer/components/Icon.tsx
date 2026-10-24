// Every glyph in the React chrome, by name.
//
// Lucide, drawn as inline SVG. The names are this app's, not Lucide's, so a
// call site says what the icon is for (`play`, `point-cloud`) and swapping a
// glyph is a one-line change here. The canvas HUD is plain DOM and takes its
// own few icons from the vanilla `lucide` package in `gl/sv_hud.esm.js`.

import type { ComponentProps } from 'react'
import {
  ArrowLeftRight,
  Box,
  Car,
  ChartLine,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleStop,
  Columns2,
  Folder,
  FolderOpen,
  Funnel,
  LoaderCircle,
  Moon,
  Palette,
  Pause,
  Play,
  Radar,
  RulerDimensionLine,
  Share,
  SkipBack,
  SkipForward,
  SlidersHorizontal,
  Square,
  Sun,
  TriangleAlert,
  Video,
  X,
  type LucideIcon
} from 'lucide-react'

const ICONS = {
  'app-mark': Box,
  camera: Video,
  check: Check,
  'chevron-down': ChevronDown,
  'chevron-left': ChevronLeft,
  'chevron-right': ChevronRight,
  'chevron-up': ChevronUp,
  close: X,
  columns: SlidersHorizontal,
  curves: ChartLine,
  display: Palette,
  export: Share,
  filters: Funnel,
  folder: Folder,
  'folder-open': FolderOpen,
  'axis-limits': RulerDimensionLine,
  'layout-one': Square,
  'layout-two': Columns2,
  'next-frame': SkipForward,
  pause: Pause,
  play: Play,
  'point-cloud': Radar,
  'previous-frame': SkipBack,
  reference: Car,
  spinner: LoaderCircle,
  stop: CircleStop,
  swap: ArrowLeftRight,
  'theme-dark': Moon,
  'theme-light': Sun,
  warning: TriangleAlert
} satisfies Record<string, LucideIcon>

export type IconName = keyof typeof ICONS

/** Glyphs drawn solid rather than as an outline, as media controls are. */
const FILLED: ReadonlySet<IconName> = new Set(['play', 'pause', 'previous-frame', 'next-frame'])

/**
 * One glyph, sized to the surrounding text (1em) and drawn in its colour.
 *
 * Decorative by default: most sit inside a control that is already named.
 * Pass `aria-label` (and `role="img"`) for one that carries meaning alone.
 */
export function Icon({
  name,
  className,
  ...rest
}: { name: IconName } & Omit<ComponentProps<LucideIcon>, 'ref'>) {
  const Glyph = ICONS[name]
  const labelled = rest['aria-label'] !== undefined
  return (
    <Glyph
      size="1em"
      strokeWidth={2}
      fill={FILLED.has(name) ? 'currentColor' : 'none'}
      aria-hidden={labelled ? undefined : true}
      focusable="false"
      className={className ? `sv-icon ${className}` : 'sv-icon'}
      {...rest}
    />
  )
}
