import { useState, useCallback } from 'react'
import type { MetaAction } from '../api'

export interface MetaChatMessage {
  role: 'user' | 'assistant'
  content: string
  actions?: MetaAction[]
}

interface CourseSummary {
  course_id: string
  course_name: string
  student_count: number
  engagement_breakdown: Record<string, number>
  avg_confusion: number
  top_struggles: string[]
}

export function useMetaChat() {
  const [messages, setMessages] = useState<MetaChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [courseSummaries, setCourseSummaries] = useState<CourseSummary[]>([])

  const sendQuestion = useCallback(async (q: string) => {
    if (!q.trim() || loading) return

    const userMsg: MetaChatMessage = { role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const token = localStorage.getItem('docere_token')

      const res = await fetch('/api/v1/instructor/meta/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          question: q,
          history: messages.slice(-10).map(m => ({ role: m.role, content: m.content })),
        }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        actions: data.actions || [],
      }])

      if (data.course_summaries?.length) {
        setCourseSummaries(data.course_summaries)
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Failed to get a response. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }, [loading, messages])

  return { messages, loading, sendQuestion, courseSummaries }
}
