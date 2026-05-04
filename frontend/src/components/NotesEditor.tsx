import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Highlight from '@tiptap/extension-highlight'
import TaskList from '@tiptap/extension-task-list'
import TaskItem from '@tiptap/extension-task-item'
import React, { useEffect, useCallback, useRef } from 'react'

interface NotesEditorProps {
  content: string
  onChange: (content: string) => void
  onClose: () => void
  isAgentWriting?: boolean
  agentWrittenSection?: string | null
  onDismissAgentSection?: () => void
  onExplain?: () => void
  onRewrite?: () => void
  isExpanded?: boolean
  onToggleExpand?: () => void
}

// Inline Docere logo SVG
function DocereLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" className={className}>
      <defs><ellipse id="nl" cx="100" cy="100" rx="90" ry="22"/></defs>
      <g fill="currentColor" fillRule="evenodd">
        <use href="#nl" transform="rotate(0 100 100)"/>
        <use href="#nl" transform="rotate(45 100 100)"/>
        <use href="#nl" transform="rotate(90 100 100)"/>
        <use href="#nl" transform="rotate(135 100 100)"/>
      </g>
    </svg>
  )
}

export function NotesEditor({
  content,
  onChange,
  onClose,
  isAgentWriting = false,
  agentWrittenSection = null,
  onDismissAgentSection,
  onExplain,
  onRewrite,
  isExpanded = false,
  onToggleExpand,
}: NotesEditorProps) {
  const isInternalUpdate = useRef(false)

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        bulletList: { keepMarks: true },
        orderedList: { keepMarks: true },
      }),
      Placeholder.configure({
        placeholder: 'Start typing your notes... Use markdown shortcuts like # for headings, - for lists, or **bold**',
      }),
      Highlight,
      TaskList,
      TaskItem.configure({ nested: true }),
    ],
    content: content || '',
    editorProps: {
      attributes: {
        class: 'notes-tiptap',
      },
    },
    onUpdate: ({ editor }) => {
      isInternalUpdate.current = true
      onChange(editor.getHTML())
    },
  })

  // Sync external content changes (e.g. agent writes notes)
  useEffect(() => {
    if (!editor) return
    if (isInternalUpdate.current) {
      isInternalUpdate.current = false
      return
    }
    if (content && content !== '<p></p>') {
      editor.commands.setContent(content, false)
    }
  }, [content, editor])

  const ToolbarButton = useCallback(({
    onClick,
    isActive = false,
    children,
    title
  }: {
    onClick: () => void
    isActive?: boolean
    children: React.ReactNode
    title: string
  }) => (
    <button
      type="button"
      onMouseDown={(e) => { e.preventDefault(); onClick() }}
      title={title}
      className={`w-7 h-7 flex items-center justify-center rounded text-xs transition-colors ${
        isActive
          ? 'bg-accent/15 text-accent'
          : 'text-text-400 hover:text-text-200 hover:bg-bg-200/60'
      }`}
    >
      {children}
    </button>
  ), [])

  if (!editor) return null

  return (
    <div className={`${isExpanded ? 'fixed inset-0 z-50 bg-bg-0' : 'w-80 border-l border-bg-300/70'} bg-bg-100 flex flex-col shrink-0 transition-all`}>
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-bg-300/70 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <DocereLogo className="w-4 h-4 text-accent" />
          <span className="text-[13px] font-medium text-text-200">Notes</span>
        </div>
        <div className="flex items-center gap-1">
          {onToggleExpand && (
            <button
              onClick={onToggleExpand}
              title={isExpanded ? 'Exit full screen' : 'Full screen'}
              className="text-text-400 hover:text-text-200 transition-colors p-1 rounded hover:bg-bg-200/60"
            >
              {isExpanded ? (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
                </svg>
              )}
            </button>
          )}
          <button
            onClick={onClose}
            className="text-text-400 hover:text-text-200 transition-colors p-1 rounded hover:bg-bg-200/60"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="px-2 py-1.5 border-b border-bg-300/50 flex items-center gap-0.5 flex-wrap">
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          isActive={editor.isActive('heading', { level: 1 })}
          title="Heading 1"
        >H1</ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          isActive={editor.isActive('heading', { level: 2 })}
          title="Heading 2"
        >H2</ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          isActive={editor.isActive('heading', { level: 3 })}
          title="Heading 3"
        >H3</ToolbarButton>

        <div className="w-px h-4 bg-bg-300/70 mx-1" />

        <ToolbarButton onClick={() => editor.chain().focus().toggleBold().run()} isActive={editor.isActive('bold')} title="Bold">
          <span className="font-bold">B</span>
        </ToolbarButton>
        <ToolbarButton onClick={() => editor.chain().focus().toggleItalic().run()} isActive={editor.isActive('italic')} title="Italic">
          <span className="italic">I</span>
        </ToolbarButton>
        <ToolbarButton onClick={() => editor.chain().focus().toggleHighlight().run()} isActive={editor.isActive('highlight')} title="Highlight">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.763m3.42 3.42a6.776 6.776 0 00-3.42-3.42" />
          </svg>
        </ToolbarButton>

        <div className="w-px h-4 bg-bg-300/70 mx-1" />

        <ToolbarButton onClick={() => editor.chain().focus().toggleBulletList().run()} isActive={editor.isActive('bulletList')} title="Bullet list">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
          </svg>
        </ToolbarButton>
        <ToolbarButton onClick={() => editor.chain().focus().toggleOrderedList().run()} isActive={editor.isActive('orderedList')} title="Numbered list">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.242 5.992h12m-12 6.003h12m-12 5.999h12M4.117 7.495v-3.75H2.99m1.125 3.75H2.99m1.125 0H4.74m-1.5 6.003h.008v.008h-.008v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.117 19.748V17.25H2.99m1.125 2.498H2.99" />
          </svg>
        </ToolbarButton>
        <ToolbarButton onClick={() => editor.chain().focus().toggleTaskList().run()} isActive={editor.isActive('taskList')} title="Checklist">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </ToolbarButton>

        <div className="w-px h-4 bg-bg-300/70 mx-1" />

        <ToolbarButton onClick={() => editor.chain().focus().toggleCodeBlock().run()} isActive={editor.isActive('codeBlock')} title="Code block">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
          </svg>
        </ToolbarButton>
        <ToolbarButton onClick={() => editor.chain().focus().toggleBlockquote().run()} isActive={editor.isActive('blockquote')} title="Quote">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
          </svg>
        </ToolbarButton>
      </div>

      {/* Agent writing indicator */}
      {isAgentWriting && (
        <div className="px-3 py-2.5 border-b border-accent/10 bg-accent/5 flex items-center gap-2.5 animate-fade-in">
          <div className="notes-writing-indicator">
            <DocereLogo className="w-4 h-4 text-accent" />
          </div>
          <span className="text-[12px] text-accent font-medium">Docere is writing...</span>
        </div>
      )}

      {/* Agent wrote section — explain/rewrite bar */}
      {!isAgentWriting && agentWrittenSection && (
        <div className="px-3 py-2 border-b border-accent/15 bg-accent/5 flex items-center gap-2 animate-fade-in">
          <DocereLogo className="w-3.5 h-3.5 text-accent shrink-0" />
          <span className="text-[11px] text-text-400 flex-1">Docere added to your notes</span>
          <button
            onClick={onExplain}
            className="px-2 py-1 text-[11px] font-medium text-accent bg-accent/10 hover:bg-accent/20 rounded-md transition-colors"
          >
            Explain
          </button>
          <button
            onClick={onRewrite}
            className="px-2 py-1 text-[11px] font-medium text-text-300 bg-bg-200/60 hover:bg-bg-200 rounded-md transition-colors"
          >
            Rewrite
          </button>
          <button
            onClick={onDismissAgentSection}
            className="text-text-500 hover:text-text-300 transition-colors p-0.5"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3 h-3">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Editor */}
      <div className={`flex-1 overflow-y-auto ${isExpanded ? 'max-w-3xl mx-auto w-full' : ''}`}>
        <EditorContent editor={editor} />
      </div>

      {/* Footer */}
      {content && content !== '<p></p>' && !isAgentWriting && !agentWrittenSection && (
        <div className="px-3 py-2 border-t border-bg-300/50 text-[11px] text-text-500">
          Your tutor can see these notes and will reference them in responses.
        </div>
      )}
    </div>
  )
}
