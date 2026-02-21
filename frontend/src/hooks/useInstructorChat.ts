import { useState, useCallback, useEffect, useRef } from 'react'
import type { InstructorWidget, SourceRef, SourceFilters } from '../api'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  widgets?: InstructorWidget[]
  sources?: SourceRef[]
}

interface TaggedStudent {
  id: string
  name: string
}

export function useInstructorChat(courseId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [sourceFilters, setSourceFilters] = useState<SourceFilters>({ profiles: true, mastery: true })

  // Store messages per course so switching back restores history
  const historyRef = useRef<Record<string, ChatMessage[]>>({})
  const prevCourseRef = useRef(courseId)

  useEffect(() => {
    if (prevCourseRef.current !== courseId) {
      // Save current messages for the old course
      historyRef.current[prevCourseRef.current] = messages
      // Restore messages for the new course (or start fresh)
      setMessages(historyRef.current[courseId] || [])
      prevCourseRef.current = courseId
    }
  }, [courseId, messages])

  const sendQuestion = useCallback(async (q: string, taggedStudents: TaggedStudent[]) => {
    if (!q.trim() || loading) return

    const userMsg: ChatMessage = { role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const token = localStorage.getItem('docere_token')

      let question = q
      if (taggedStudents.length > 0) {
        const studentNames = taggedStudents.map(s => `"${s.name}" (ID: ${s.id})`).join(', ')
        const focusWord = taggedStudents.length === 1 ? 'this student' : 'these students'
        question = `[Context: The instructor is asking about ${focusWord}: ${studentNames}. Focus your answer on ${focusWord}.]\n\n${q}`
      }

      const res = await fetch(`/api/v1/instructor/dashboard/${courseId}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          question,
          history: messages.slice(-10).map(m => ({ role: m.role, content: m.content })),
          source_filters: sourceFilters,
        }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        widgets: data.widgets || [],
        sources: data.sources || [],
      }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Failed to get a response. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }, [courseId, loading, messages, sourceFilters])

  return { messages, loading, sendQuestion, sourceFilters, setSourceFilters }
}
