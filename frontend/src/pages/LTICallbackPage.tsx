import { useEffect, useState } from 'react'
import { storeAuth } from '../api'
import { Icons } from '../components/ClaudeChatInput'

/**
 * Handles the redirect from the LTI 1.3 launch flow.
 * Reads token + user info from the URL hash fragment,
 * stores auth in localStorage, then redirects to the chat page.
 */
export function LTICallbackPage() {
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    try {
      const hash = window.location.hash.substring(1) // remove '#'
      if (!hash) {
        setError('No authentication data in URL')
        return
      }

      const params = new URLSearchParams(hash)

      const token = params.get('token')
      const userId = params.get('user_id')
      const name = params.get('name')
      const role = params.get('role')

      if (!token || !userId || !name || !role) {
        setError('Missing authentication data from LTI launch')
        return
      }

      // Store auth using existing api.ts helper
      storeAuth(token, {
        id: userId,
        name,
        email: null,
        role,
      })

      // Store launched course ID so ChatPage can auto-select it
      const courseId = params.get('course_id')
      if (courseId) {
        localStorage.setItem('docere_lti_course_id', courseId)
      }

      // Use replace so back button doesn't return to callback
      // Small delay to ensure localStorage write completes
      setTimeout(() => {
        window.location.replace('/')
      }, 50)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process LTI callback')
    }
  }, [])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg-0 text-text-100">
        <div className="text-center p-8">
          <h1 className="text-xl font-serif text-text-200 mb-2">Launch Error</h1>
          <p className="text-sm text-text-400">{error}</p>
          <p className="text-xs text-text-500 mt-4">
            Please try launching Docere from your LMS again.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-0">
      <Icons.Logo className="w-12 h-12 animate-pulse" />
    </div>
  )
}
