import React, { useMemo, useState } from 'react';
import {
  Download,
  FileJson,
  FileSpreadsheet,
  Globe,
  ShieldAlert,
  CheckCircle2,
  ExternalLink,
  Eye,
  Layers,
  Link2,
  Image as ImageIcon,
  MousePointer,
  AlertTriangle,
  X,
  Maximize2
} from 'lucide-react';

export default function CrawlResults({ crawl }) {
  const [statusFilter, setStatusFilter] = useState('ALL'); // 'ALL' | 'FAIL' | 'PASS'
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [selectedPageUrl, setSelectedPageUrl] = useState(null);
  const [zoomImage, setZoomImage] = useState(null);

  const rawIssues = crawl?.issues || [];
  const defects = crawl?.defects || [];
  const pages = crawl?.pages || [];
  const summary = crawl?.summary || {};
  const runId = crawl?.run_id;

  // Extract unique defect categories for filtering
  const availableCategories = useMemo(() => {
    const cats = new Set();
    for (const item of rawIssues) {
      if (item.Category || item.Issue) {
        cats.add(item.Category || item.Issue);
      }
    }
    return Array.from(cats);
  }, [rawIssues]);

  const filteredIssues = useMemo(() => {
    return rawIssues.filter((row) => {
      const matchStatus = statusFilter === 'ALL' || row.Status === statusFilter;
      const cat = row.Category || row.Issue;
      const matchCat = categoryFilter === 'ALL' || cat === categoryFilter;
      return matchStatus && matchCat;
    });
  }, [rawIssues, statusFilter, categoryFilter]);

  if (!crawl) return null;

  const previewPage = pages.find((p) => p.url === selectedPageUrl) || pages[0];

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      
      {/* 1. Header & Summary KPI Dashboard */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Globe className="w-5 h-5 text-[#0696D7]" />
              <h2 className="text-lg font-black text-slate-900">Site Crawl & Quality Validation Report</h2>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-black border uppercase tracking-wider ${
                summary.status === 'PASS'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : 'bg-rose-50 text-rose-800 border-rose-200'
              }`}>
                {summary.status || 'DONE'}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1 break-all">
              <span className="font-semibold text-slate-700">Root URL:</span> {crawl.root_url}
              {crawl.baseline_root_url ? (
                <>
                  <span className="mx-2 text-slate-300">|</span>
                  <span className="font-semibold text-slate-700">Baseline URL:</span> {crawl.baseline_root_url}
                </>
              ) : null}
            </p>
          </div>

          {/* Export Action Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            {crawl.reports?.json && (
              <a
                href={crawl.reports.json}
                download="report.json"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-slate-900 text-white hover:bg-slate-800 shadow-sm transition"
              >
                <FileJson className="w-4 h-4" /> JSON
              </a>
            )}
            {crawl.reports?.csv && (
              <a
                href={crawl.reports.csv}
                download="report.csv"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-slate-100 text-slate-800 border border-slate-200 hover:bg-slate-200 shadow-sm transition"
              >
                <Download className="w-4 h-4 text-slate-600" /> CSV
              </a>
            )}
            {crawl.reports?.xlsx && (
              <a
                href={crawl.reports.xlsx}
                download="report.xlsx"
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-[#0696D7] text-white hover:bg-[#0284C7] shadow-sm transition"
              >
                <FileSpreadsheet className="w-4 h-4" /> Excel (.xlsx)
              </a>
            )}
            {runId && (
              <span className="text-[11px] font-mono text-slate-400 self-center px-2 py-1 bg-slate-50 rounded-lg border border-slate-200">
                Run #{runId}
              </span>
            )}
          </div>
        </div>

        {/* 8 Metric KPI Cards Grid */}
        {(() => {
          const totalElements = summary.total_elements_checked || 0;
          const failedCount = summary.fail_count ?? summary.total_defects ?? 0;
          const passedCount = (summary.pass_count !== undefined && summary.pass_count > 0)
            ? summary.pass_count
            : Math.max(0, totalElements - failedCount);

          return (
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 pt-2">
              {[
                { label: 'Pages Crawled', value: summary.pages_crawled ?? pages.length, icon: Globe, color: 'text-slate-700' },
                { label: 'Elements Checked', value: totalElements, icon: Layers, color: 'text-sky-700' },
                { label: 'Links Checked', value: summary.total_links_checked ?? 0, icon: Link2, color: 'text-blue-700' },
                { label: 'Images Checked', value: summary.total_images_checked ?? 0, icon: ImageIcon, color: 'text-purple-700' },
                { label: 'Interactions', value: summary.total_interactions_checked ?? 0, icon: MousePointer, color: 'text-indigo-700' },
                { label: 'Total Defects', value: failedCount, icon: AlertTriangle, color: 'text-rose-600 font-black' },
                { label: 'Passed Checks', value: passedCount, icon: CheckCircle2, color: 'text-emerald-600 font-black' },
                { label: 'Failed Checks', value: failedCount, icon: ShieldAlert, color: 'text-rose-600' },
              ].map((kpi) => {
                const Icon = kpi.icon;
                return (
                  <div key={kpi.label} className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 text-center flex flex-col justify-between">
                    <div className="flex items-center justify-center text-slate-400 mb-1">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className={`text-xl font-black ${kpi.color}`}>{kpi.value}</div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mt-0.5">{kpi.label}</div>
                  </div>
                );
              })}
            </div>
          );
        })()}
      </div>

      {/* 2. Visual Explorer: Crawled Pages List + Evidence Viewport */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        
        {/* Left Column: Pages List */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 card-shadow lg:col-span-1 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-[#0696D7]" />
              Discovered Pages ({pages.length})
            </h3>
          </div>

          <div className="max-h-96 overflow-auto space-y-2 pr-1">
            {pages.map((page, idx) => {
              const isSelected = (previewPage && previewPage.url === page.url) || (!selectedPageUrl && idx === 0);
              const counts = page.element_counts || {};
              return (
                <button
                  key={page.url}
                  type="button"
                  onClick={() => setSelectedPageUrl(page.url)}
                  className={`w-full text-left rounded-xl border p-3 transition duration-150 ${
                    isSelected
                      ? 'border-[#0696D7] bg-sky-50/80 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-800 truncate">
                      {page.title || page.url}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${
                      page.http_status >= 400
                        ? 'bg-rose-100 text-rose-700'
                        : 'bg-emerald-100 text-emerald-700'
                    }`}>
                      {page.http_status ? `HTTP ${page.http_status}` : '200'}
                    </span>
                  </div>

                  <div className="text-[11px] text-slate-500 truncate mt-0.5" title={page.url}>
                    {page.url}
                  </div>

                  <div className="flex items-center gap-3 text-[10px] text-slate-400 mt-2">
                    <span>Depth: <b>{page.depth}</b></span>
                    <span>Elements: <b>{counts.total ?? 0}</b></span>
                    {page.duration_ms ? <span>Time: <b>{page.duration_ms}ms</b></span> : null}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Column: Screenshot & Annotated Evidence Viewer */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 card-shadow lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <Eye className="w-3.5 h-3.5 text-[#0696D7]" />
              Annotated Quality Evidence
            </h3>
            {previewPage && (
              <span className="text-xs text-slate-500 truncate max-w-sm" title={previewPage.url}>
                {previewPage.title || previewPage.url}
              </span>
            )}
          </div>

          <div className="relative rounded-xl border border-slate-200 bg-slate-900/5 overflow-hidden flex items-center justify-center min-h-[260px] group">
            {previewPage?.annotated_b64 || previewPage?.screenshot_b64 ? (
              <>
                <img
                  src={previewPage.annotated_b64 || previewPage.screenshot_b64}
                  alt="Page quality evidence"
                  className="w-full object-contain max-h-[380px] rounded-lg"
                />
                <button
                  type="button"
                  onClick={() => setZoomImage(previewPage.annotated_b64 || previewPage.screenshot_b64)}
                  className="absolute bottom-3 right-3 bg-slate-900/80 hover:bg-slate-900 text-white text-xs px-3 py-1.5 rounded-lg font-bold flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition shadow-md backdrop-blur-sm"
                >
                  <Maximize2 className="w-3.5 h-3.5" /> Fullscreen Preview
                </button>
              </>
            ) : (
              <div className="p-8 text-center text-xs text-slate-400">
                No inline image preview available for this page.
              </div>
            )}
          </div>

          {/* Element Breakdown Chips */}
          {previewPage?.element_counts && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[10px] font-bold text-slate-400 uppercase mr-1">Elements:</span>
              {Object.entries(previewPage.element_counts)
                .filter(([k, v]) => k !== 'total' && v > 0)
                .map(([k, v]) => (
                  <span key={k} className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200 font-medium">
                    {k}: <b className="text-slate-800">{v}</b>
                  </span>
                ))}
            </div>
          )}
        </div>

      </div>

      {/* 3. Detailed Filterable Findings & Issues Table */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow space-y-4">
        
        {/* Table Filters Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Audit Findings & Element Diagnostic Records ({filteredIssues.length})
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Inspect element selectors, expected vs actual behaviors, and captured evidence
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Status Filter */}
            <div className="flex gap-1 p-1 rounded-xl bg-slate-100">
              {['ALL', 'FAIL', 'PASS'].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatusFilter(s)}
                  className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                    statusFilter === s
                      ? 'bg-white text-[#0696D7] shadow-sm'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {/* Category Dropdown */}
            {availableCategories.length > 0 && (
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="text-xs px-3 py-1.5 rounded-xl border border-slate-300 bg-white font-medium focus:outline-none focus:ring-2 focus:ring-[#0696D7]"
              >
                <option value="ALL">All Defect Categories ({availableCategories.length})</option>
                {availableCategories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            )}
          </div>
        </div>

        {/* Table Content */}
        <div className="overflow-x-auto max-h-[520px] border border-slate-200 rounded-xl">
          <table className="min-w-full text-xs">
            <thead className="bg-slate-50 sticky top-0 z-10 border-b border-slate-200">
              <tr className="text-left text-[10px] uppercase font-bold tracking-wider text-slate-500">
                <th className="px-3.5 py-3">Status</th>
                <th className="px-3.5 py-3">Defect Category</th>
                <th className="px-3.5 py-3">Element / Selector</th>
                <th className="px-3.5 py-3">Expected Behavior</th>
                <th className="px-3.5 py-3">Actual Behavior / Error</th>
                <th className="px-3.5 py-3 text-center">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {filteredIssues.map((row, idx) => {
                const isFail = row.Status === 'FAIL';
                const category = row.Category || row.Issue || 'Other';
                const evidenceUrl = row.EvidenceImage || '';

                return (
                  <tr key={`${row.Page}-${row.Issue}-${idx}`} className="hover:bg-slate-50/70 transition align-top">
                    
                    {/* Status Badge */}
                    <td className="px-3.5 py-3 whitespace-nowrap">
                      {isFail ? (
                        <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md font-bold bg-rose-50 text-rose-700 border border-rose-200">
                          <ShieldAlert className="w-3.5 h-3.5" /> FAIL
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 className="w-3.5 h-3.5" /> PASS
                        </span>
                      )}
                    </td>

                    {/* Defect Category */}
                    <td className="px-3.5 py-3 whitespace-nowrap font-bold text-slate-800">
                      <div>{category}</div>
                      {row.HttpStatus ? (
                        <span className="text-[10px] font-mono text-rose-600">HTTP {row.HttpStatus}</span>
                      ) : null}
                    </td>

                    {/* Element & Selector */}
                    <td className="px-3.5 py-3 max-w-[240px]">
                      <div className="font-semibold text-slate-800 truncate" title={row.Element}>
                        {row.Element}
                      </div>
                      {row.Selector ? (
                        <div className="text-[10px] font-mono text-slate-400 truncate mt-0.5" title={row.Selector}>
                          {row.Selector}
                        </div>
                      ) : null}
                      <div className="text-[10px] text-slate-400 truncate mt-0.5" title={row.Page}>
                        {row.Page}
                      </div>
                    </td>

                    {/* Expected Behavior */}
                    <td className="px-3.5 py-3 text-slate-600 max-w-[220px]">
                      {row.Expected || 'Element functions according to UI quality standards.'}
                    </td>

                    {/* Actual Behavior */}
                    <td className="px-3.5 py-3 text-slate-800 max-w-[260px]">
                      <div className="font-medium">{row.Actual || row.Details}</div>
                    </td>

                    {/* Evidence Thumbnail */}
                    <td className="px-3.5 py-3 text-center whitespace-nowrap">
                      {evidenceUrl ? (
                        <button
                          type="button"
                          onClick={() => setZoomImage(evidenceUrl)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 bg-slate-50 hover:bg-sky-50 hover:border-sky-300 text-[11px] font-bold text-[#0696D7] transition shadow-xs"
                        >
                          <Eye className="w-3.5 h-3.5" /> Preview
                        </button>
                      ) : (
                        <span className="text-slate-300 text-[11px]">—</span>
                      )}
                    </td>

                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. Fullscreen Zoom Modal for Evidence Screenshots */}
      {zoomImage && (
        <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="relative bg-white rounded-2xl max-w-4xl w-full p-4 card-shadow space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <Eye className="w-4 h-4 text-[#0696D7]" />
                Evidence Screenshot Zoom
              </h4>
              <button
                type="button"
                onClick={() => setZoomImage(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="max-h-[75vh] overflow-auto flex items-center justify-center rounded-xl bg-slate-950 p-2">
              <img
                src={zoomImage}
                alt="Defect Evidence Fullscreen"
                className="max-h-full max-w-full object-contain rounded"
              />
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
