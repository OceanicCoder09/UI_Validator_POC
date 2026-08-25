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
  Maximize2,
  Split,
  Flame,
  Code2
} from 'lucide-react';
import FindingModal from './FindingModal';

export default function CrawlResults({ crawl }) {
  const [statusFilter, setStatusFilter] = useState('ALL'); // 'ALL' | 'FAIL' | 'PASS'
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [selectedPageUrl, setSelectedPageUrl] = useState(null);
  const [zoomImage, setZoomImage] = useState(null);
  const [viewMode, setViewMode] = useState('side_by_side'); // 'side_by_side' | 'annotated' | 'heatmap'
  const [selectedFindingModal, setSelectedFindingModal] = useState(null);

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
  const hasBaseline = Boolean(previewPage?.baseline_b64 || crawl?.baseline_root_url);

  const handleOpenFinding = (row) => {
    let targetUrl = row.target_url || row.TargetUrl || '';
    if (!targetUrl) {
      const match = (row.Actual || row.Expected || row.Details || '').match(/https?:\/\/[^\s'")]+/);
      if (match) {
        targetUrl = match[0].replace(/['"]$/, '');
      }
    }

    const findingObj = {
      id: row.lqa_code ? `ERR-${row.lqa_code}` : (row.id || (row.Selector ? row.Selector.slice(0, 15) : 'DEFECT')),
      severity: row.Severity || row.severity || 'Major',
      category: row.Category || row.Issue || row.defect_category || 'Localization Defect',
      title: row.Element || row.title || `${row.Category || row.Issue} Discrepancy`,
      description: row.Details || row.error_message || row.description || row.Actual || 'Visual discrepancy detected against baseline.',
      location: row._bbox || row.bbox || { x: 0, y: 0, width: 0, height: 0 },
      crop_baseline_b64: row.crop_baseline_b64 || '',
      crop_localized_b64: row.crop_localized_b64 || (row.EvidenceImage && row.EvidenceImage.startsWith('data:') ? row.EvidenceImage : '') || '',
      expected: row.Expected || row.expected_behavior || 'Matches baseline English layout and dimensions.',
      actual: row.Actual || row.actual_behavior || row.Details || 'Detected defect on localized page.',
      remediation: row.remediation || 'Ensure container uses dynamic padding and width (e.g. min-width: auto; padding: 0.5rem 1rem;).',
      target_url: targetUrl,
      page_url: row.Page || row.crawled_url || previewPage?.url || '',
    };
    setSelectedFindingModal(findingObj);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      
      {/* 1. Header & Summary KPI Dashboard */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Globe className="w-5 h-5 text-[#0696D7]" />
              <h2 className="text-lg font-black text-slate-900">
                {hasBaseline ? '2-Language Pairwise Crawl & Localization Report' : 'Site Crawl & Quality Validation Report'}
              </h2>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-black border uppercase tracking-wider ${
                summary.status === 'PASS'
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : 'bg-rose-50 text-rose-800 border-rose-200'
              }`}>
                {summary.status || 'DONE'}
              </span>
            </div>
            
            <div className="flex flex-wrap items-center gap-y-1 text-xs text-slate-500 mt-1.5">
              <span className="font-semibold text-slate-700 mr-1">Target Localized Site:</span>
              <span className="font-mono text-slate-800 mr-3">{crawl.root_url}</span>
              
              {crawl.baseline_root_url ? (
                <>
                  <span className="text-slate-300 mr-3">|</span>
                  <span className="font-semibold text-blue-700 mr-1">English Baseline Reference:</span>
                  <span className="font-mono text-blue-900">{crawl.baseline_root_url}</span>
                </>
              ) : null}
            </div>
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

        {/* Metric KPI Cards Grid */}
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

      {/* 2. Visual Explorer: Crawled Pages List + Side-by-Side Viewport */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        
        {/* Left Column: Pages List */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 card-shadow lg:col-span-1 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-[#0696D7]" />
              Crawled Pages ({pages.length})
            </h3>
            <span className="text-[11px] text-slate-400 font-semibold">Select to inspect</span>
          </div>

          <div className="max-h-[500px] overflow-auto space-y-2 pr-1">
            {pages.map((page, idx) => {
              const isSelected = (previewPage && previewPage.url === page.url) || (!selectedPageUrl && idx === 0);
              const counts = page.element_counts || {};
              const defCount = page.defects_count || 0;
              return (
                <button
                  key={`${page.url}-${idx}`}
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
                    <div className="flex items-center gap-1 shrink-0">
                      {defCount > 0 ? (
                        <span className="text-[10px] px-1.5 py-0.5 rounded font-bold bg-rose-100 text-rose-700">
                          {defCount} defects
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.5 rounded font-bold bg-emerald-100 text-emerald-700">
                          Clean
                        </span>
                      )}
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-bold ${
                        page.http_status >= 400
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-slate-100 text-slate-700'
                      }`}>
                        {page.http_status ? `HTTP ${page.http_status}` : '200'}
                      </span>
                    </div>
                  </div>

                  <div className="text-[11px] text-slate-500 truncate mt-0.5" title={page.url}>
                    {page.url}
                  </div>

                  {page.baseline_url ? (
                    <div className="text-[10px] text-blue-600 truncate mt-1 flex items-center gap-1 font-medium" title={page.baseline_url}>
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span>
                      <span>Ref: {page.baseline_url}</span>
                    </div>
                  ) : null}

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

        {/* Right Column: Visual Evidence Viewport (Side-by-Side or Annotated) */}
        <div className="bg-white border border-slate-200 rounded-2xl p-5 card-shadow lg:col-span-2 space-y-4">
          
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <Eye className="w-3.5 h-3.5 text-[#0696D7]" />
                Visual Quality Evidence
              </h3>
              {previewPage && (
                <p className="text-xs text-slate-500 truncate max-w-md mt-0.5" title={previewPage.url}>
                  {previewPage.title || previewPage.url}
                </p>
              )}
            </div>

            {/* View Mode Switcher */}
            {hasBaseline && (
              <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-100 border border-slate-200">
                <button
                  onClick={() => setViewMode('side_by_side')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                    viewMode === 'side_by_side'
                      ? 'bg-[#0696D7] text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Split className="w-3.5 h-3.5" />
                  <span>Side-by-Side</span>
                </button>

                <button
                  onClick={() => setViewMode('annotated')}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                    viewMode === 'annotated'
                      ? 'bg-[#0696D7] text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                  }`}
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Defects Highlighted</span>
                </button>

                {previewPage?.heatmap_b64 && (
                  <button
                    onClick={() => setViewMode('heatmap')}
                    className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                      viewMode === 'heatmap'
                        ? 'bg-[#0696D7] text-white shadow-sm'
                        : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                    }`}
                  >
                    <Flame className="w-3.5 h-3.5" />
                    <span>Heatmap</span>
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Viewport Display */}
          <div className="bg-slate-50 rounded-xl border border-slate-200 p-3 min-h-[340px] flex items-center justify-center">
            
            {/* 1. SIDE-BY-SIDE PAIRWISE VIEW */}
            {hasBaseline && viewMode === 'side_by_side' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                
                {/* English Baseline Reference */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between px-1">
                    <span className="text-xs font-bold text-blue-800 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                      English Baseline (Passed Standard)
                    </span>
                    <span className="text-[10px] text-slate-400 font-semibold">Reference</span>
                  </div>
                  <div className="rounded-lg overflow-hidden border border-slate-300 bg-white shadow-sm flex items-center justify-center min-h-[220px]">
                    {previewPage?.baseline_b64 ? (
                      <img
                        src={previewPage.baseline_b64}
                        alt="English Baseline"
                        className="w-full object-contain max-h-[360px]"
                      />
                    ) : (
                      <span className="text-xs text-slate-400 p-4">Baseline image loading...</span>
                    )}
                  </div>
                </div>

                {/* Localized Target with Highlights */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between px-1">
                    <span className="text-xs font-bold text-rose-700 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-rose-600"></span>
                      Localized Target (with Defect Boxes)
                    </span>
                    <span className="text-[10px] font-bold text-rose-600">
                      {previewPage?.defects_count ?? 0} defects marked
                    </span>
                  </div>
                  <div className="rounded-lg overflow-hidden border border-slate-300 bg-white shadow-sm flex items-center justify-center min-h-[220px] relative group">
                    {previewPage?.annotated_b64 || previewPage?.screenshot_b64 ? (
                      <>
                        <img
                          src={previewPage.annotated_b64 || previewPage.screenshot_b64}
                          alt="Localized Target Annotated"
                          className="w-full object-contain max-h-[360px]"
                        />
                        <button
                          type="button"
                          onClick={() => setZoomImage(previewPage.annotated_b64 || previewPage.screenshot_b64)}
                          className="absolute bottom-2 right-2 bg-slate-900/80 hover:bg-slate-900 text-white text-xs px-2.5 py-1 rounded-lg font-bold flex items-center gap-1 opacity-0 group-hover:opacity-100 transition shadow-md backdrop-blur-sm"
                        >
                          <Maximize2 className="w-3 h-3" /> Zoom
                        </button>
                      </>
                    ) : (
                      <span className="text-xs text-slate-400 p-4">Screenshot not available</span>
                    )}
                  </div>
                </div>

              </div>
            )}

            {/* 2. ANNOTATED SINGLE FULL VIEW */}
            {(!hasBaseline || viewMode === 'annotated') && (
              <div className="relative w-full overflow-hidden flex items-center justify-center group">
                {previewPage?.annotated_b64 || previewPage?.screenshot_b64 ? (
                  <>
                    <img
                      src={previewPage.annotated_b64 || previewPage.screenshot_b64}
                      alt="Page quality evidence"
                      className="w-full object-contain max-h-[380px] rounded-lg shadow-sm"
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
                    No image preview available for this page.
                  </div>
                )}
              </div>
            )}

            {/* 3. DIFFERENCE HEATMAP */}
            {hasBaseline && viewMode === 'heatmap' && previewPage?.heatmap_b64 && (
              <div className="relative w-full overflow-hidden flex items-center justify-center">
                <img
                  src={previewPage.heatmap_b64}
                  alt="Difference Heatmap"
                  className="w-full object-contain max-h-[380px] rounded-lg shadow-sm"
                />
              </div>
            )}

          </div>

          {/* Element Breakdown Chips */}
          {previewPage?.element_counts && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[10px] font-bold text-slate-400 uppercase mr-1">DOM Elements:</span>
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

      {/* 3. Detailed Filterable Findings & Diagnostic Records Table */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow space-y-4">
        
        {/* Table Filters Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Audit Findings & Element Diagnostic Records ({filteredIssues.length})
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Click any finding or Preview button to view side-by-side visual crops and engineering CSS fixes
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
                <th className="px-3.5 py-3 text-center">Evidence & Crops</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {filteredIssues.map((row, idx) => {
                const isFail = row.Status === 'FAIL';
                const category = row.Category || row.Issue || 'Other';
                const hasEvidence = Boolean(row.EvidenceImage || row.crop_localized_b64 || row.crop_baseline_b64);

                return (
                  <tr
                    key={`${row.Page}-${row.Issue}-${idx}`}
                    onClick={() => handleOpenFinding(row)}
                    className="hover:bg-sky-50/50 transition cursor-pointer align-top"
                  >
                    
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
                      {row.Page ? (
                        <a
                          href={row.Page}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-[10px] text-slate-400 hover:text-[#0696D7] truncate mt-0.5 flex items-center gap-1 font-mono hover:underline"
                          title={`Open crawled page: ${row.Page}`}
                        >
                          <span className="truncate">{row.Page}</span>
                          <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                        </a>
                      ) : null}
                    </td>

                    {/* Expected Behavior */}
                    <td className="px-3.5 py-3 text-slate-600 max-w-[220px]">
                      {row.Expected || 'Element functions according to UI quality standards.'}
                    </td>

                    {/* Actual Behavior */}
                    <td className="px-3.5 py-3 text-slate-800 max-w-[260px]">
                      <div className="font-medium">{row.Actual || row.Details}</div>
                      {(() => {
                        let targetUrl = row.target_url || row.TargetUrl || '';
                        if (!targetUrl) {
                          const match = (row.Actual || row.Expected || row.Details || '').match(/https?:\/\/[^\s'")]+/);
                          if (match) targetUrl = match[0].replace(/['"]$/, '');
                        }
                        if (targetUrl) {
                          return (
                            <a
                              href={targetUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 px-2 py-0.5 mt-1.5 rounded-md bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 text-[10px] font-mono font-bold hover:underline transition max-w-full truncate"
                              title={`Open destination: ${targetUrl}`}
                            >
                              <ExternalLink className="w-3 h-3 shrink-0" />
                              <span className="truncate">Open Target URL ↗</span>
                            </a>
                          );
                        }
                        return null;
                      })()}
                    </td>

                    {/* Evidence Thumbnail / Action */}
                    <td className="px-3.5 py-3 text-center whitespace-nowrap">
                      {hasEvidence ? (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenFinding(row);
                          }}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 bg-slate-50 hover:bg-[#0696D7] hover:text-white hover:border-[#0696D7] text-[11px] font-bold text-slate-700 transition shadow-xs"
                        >
                          <Eye className="w-3.5 h-3.5" /> Inspect Crop
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

      {/* 5. Rich Finding Modal with Side-by-Side Crops & CSS Fixes */}
      {selectedFindingModal && (
        <FindingModal
          finding={selectedFindingModal}
          onClose={() => setSelectedFindingModal(null)}
        />
      )}

    </div>
  );
}
