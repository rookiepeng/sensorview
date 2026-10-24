// Which theme the document is in.
//
// The attribute on <html> is the single source: the scene re-reads its palette
// from it, the CSS switches on it, and anything that has to pass a color into
// a library -- Plotly, which has no idea the attribute exists -- reads it
// through here rather than keeping its own copy in step.

import { useEffect, useState } from 'react'

export type ThemeName = 'dark' | 'light'

function current(): ThemeName {
  return document.documentElement.getAttribute('data-bs-theme') === 'light' ? 'light' : 'dark'
}

export function useTheme(): ThemeName {
  const [theme, setTheme] = useState<ThemeName>(current)

  useEffect(() => {
    const read = () => setTheme(current())
    read()
    const observer = new MutationObserver(read)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-bs-theme']
    })
    return () => observer.disconnect()
  }, [])

  return theme
}
