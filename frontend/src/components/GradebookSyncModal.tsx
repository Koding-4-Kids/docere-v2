import { useState, useEffect, useCallback, useRef } from 'react'
import type {
  Course,
  IntegrationStatus,
  SpreadsheetInfo,
  SpreadsheetData,
  GradeItem,
  ValidationResult,
  ValidationIssue,
  SyncResult,
  FixResult,
  ColumnMapping,
} from '../api'
import {
  listGoogleSpreadsheets,
  readGoogleSpreadsheet,
  readGoogleSpreadsheetUrl,
  uploadExcel,
  getGradeItems,
  validateGradebook,
  syncGradebook,
  fixGradebook,
  downloadFixedExcel,
} from '../api'

type Step = 'source' | 'destination' | 'validation' | 'sync'

interface Props {
  onClose: () => void
  source: 'google_sheets' | 'excel'
  integrationStatus: IntegrationStatus | null
  courses: Course[]
}

// ── Icons ──

const SheetIcon = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#0F9D58" />
    <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#87CEAC" />
    <rect x="6.5" y="11.5" width="11" height="8" rx="0.5" fill="#fff" fillOpacity="0.9" />
    <line x1="6.5" y1="15.5" x2="17.5" y2="15.5" stroke="#0F9D58" strokeWidth="0.8" />
    <line x1="11" y1="11.5" x2="11" y2="19.5" stroke="#0F9D58" strokeWidth="0.8" />
  </svg>
)

const ExcelIcon = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#217346" />
    <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#33C481" />
    <path d="M7.5 12l3 4m0-4l-3 4" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
)

const CheckIcon = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
)

// ── Shared Components ──

function StepIndicator({ current, steps }: { current: number; steps: string[] }) {
  return (
    <div className="flex items-center gap-1 mb-5">
      {steps.map((label, i) => (
        <div key={i} className="flex items-center gap-1">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold transition-colors ${
            i < current ? 'bg-emerald-500/20 text-emerald-400' :
            i === current ? 'bg-[#4488ff]/20 text-[#4488ff]' :
            'bg-white/[0.04] text-white/20'
          }`}>
            {i < current ? CheckIcon : i + 1}
          </div>
          <span className={`text-[11px] ${i === current ? 'text-white/60' : 'text-white/25'}`}>{label}</span>
          {i < steps.length - 1 && <div className="w-4 h-px bg-white/[0.08] mx-1" />}
        </div>
      ))}
    </div>
  )
}

function LoadingDots() {
  return (
    <div className="flex items-center justify-center gap-1 py-8">
      <span className="w-1.5 h-1.5 bg-[#4488ff]/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-1.5 h-1.5 bg-[#4488ff]/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-1.5 h-1.5 bg-[#4488ff]/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
    </div>
  )
}

// ── Step 1: Source Selection ──

function SourceStep({ source, onSelect, integrationStatus }: {
  source: 'google_sheets' | 'excel'
  onSelect: (data: SpreadsheetData) => void
  integrationStatus: IntegrationStatus | null
}) {
  const [tab, setTab] = useState<'sheets' | 'excel'>(source === 'google_sheets' ? 'sheets' : 'excel')
  const [spreadsheets, setSpreadsheets] = useState<SpreadsheetInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [showUrlInput, setShowUrlInput] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const googleConnected = integrationStatus?.google_connected ?? false
  const hasSheetScopes = integrationStatus?.google_scopes?.some(
    s => s.includes('spreadsheets') || s.includes('drive')
  ) ?? false
  const needsScopeUpgrade = googleConnected && !hasSheetScopes

  useEffect(() => {
    if (tab === 'sheets' && googleConnected && hasSheetScopes) {
      setLoading(true)
      listGoogleSpreadsheets()
        .then(setSpreadsheets)
        .catch(e => setError(e.message))
        .finally(() => setLoading(false))
    }
  }, [tab, googleConnected])

  const handleSheetClick = async (sheet: SpreadsheetInfo) => {
    setLoading(true)
    setError(null)
    try {
      const data = await readGoogleSpreadsheet(sheet.id)
      onSelect(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleUrlSubmit = async () => {
    if (!urlInput.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await readGoogleSpreadsheetUrl(urlInput.trim())
      onSelect(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const result = await uploadExcel(file)
      onSelect({ title: result.filename, headers: result.headers, rows: result.rows })
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (!file || !file.name.endsWith('.xlsx')) {
      setError('Only .xlsx files are supported')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const result = await uploadExcel(file)
      onSelect({ title: result.filename, headers: result.headers, rows: result.rows })
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      {/* Tab switcher */}
      <div className="flex gap-1 p-1 rounded-xl bg-white/[0.03] mb-4">
        <button
          onClick={() => setTab('sheets')}
          className={`flex-1 px-3 py-2 rounded-lg text-[12px] font-medium transition-colors ${
            tab === 'sheets' ? 'bg-white/[0.08] text-white/70' : 'text-white/30 hover:text-white/50'
          }`}
        >
          Google Sheets
        </button>
        <button
          onClick={() => setTab('excel')}
          className={`flex-1 px-3 py-2 rounded-lg text-[12px] font-medium transition-colors ${
            tab === 'excel' ? 'bg-white/[0.08] text-white/70' : 'text-white/30 hover:text-white/50'
          }`}
        >
          Excel Upload
        </button>
      </div>

      {error && (
        <div className="text-[12px] text-red-400/80 bg-red-500/5 rounded-lg px-3 py-2 mb-3">{error}</div>
      )}

      {loading && <LoadingDots />}

      {/* Google Sheets tab */}
      {tab === 'sheets' && !loading && (
        <div>
          {!googleConnected ? (
            <div className="text-center py-6">
              <p className="text-[13px] text-white/40 mb-4">Connect Google to access your spreadsheets.</p>
              <button
                onClick={() => {
                  const token = localStorage.getItem('docere_token')
                  fetch('/api/v1/calendar/oauth/authorize', {
                    headers: { 'Authorization': `Bearer ${token}` },
                  })
                    .then(r => r.json())
                    .then(data => { if (data.url) window.open(data.url, '_blank', 'width=600,height=700') })
                    .catch(() => {})
                }}
                className="px-4 py-2 rounded-xl bg-[#4488ff]/15 text-[#4488ff] text-[13px] font-medium hover:bg-[#4488ff]/25 transition-colors"
              >
                Connect Google
              </button>
            </div>
          ) : needsScopeUpgrade ? (
            <div className="text-center py-6">
              <p className="text-[13px] text-white/40 mb-2">Google is connected but missing Sheets permissions.</p>
              <p className="text-[11px] text-white/25 mb-4">Reconnect to grant access to Google Sheets and Drive.</p>
              <button
                onClick={() => {
                  const token = localStorage.getItem('docere_token')
                  fetch('/api/v1/calendar/oauth/upgrade-scopes', {
                    headers: { 'Authorization': `Bearer ${token}` },
                  })
                    .then(r => r.json())
                    .then(data => { if (data.url) window.open(data.url, '_blank', 'width=600,height=700') })
                    .catch(() => {})
                }}
                className="px-4 py-2 rounded-xl bg-[#4488ff]/15 text-[#4488ff] text-[13px] font-medium hover:bg-[#4488ff]/25 transition-colors"
              >
                Upgrade Permissions
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {spreadsheets.length === 0 && !loading && (
                <p className="text-[12px] text-white/30 text-center py-4">No spreadsheets created by Docere yet.</p>
              )}
              {spreadsheets.map(sheet => (
                <button
                  key={sheet.id}
                  onClick={() => handleSheetClick(sheet)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-white/[0.02] border border-white/[0.06] hover:border-white/[0.12] hover:bg-white/[0.04] transition-all text-left"
                >
                  {SheetIcon}
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] text-white/60 truncate">{sheet.title}</div>
                    <div className="text-[10px] text-white/25">{new Date(sheet.modified_time).toLocaleDateString()}</div>
                  </div>
                </button>
              ))}

              {/* Paste URL option */}
              <div className="pt-2 border-t border-white/[0.06]">
                {!showUrlInput ? (
                  <button
                    onClick={() => setShowUrlInput(true)}
                    className="text-[12px] text-[#4488ff]/60 hover:text-[#4488ff] transition-colors"
                  >
                    Or paste a Google Sheets URL...
                  </button>
                ) : (
                  <div className="flex gap-2">
                    <input
                      value={urlInput}
                      onChange={e => setUrlInput(e.target.value)}
                      placeholder="https://docs.google.com/spreadsheets/d/..."
                      className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[12px] text-white/70 placeholder:text-white/20 outline-none focus:border-white/[0.15]"
                      onKeyDown={e => e.key === 'Enter' && handleUrlSubmit()}
                      autoFocus
                    />
                    <button
                      onClick={handleUrlSubmit}
                      className="px-3 py-2 rounded-lg bg-[#4488ff]/15 text-[#4488ff] text-[11px] font-medium hover:bg-[#4488ff]/25 transition-colors"
                    >
                      Load
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Excel tab */}
      {tab === 'excel' && !loading && (
        <div
          onDragOver={e => e.preventDefault()}
          onDrop={handleDrop}
          className="border-2 border-dashed border-white/[0.08] rounded-xl p-8 text-center hover:border-white/[0.15] transition-colors cursor-pointer"
          onClick={() => fileRef.current?.click()}
        >
          <div className="w-12 h-12 rounded-xl bg-[#217346]/10 flex items-center justify-center mx-auto mb-3">
            {ExcelIcon}
          </div>
          <p className="text-[13px] text-white/50 mb-1">Drop your .xlsx file here</p>
          <p className="text-[11px] text-white/25">or click to browse</p>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls"
            onChange={handleFileUpload}
            className="hidden"
          />
        </div>
      )}
    </div>
  )
}

// ── Step 2: Destination Selection ──

function DestinationStep({ courses, sourceData, onValidate }: {
  courses: Course[]
  sourceData: SpreadsheetData
  onValidate: (courseId: string, gradeItemIds: string[], result: ValidationResult) => void
}) {
  const [selectedCourse, setSelectedCourse] = useState<string>(courses[0]?.id || '')
  const [gradeItems, setGradeItems] = useState<GradeItem[]>([])
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [validating, setValidating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!selectedCourse) return
    setLoading(true)
    setError(null)
    getGradeItems(selectedCourse)
      .then(items => {
        setGradeItems(items)
        setSelectedItems(new Set(items.map(i => i.id)))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [selectedCourse])

  const toggleItem = (id: string) => {
    setSelectedItems(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleValidate = async () => {
    if (selectedItems.size === 0) return
    setValidating(true)
    setError(null)
    try {
      const result = await validateGradebook(sourceData, selectedCourse, [...selectedItems])
      onValidate(selectedCourse, [...selectedItems], result)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setValidating(false)
    }
  }

  // Group items by category
  const grouped: Record<string, GradeItem[]> = {}
  for (const item of gradeItems) {
    const cat = item.category || 'Uncategorized'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(item)
  }

  return (
    <div>
      {/* Source preview */}
      <div className="bg-white/[0.02] rounded-xl border border-white/[0.06] px-3 py-2.5 mb-4">
        <div className="text-[11px] text-white/30 mb-1">Source</div>
        <div className="text-[13px] text-white/60">{sourceData.title || 'Spreadsheet'}</div>
        <div className="text-[10px] text-white/25">{sourceData.headers.length} columns, {sourceData.rows.length} rows</div>
      </div>

      {/* Course selector */}
      {courses.length > 1 && (
        <div className="mb-4">
          <label className="text-[11px] text-white/30 mb-1.5 block">Course</label>
          <select
            value={selectedCourse}
            onChange={e => setSelectedCourse(e.target.value)}
            className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[12px] text-white/70 outline-none"
          >
            {courses.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <div className="text-[12px] text-red-400/80 bg-red-500/5 rounded-lg px-3 py-2 mb-3">{error}</div>
      )}

      {loading && <LoadingDots />}

      {/* Grade items */}
      {!loading && gradeItems.length > 0 && (
        <div className="space-y-3 mb-4">
          <div className="flex items-center justify-between">
            <label className="text-[11px] text-white/30">Assignment sections to sync</label>
            <button
              onClick={() => {
                if (selectedItems.size === gradeItems.length) setSelectedItems(new Set())
                else setSelectedItems(new Set(gradeItems.map(i => i.id)))
              }}
              className="text-[10px] text-[#4488ff]/60 hover:text-[#4488ff]"
            >
              {selectedItems.size === gradeItems.length ? 'Deselect all' : 'Select all'}
            </button>
          </div>
          {Object.entries(grouped).map(([category, items]) => (
            <div key={category}>
              <div className="text-[10px] text-white/20 uppercase tracking-wider mb-1.5">{category}</div>
              <div className="space-y-1">
                {items.map(item => (
                  <button
                    key={item.id}
                    onClick={() => toggleItem(item.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-all ${
                      selectedItems.has(item.id)
                        ? 'bg-[#4488ff]/5 border border-[#4488ff]/20'
                        : 'bg-white/[0.02] border border-white/[0.06] hover:border-white/[0.1]'
                    }`}
                  >
                    <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                      selectedItems.has(item.id)
                        ? 'bg-[#4488ff]/20 border-[#4488ff]/40 text-[#4488ff]'
                        : 'border-white/[0.12]'
                    }`}>
                      {selectedItems.has(item.id) && CheckIcon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[12px] text-white/60 truncate">{item.name}</div>
                    </div>
                    <div className="text-[10px] text-white/20">/{item.grade_max}</div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && gradeItems.length === 0 && !error && selectedCourse && (
        <p className="text-[12px] text-white/30 text-center py-4">No grade items found for this course.</p>
      )}

      {/* Validate button */}
      {gradeItems.length > 0 && (
        <button
          onClick={handleValidate}
          disabled={selectedItems.size === 0 || validating}
          className="w-full py-2.5 rounded-xl bg-[#4488ff]/15 text-[#4488ff] text-[13px] font-medium hover:bg-[#4488ff]/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {validating ? 'Validating...' : `Validate ${selectedItems.size} item${selectedItems.size !== 1 ? 's' : ''}`}
        </button>
      )}
    </div>
  )
}

// ── Step 3: Validation Results ──

function ValidationStep({ result, sourceData, courseId, onSync, onFix, onBack }: {
  result: ValidationResult
  sourceData: SpreadsheetData
  courseId: string
  onSync: (syncResult: SyncResult) => void
  onFix: (fixResult: FixResult) => void
  onBack: () => void
}) {
  const [syncing, setSyncing] = useState(false)
  const [fixing, setFixing] = useState(false)
  const [editableRows, setEditableRows] = useState<string[][]>(sourceData.rows)
  const [error, setError] = useState<string | null>(null)

  const issueMap = new Map<string, ValidationIssue>()
  for (const issue of result.issues) {
    issueMap.set(`${issue.row}-${issue.col}`, issue)
  }

  const handleSync = async () => {
    if (!result.mappings) return
    setSyncing(true)
    setError(null)
    try {
      const syncResult = await syncGradebook(
        courseId,
        result.mappings,
        { ...sourceData, rows: editableRows },
      )
      onSync(syncResult)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSyncing(false)
    }
  }

  const handleDocereFix = async () => {
    setFixing(true)
    setError(null)
    try {
      const fixResult = await fixGradebook(
        { ...sourceData, rows: editableRows },
        result.issues,
      )
      onFix(fixResult)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setFixing(false)
    }
  }

  const handleCellEdit = (rowIdx: number, colIdx: number, value: string) => {
    setEditableRows(prev => {
      const next = prev.map(r => [...r])
      next[rowIdx][colIdx] = value
      return next
    })
  }

  if (result.valid) {
    return (
      <div>
        {/* Valid state */}
        <div className="text-center py-4 mb-4">
          <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-3">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
          </div>
          <p className="text-[14px] text-white/70 mb-1">Data looks good!</p>
          <p className="text-[12px] text-white/30">{result.student_count} students, {result.preview.reduce((n, p) => n + p.grades.length, 0)} grades ready to sync</p>
        </div>

        {error && (
          <div className="bg-red-500/5 border border-red-500/10 rounded-xl px-4 py-3 mb-4">
            <div className="text-[12px] text-red-400/80 mb-2">{error}</div>
            <div className="flex gap-2">
              <button
                onClick={handleDocereFix}
                disabled={fixing}
                className="flex-1 py-2 rounded-lg bg-[#4488ff]/15 text-[#4488ff] text-[11px] font-medium hover:bg-[#4488ff]/25 transition-colors disabled:opacity-40"
              >
                {fixing ? 'Fixing...' : 'Let Docere Fix It'}
              </button>
              <button
                onClick={onBack}
                className="flex-1 py-2 rounded-lg bg-white/[0.04] text-white/40 text-[11px] font-medium hover:bg-white/[0.08] transition-colors"
              >
                Fix Manually & Retry
              </button>
            </div>
          </div>
        )}

        {/* Preview table */}
        {result.preview.length > 0 && (
          <div className="overflow-x-auto mb-4 rounded-xl border border-white/[0.06]">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="px-3 py-2 text-left text-white/30 font-medium">Student</th>
                  <th className="px-3 py-2 text-left text-white/30 font-medium">Assignment</th>
                  <th className="px-3 py-2 text-right text-white/30 font-medium">Grade</th>
                </tr>
              </thead>
              <tbody>
                {result.preview.slice(0, 10).flatMap(p =>
                  p.grades.map((g, i) => (
                    <tr key={`${p.student}-${i}`} className="border-b border-white/[0.03]">
                      {i === 0 ? (
                        <td className="px-3 py-1.5 text-white/50" rowSpan={p.grades.length}>{p.student}</td>
                      ) : null}
                      <td className="px-3 py-1.5 text-white/40">{g.item}</td>
                      <td className="px-3 py-1.5 text-right text-white/60 font-mono">{g.new}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            {result.preview.length > 10 && (
              <div className="px-3 py-2 text-[10px] text-white/20">+{result.preview.length - 10} more students</div>
            )}
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex-1 py-2.5 rounded-xl bg-emerald-500/15 text-emerald-400 text-[13px] font-medium hover:bg-emerald-500/25 transition-colors disabled:opacity-40"
          >
            {syncing ? 'Syncing to gradebook...' : 'Sync to Gradebook'}
          </button>
          <button
            onClick={() => downloadFixedExcel({ ...sourceData, rows: editableRows })}
            className="py-2.5 px-4 rounded-xl bg-white/[0.04] text-white/40 text-[13px] font-medium hover:bg-white/[0.08] hover:text-white/60 transition-colors"
            title="Download the validated spreadsheet as .xlsx"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </button>
        </div>
      </div>
    )
  }

  // Invalid state — show issues
  const issuesByType: Record<string, number> = {}
  for (const issue of result.issues) {
    issuesByType[issue.type] = (issuesByType[issue.type] || 0) + 1
  }

  return (
    <div>
      {/* Issue summary */}
      <div className="bg-red-500/5 border border-red-500/10 rounded-xl px-4 py-3 mb-4">
        <div className="text-[13px] text-red-400/80 font-medium mb-1">Issues found</div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(issuesByType).map(([type, count]) => (
            <span key={type} className="text-[11px] text-red-400/60 bg-red-500/5 px-2 py-0.5 rounded-full">
              {count} {type.replace('_', ' ')}
            </span>
          ))}
        </div>
      </div>

      {error && (
        <div className="text-[12px] text-red-400/80 bg-red-500/5 rounded-lg px-3 py-2 mb-3">{error}</div>
      )}

      {/* Spreadsheet preview with highlighted issues */}
      <div className="overflow-x-auto mb-4 rounded-xl border border-white/[0.06]">
        <table className="w-full text-[10px]">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="px-2 py-1.5 text-left text-white/25 font-medium w-8">#</th>
              {sourceData.headers.map((h, i) => (
                <th key={i} className="px-2 py-1.5 text-left text-white/30 font-medium max-w-[120px] truncate">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {editableRows.slice(0, 20).map((row, rowIdx) => (
              <tr key={rowIdx} className="border-b border-white/[0.03]">
                <td className="px-2 py-1 text-white/15 font-mono">{rowIdx + 1}</td>
                {row.map((cell, colIdx) => {
                  const issue = issueMap.get(`${rowIdx}-${colIdx}`)
                  return (
                    <td
                      key={colIdx}
                      className={`px-2 py-1 max-w-[120px] ${issue ? 'bg-red-500/10' : ''}`}
                      title={issue ? `${issue.type}: ${issue.suggestion}` : undefined}
                    >
                      <input
                        value={cell}
                        onChange={e => handleCellEdit(rowIdx, colIdx, e.target.value)}
                        className={`w-full bg-transparent outline-none text-[10px] ${
                          issue ? 'text-red-400/80' : 'text-white/40'
                        }`}
                      />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {editableRows.length > 20 && (
          <div className="px-2 py-1.5 text-[10px] text-white/20">+{editableRows.length - 20} more rows</div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={handleDocereFix}
          disabled={fixing}
          className="flex-1 py-2.5 rounded-xl bg-[#4488ff]/15 text-[#4488ff] text-[12px] font-medium hover:bg-[#4488ff]/25 transition-colors disabled:opacity-40"
        >
          {fixing ? 'Fixing...' : 'Let Docere Fix It'}
        </button>
        <button
          onClick={onBack}
          className="flex-1 py-2.5 rounded-xl bg-white/[0.04] text-white/40 text-[12px] font-medium hover:bg-white/[0.08] hover:text-white/60 transition-colors"
        >
          Fix Manually & Retry
        </button>
        <button
          onClick={() => downloadFixedExcel({ ...sourceData, rows: editableRows })}
          className="py-2.5 px-3 rounded-xl bg-white/[0.04] text-white/30 hover:bg-white/[0.08] hover:text-white/50 transition-colors"
          title="Download current spreadsheet as .xlsx"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        </button>
      </div>
    </div>
  )
}

// ── Step 4: Sync Result ──

function SyncResultStep({ result, onClose, onFix, onManualFix }: {
  result: SyncResult
  onClose: () => void
  onFix: () => void
  onManualFix: () => void
}) {
  const total = result.synced + result.failed
  const percent = total > 0 ? Math.round((result.synced / total) * 100) : 0

  return (
    <div className="text-center py-4">
      {result.failed === 0 ? (
        <>
          <div className="w-14 h-14 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-4">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
          </div>
          <p className="text-[16px] text-white/80 font-medium mb-1">{result.synced} grades synced</p>
          <p className="text-[12px] text-white/30">All grades transferred to gradebook successfully.</p>
        </>
      ) : (
        <>
          <div className="w-14 h-14 rounded-full bg-amber-500/10 flex items-center justify-center mx-auto mb-4">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <p className="text-[16px] text-white/80 font-medium mb-1">{result.synced}/{total} grades synced</p>
          <p className="text-[12px] text-white/30 mb-4">{result.failed} failed to sync.</p>

          {/* Progress bar */}
          <div className="w-full h-2 bg-white/[0.04] rounded-full overflow-hidden mb-4">
            <div
              className="h-full bg-emerald-500/60 rounded-full transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>

          {/* Error details */}
          {result.errors.length > 0 && (
            <div className="text-left bg-white/[0.02] rounded-xl border border-white/[0.06] p-3 mb-4 max-h-32 overflow-y-auto">
              {result.errors.map((err, i) => (
                <div key={i} className="text-[11px] text-red-400/60 mb-1">
                  {err.student}: {err.error}
                </div>
              ))}
            </div>
          )}

          {/* Fix options */}
          <div className="flex gap-2 mb-2">
            <button
              onClick={onFix}
              className="flex-1 py-2.5 rounded-xl bg-[#4488ff]/15 text-[#4488ff] text-[12px] font-medium hover:bg-[#4488ff]/25 transition-colors"
            >
              Let Docere Fix It
            </button>
            <button
              onClick={onManualFix}
              className="flex-1 py-2.5 rounded-xl bg-white/[0.04] text-white/40 text-[12px] font-medium hover:bg-white/[0.08] hover:text-white/60 transition-colors"
            >
              Fix Manually & Retry
            </button>
          </div>
        </>
      )}

      <button
        onClick={onClose}
        className="mt-2 px-6 py-2.5 rounded-xl bg-white/[0.06] text-white/50 text-[13px] font-medium hover:bg-white/[0.1] transition-colors"
      >
        Done
      </button>
    </div>
  )
}

// ── Main Modal ──

export function GradebookSyncModal({ onClose, source, integrationStatus, courses }: Props) {
  const [step, setStep] = useState<Step>('source')
  const [sourceData, setSourceData] = useState<SpreadsheetData | null>(null)
  const [courseId, setCourseId] = useState<string>('')
  const [gradeItemIds, setGradeItemIds] = useState<string[]>([])
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null)
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [autoFixing, setAutoFixing] = useState(false)

  const stepIndex = step === 'source' ? 0 : step === 'destination' ? 1 : step === 'validation' ? 2 : 3

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  const handleSourceSelect = (data: SpreadsheetData) => {
    setSourceData(data)
    setStep('destination')
  }

  const handleValidate = (cId: string, selectedGradeItemIds: string[], result: ValidationResult) => {
    setCourseId(cId)
    setGradeItemIds(selectedGradeItemIds)
    setValidationResult(result)
    setStep('validation')
  }

  const handleSync = (result: SyncResult) => {
    setSyncResult(result)
    setStep('sync')
  }

  // Helper: re-validate current source data and jump to validation step
  const revalidateWithData = async (data: SpreadsheetData) => {
    setSourceData(data)
    setAutoFixing(true)
    try {
      const result = await validateGradebook(data, courseId, gradeItemIds)
      setValidationResult(result)
      setStep('validation')
    } catch {
      // If re-validation fails, fall back to destination step
      setStep('destination')
    } finally {
      setAutoFixing(false)
    }
  }

  // Validation step: Docere fixed the data → auto-revalidate
  const handleFix = (fixResult: FixResult) => {
    revalidateWithData(fixResult.fixed_data)
  }

  // Validation step: user wants to fix manually → go to destination
  const handleRevalidate = () => {
    setStep('destination')
  }

  // Sync step: Docere fix → call fix API with sync errors, then re-validate
  const handleSyncFixWithDocere = async () => {
    if (!sourceData || !syncResult) return
    setAutoFixing(true)
    try {
      // Build issues from sync errors so the fix agent knows what to correct
      const issues: ValidationIssue[] = syncResult.errors.map((err, i) => ({
        row: i,
        col: 0,
        type: 'format_error' as const,
        current: err.error || '',
        expected: 'Numeric grade',
        suggestion: `${err.student}: ${err.error}`,
      }))
      // If we have validation issues, use those (they're more precise)
      const fixIssues = validationResult?.issues?.length ? validationResult.issues : issues
      const fixResult = await fixGradebook(sourceData, fixIssues)
      // Re-validate the fixed data
      await revalidateWithData(fixResult.fixed_data)
    } catch {
      setStep('destination')
    } finally {
      setAutoFixing(false)
    }
  }

  // Sync step: user fixes manually → go to destination
  const handleSyncManualFix = () => {
    setStep('destination')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-xl mx-4 max-h-[85vh] bg-[#0e0e14] rounded-2xl border border-white/10 shadow-2xl overflow-hidden animate-fade-in flex flex-col">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-white/[0.06] shrink-0">
          <div className="w-8 h-8 rounded-xl bg-white/[0.05] flex items-center justify-center">
            {source === 'google_sheets' ? SheetIcon : ExcelIcon}
          </div>
          <h2 className="text-[14px] font-medium text-white/80">Gradebook Sync</h2>
          <button onClick={onClose} className="ml-auto text-white/20 hover:text-white/50 transition-colors text-lg">&times;</button>
        </div>

        {/* Content */}
        <div className="px-5 py-4 overflow-y-auto flex-1">
          <StepIndicator
            current={stepIndex}
            steps={['Source', 'Destination', 'Validate', 'Sync']}
          />

          {autoFixing ? (
            <div className="text-center py-12">
              <LoadingDots />
              <p className="text-[13px] text-white/40 mt-2">Docere is fixing the data and revalidating...</p>
            </div>
          ) : (
            <>
              {step === 'source' && (
                <SourceStep
                  source={source}
                  onSelect={handleSourceSelect}
                  integrationStatus={integrationStatus}
                />
              )}

              {step === 'destination' && sourceData && (
                <DestinationStep
                  courses={courses}
                  sourceData={sourceData}
                  onValidate={handleValidate}
                />
              )}

              {step === 'validation' && validationResult && sourceData && (
                <ValidationStep
                  result={validationResult}
                  sourceData={sourceData}
                  courseId={courseId}
                  onSync={handleSync}
                  onFix={handleFix}
                  onBack={handleRevalidate}
                />
              )}

              {step === 'sync' && syncResult && (
                <SyncResultStep
                  result={syncResult}
                  onClose={onClose}
                  onFix={handleSyncFixWithDocere}
                  onManualFix={handleSyncManualFix}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
