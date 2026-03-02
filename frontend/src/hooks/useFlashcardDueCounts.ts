import { useState, useEffect } from 'react'
import { getDueCounts } from '../api'

export function useFlashcardDueCounts(pollingInterval = 60000) {
  const [dueCounts, setDueCounts] = useState<Map<string, number>>(new Map())

  useEffect(() => {
    let active = true

    const fetchCounts = () => {
      getDueCounts()
        .then(counts => {
          if (!active) return
          const map = new Map(counts.map(c => [c.course_id, c.due_count]))
          setDueCounts(map)
        })
        .catch(() => {})
    }

    fetchCounts()
    const interval = setInterval(fetchCounts, pollingInterval)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [pollingInterval])

  return dueCounts
}
