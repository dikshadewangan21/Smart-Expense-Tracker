import { FileSpreadsheet, Receipt as ReceiptIcon, UploadCloud, CheckCircle2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { money } from '../lib/format'
import { useLookups } from '../lib/useLookups'
import { Empty, ErrorBox, Skeleton, Stat, ghost, useLoad } from '../components/ui'

interface ImportRecord {
  id: number
  kind: string
  filename: string
  rows_total: number
  rows_imported: number
  rows_duplicate: number
  status: string
  created_at: string
}

interface ParsedReceipt {
  id: number
  merchant: string | null
  total: number | string | null
  tax: number | string | null
  receipt_date: string | null
  status: string
  suggested_category_id: number | null
  items: { id: number; name: string; amount: number | string }[]
}

export default function ImportCenter() {
  const { user } = useAuth()
  const { categories, accounts } = useLookups()
  const cur = user?.currency ?? 'INR'

  const [tab, setTab] = useState<'csv' | 'receipt'>('csv')

  // CSV States
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<{ headers: string[]; sample_rows: string[][]; detected_mapping: Record<string, number> } | null>(null)
  const [mapping, setMapping] = useState<Record<string, number>>({})
  const [targetAccount, setTargetAccount] = useState<string>('')
  const [csvResult, setCsvResult] = useState<Record<string, number> | null>(null)
  const [csvBusy, setCsvBusy] = useState(false)
  const [csvErr, setCsvErr] = useState<string | null>(null)

  // Receipt OCR States
  const [receiptFile, setReceiptFile] = useState<File | null>(null)
  const [ocrResult, setOcrResult] = useState<ParsedReceipt | null>(null)
  const [ocrBusy, setOcrBusy] = useState(false)
  const [ocrErr, setOcrErr] = useState<string | null>(null)

  // Confirm Receipt State
  const [confMerchant, setConfMerchant] = useState('')
  const [confAmount, setConfAmount] = useState('')
  const [confDate, setConfDate] = useState('')
  const [confCategory, setConfCategory] = useState('')
  const [confAccount, setConfAccount] = useState('')
  const [confSuccess, setConfSuccess] = useState(false)

  const importsList = useLoad(() => api<ImportRecord[]>('/imports'), [])
  const receiptsList = useLoad(() => api<ParsedReceipt[]>('/receipts'), [])

  async function handleCsvSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setCsvFile(file)
    setCsvErr(null)
    setCsvResult(null)
    setCsvBusy(true)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await api<{ headers: string[]; sample_rows: string[][]; detected_mapping: Record<string, number> }>('/imports/preview', {
        method: 'POST',
        body: formData,
      })
      setPreview(res)
      setMapping(res.detected_mapping || {})
    } catch (err2) {
      setCsvErr(err2 instanceof Error ? err2.message : 'Could not read CSV file.')
    } finally {
      setCsvBusy(false)
    }
  }

  async function executeCsvImport() {
    if (!csvFile || !preview) return
    setCsvBusy(true)
    setCsvErr(null)

    const formData = new FormData()
    formData.append('file', csvFile)
    formData.append('mapping', JSON.stringify(mapping))
    if (targetAccount) formData.append('account_id', targetAccount)

    try {
      const res = await api<Record<string, number>>('/imports/execute', {
        method: 'POST',
        body: formData,
      })
      setCsvResult(res)
      setPreview(null)
      setCsvFile(null)
      importsList.reload()
    } catch (err2) {
      setCsvErr(err2 instanceof Error ? err2.message : 'Import failed.')
    } finally {
      setCsvBusy(false)
    }
  }

  async function handleReceiptUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setReceiptFile(file)
    setOcrErr(null)
    setOcrBusy(true)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await api<ParsedReceipt>('/receipts/upload', {
        method: 'POST',
        body: formData,
      })
      setOcrResult(res)
      setConfMerchant(res.merchant || '')
      setConfAmount(res.total ? String(res.total) : '')
      setConfDate(res.receipt_date || new Date().toISOString().split('T')[0])
      setConfCategory(res.suggested_category_id ? String(res.suggested_category_id) : '')
      receiptsList.reload()
    } catch (err2) {
      setOcrErr(err2 instanceof Error ? err2.message : 'Failed to scan receipt.')
    } finally {
      setOcrBusy(false)
    }
  }

  async function confirmReceipt() {
    if (!ocrResult) return
    setOcrBusy(true)
    setOcrErr(null)
    try {
      await api(`/receipts/${ocrResult.id}/confirm`, {
        method: 'POST',
        body: JSON.stringify({
          merchant: confMerchant,
          amount: confAmount,
          date: confDate,
          category_id: confCategory ? Number(confCategory) : null,
          account_id: confAccount ? Number(confAccount) : null,
        }),
      })
      setConfSuccess(true)
      receiptsList.reload()
    } catch (err2) {
      setOcrErr(err2 instanceof Error ? err2.message : 'Could not confirm receipt.')
    } finally {
      setOcrBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">Import Center</h1>
        <div className="flex gap-2" role="group">
          <button className="btn flex items-center gap-2" style={tab === 'csv' ? {} : ghost} onClick={() => setTab('csv')}>
            <FileSpreadsheet size={16} /> CSV Bank Statements
          </button>
          <button className="btn flex items-center gap-2" style={tab === 'receipt' ? {} : ghost} onClick={() => setTab('receipt')}>
            <ReceiptIcon size={16} /> Receipt OCR Scanner
          </button>
        </div>
      </div>

      {tab === 'csv' && (
        <div className="flex flex-col gap-4">
          <section className="card flex flex-col gap-3">
            <h2 className="font-semibold text-base">Import Bank or Card Statement</h2>
            <p className="muted text-sm">Upload any bank or credit card CSV file. We automatically match columns and skip previously imported duplicates.</p>

            <label className="border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center gap-2 cursor-pointer hover:bg-card/50" style={{ borderColor: 'var(--border)' }}>
              <UploadCloud size={32} className="muted" />
              <span className="font-medium text-sm">{csvFile ? csvFile.name : 'Select or drop CSV file'}</span>
              <span className="muted text-xs">Supports HDFC, ICICI, SBI, Axis, AMEX, and custom CSV formats</span>
              <input type="file" accept=".csv,text/csv" className="hidden" onChange={handleCsvSelect} />
            </label>

            {csvBusy && <p className="muted text-sm">Processing file...</p>}
            {csvErr && <ErrorBox message={csvErr} />}

            {csvResult && (
              <div className="card flex flex-col gap-2" style={{ borderColor: 'var(--good)' }}>
                <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--good)' }}>
                  <CheckCircle2 size={18} /> Import Completed Successfully!
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <Stat label="Total Read" value={String(csvResult.rows_total)} />
                  <Stat label="Imported" value={String(csvResult.rows_imported)} tone="good" />
                  <Stat label="Duplicates Skipped" value={String(csvResult.rows_duplicate)} />
                </div>
              </div>
            )}

            {preview && (
              <div className="flex flex-col gap-4 mt-2">
                <h3 className="font-semibold text-sm">Map Columns</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <label className="text-sm">
                    Date Column
                    <select className="input" value={mapping.date ?? ''} onChange={(e) => setMapping({ ...mapping, date: Number(e.target.value) })}>
                      <option value="">-- Select --</option>
                      {preview.headers.map((h, i) => <option key={i} value={i}>{h} (Col {i + 1})</option>)}
                    </select>
                  </label>
                  <label className="text-sm">
                    Description / Merchant
                    <select className="input" value={mapping.merchant ?? ''} onChange={(e) => setMapping({ ...mapping, merchant: Number(e.target.value) })}>
                      <option value="">-- Select --</option>
                      {preview.headers.map((h, i) => <option key={i} value={i}>{h} (Col {i + 1})</option>)}
                    </select>
                  </label>
                  <label className="text-sm">
                    Amount Column
                    <select className="input" value={mapping.amount ?? ''} onChange={(e) => setMapping({ ...mapping, amount: Number(e.target.value) })}>
                      <option value="">-- Select --</option>
                      {preview.headers.map((h, i) => <option key={i} value={i}>{h} (Col {i + 1})</option>)}
                    </select>
                  </label>
                  <label className="text-sm">
                    Assign to Account
                    <select className="input" value={targetAccount} onChange={(e) => setTargetAccount(e.target.value)}>
                      <option value="">-- None / Default --</option>
                      {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                    </select>
                  </label>
                </div>

                <div className="overflow-x-auto text-xs border rounded" style={{ borderColor: 'var(--border)' }}>
                  <table className="w-full text-left">
                    <thead className="bg-card">
                      <tr>
                        {preview.headers.map((h, i) => <th key={i} className="p-2 border-b" style={{ borderColor: 'var(--border)' }}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.sample_rows.map((r, ri) => (
                        <tr key={ri} className="border-b" style={{ borderColor: 'var(--border)' }}>
                          {r.map((c, ci) => <td key={ci} className="p-2 truncate max-w-xs">{c}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex justify-end gap-2">
                  <button className="btn" style={ghost} onClick={() => setPreview(null)}>Cancel</button>
                  <button className="btn" disabled={csvBusy || mapping.date === undefined || (mapping.amount === undefined && mapping.debit === undefined)} onClick={executeCsvImport}>
                    {csvBusy ? 'Importing...' : 'Confirm & Import Transactions'}
                  </button>
                </div>
              </div>
            )}
          </section>

          <section className="card flex flex-col gap-3">
            <h2 className="font-semibold text-base">Previous Imports History</h2>
            {importsList.error && <ErrorBox message={importsList.error} onRetry={importsList.reload} />}
            {!importsList.data ? <Skeleton rows={3} /> : importsList.data.length === 0 ? <Empty>No statement imports run yet.</Empty> : (
              <div className="overflow-x-auto text-sm">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b muted text-xs" style={{ borderColor: 'var(--border)' }}>
                      <th className="py-2">File</th>
                      <th>Total</th>
                      <th>Imported</th>
                      <th>Duplicates</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {importsList.data.map((imp) => (
                      <tr key={imp.id} className="border-b" style={{ borderColor: 'var(--border)' }}>
                        <td className="py-2 font-medium">{imp.filename}</td>
                        <td>{imp.rows_total}</td>
                        <td style={{ color: 'var(--good)' }}>{imp.rows_imported}</td>
                        <td>{imp.rows_duplicate}</td>
                        <td className="muted text-xs">{new Date(imp.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}

      {tab === 'receipt' && (
        <div className="flex flex-col gap-4">
          <section className="card flex flex-col gap-3">
            <h2 className="font-semibold text-base">Scan Receipt & Invoices</h2>
            <p className="muted text-sm">Upload a photo of a bill, receipt, or invoice. OCR parses total amounts, tax, items, and merchant information automatically.</p>

            <label className="border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center gap-2 cursor-pointer hover:bg-card/50" style={{ borderColor: 'var(--border)' }}>
              <ReceiptIcon size={32} className="muted" />
              <span className="font-medium text-sm">{receiptFile ? receiptFile.name : 'Upload receipt image or document'}</span>
              <span className="muted text-xs">JPG, PNG, PDF or text receipts</span>
              <input type="file" accept="image/*,.pdf,text/plain" className="hidden" onChange={handleReceiptUpload} />
            </label>

            {ocrBusy && <p className="muted text-sm">Extracting text & line items with OCR...</p>}
            {ocrErr && <ErrorBox message={ocrErr} />}

            {ocrResult && (
              <div className="card flex flex-col gap-4 mt-2">
                <h3 className="font-semibold text-sm">Review Extracted Receipt</h3>
                {confSuccess ? (
                  <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--good)' }}>
                    <CheckCircle2 size={18} /> Receipt successfully saved as a transaction!
                  </div>
                ) : (
                  <form onSubmit={(e) => { e.preventDefault(); confirmReceipt() }} className="flex flex-col gap-3">
                    <div className="grid grid-cols-2 gap-3">
                      <label className="text-sm">
                        Merchant
                        <input className="input" value={confMerchant} onChange={(e) => setConfMerchant(e.target.value)} required />
                      </label>
                      <label className="text-sm">
                        Total Amount ({cur})
                        <input className="input" inputMode="decimal" value={confAmount} onChange={(e) => setConfAmount(e.target.value)} required />
                      </label>
                      <label className="text-sm">
                        Receipt Date
                        <input className="input" type="date" value={confDate} onChange={(e) => setConfDate(e.target.value)} required />
                      </label>
                      <label className="text-sm">
                        Category
                        <select className="input" value={confCategory} onChange={(e) => setConfCategory(e.target.value)}>
                          <option value="">-- None / Uncategorized --</option>
                          {categories.filter((c) => c.kind === 'expense').map((c) => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                      <label className="text-sm">
                        Account
                        <select className="input" value={confAccount} onChange={(e) => setConfAccount(e.target.value)}>
                          <option value="">-- None / Default --</option>
                          {accounts.map((a) => (
                            <option key={a.id} value={a.id}>{a.name}</option>
                          ))}
                        </select>
                      </label>
                    </div>

                    {ocrResult.items.length > 0 && (
                      <div className="flex flex-col gap-1 mt-1">
                        <span className="muted text-xs font-medium">Extracted Line Items:</span>
                        <ul className="text-xs divide-y border rounded p-2" style={{ borderColor: 'var(--border)' }}>
                          {ocrResult.items.map((it) => (
                            <li key={it.id} className="py-1 flex justify-between">
                              <span>{it.name}</span>
                              <span className="font-medium">{money(Number(it.amount), cur)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div className="flex justify-end gap-2">
                      <button type="button" className="btn" style={ghost} onClick={() => setOcrResult(null)}>Cancel</button>
                      <button type="submit" className="btn" disabled={ocrBusy}>{ocrBusy ? 'Saving...' : 'Add as Expense Transaction'}</button>
                    </div>
                  </form>
                )}
              </div>
            )}
          </section>

          <section className="card flex flex-col gap-3">
            <h2 className="font-semibold text-base">Receipt Uploads History</h2>
            {!receiptsList.data ? <Skeleton rows={3} /> : receiptsList.data.length === 0 ? <Empty>No receipts scanned yet.</Empty> : (
              <ul className="divide-y text-sm" style={{ borderColor: 'var(--border)' }}>
                {receiptsList.data.map((r) => (
                  <li key={r.id} className="py-2 flex items-center justify-between">
                    <div>
                      <div className="font-medium">{r.merchant || 'Unnamed receipt'}</div>
                      <div className="muted text-xs">{r.receipt_date || 'No date'} · {r.status}</div>
                    </div>
                    <span className="font-semibold">{r.total ? money(Number(r.total), cur) : '—'}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
