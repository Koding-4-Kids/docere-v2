interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  if (role === 'user') {
    return (
      <div className="flex justify-end mb-4 animate-fade-in">
        <div className="max-w-[75%] px-4 py-3 rounded-2xl rounded-br-md bg-accent text-white text-sm leading-relaxed">
          {content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start mb-4 animate-fade-in">
      <div className="max-w-[75%] px-4 py-3 rounded-2xl rounded-bl-md bg-bg-200 text-text-100 text-sm leading-relaxed">
        {content}
      </div>
    </div>
  )
}
