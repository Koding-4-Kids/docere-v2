import { useState } from 'react'

/** Detects whether the app is running inside an iframe (e.g. LMS embed). */
export function useEmbedded(): boolean {
  const [isEmbedded] = useState(() => {
    try {
      return window.self !== window.top
    } catch {
      // Cross-origin iframe — we ARE embedded but can't access parent
      return true
    }
  })
  return isEmbedded
}
