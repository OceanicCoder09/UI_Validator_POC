import React, { useState } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  AlertCircle,
  Search,
  Copy,
  Check,
  ExternalLink,
  Code2,
  Sparkles
} from 'lucide-react';

export default function FindingsList({ findings, onSelectFinding, selectedFindingId, onOpenModal }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [copiedId, setCopiedId] = useState(null);

  if (!findings || findings.length === 0) {
    return (
      <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-8 card-shadow text-center space-y-2">
        <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
          <Sparkles className="w-6 h-6" />
        </div>
        <h3 className="text-base font-bold text-emerald-900">
          No UI Quality Issues Found!
        </h3>
        <p className="text-xs text-emerald-700 max-w-md mx-auto">
          All translated labels fit within their buttons, no buttons or icons were lost, and layout alignment is completely preserved.
        </p>
      </div>
    );
  }

  const filteredFindings = findings.filter(f => {
    const matchesSearch =
      f.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesSeverity =
      severityFilter === 'ALL' || f.severity.toUpperCase() === severityFilter;

    return matchesSearch && matchesSeverity;
  });

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getBadge = (sev) => {
    if (sev === 'Critical') {
      return (
        <span className="flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200">
          <ShieldAlert className="w-3.5 h-3.5 text-rose-600" /> CRITICAL
        </span>
      );
    }
    if (sev === 'Major') {
      return (
        <span className="flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> MAJOR
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-800 border border-slate-300">
        <AlertCircle className="w-3.5 h-3.5 text-slate-600" /> MINOR
      </span>
    );
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow space-y-5">

      {/* Header & Filters */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-200">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <span>Detected UI Quality Findings & Code Fixes</span>
            <span className="px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 text-xs font-bold border border-slate-200">
              {filteredFindings.length} Total
            </span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Compare expected baseline against localized flaws with exact pixel coordinates and CSS fixes:
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search findings..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-[#0696D7] transition w-44"
            />
          </div>

          <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-100 border border-slate-200">
            {['ALL', 'CRITICAL', 'MAJOR', 'MINOR'].map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition ${severityFilter === sev
                    ? 'bg-white text-[#0696D7] shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                  }`}
              >
                {sev}
              </button>
            ))}
          </div>

        </div>
      </div>

      {/* Findings Cards List */}
      <div className="space-y-4">
        {filteredFindings.map((finding) => {
          const isSelected = selectedFindingId === finding.id;
          const { location } = finding;

          return (
            <div
              key={finding.id}
              onClick={() => onSelectFinding?.(finding.id)}
              className={`rounded-xl border-2 transition-all p-5 space-y-4 cursor-pointer ${isSelected
                  ? 'bg-sky-50/40 border-[#0696D7] shadow-md'
                  : 'bg-slate-50/50 border-slate-200 hover:border-slate-300 hover:bg-white'
                }`}
            >

              {/* Finding Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-slate-900 text-white font-mono text-xs font-bold">
                    {finding.id}
                  </span>
                  {getBadge(finding.severity)}
                  <span className="text-xs font-bold text-slate-600">
                    {finding.category}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-slate-500 bg-white px-2 py-0.5 rounded border border-slate-200">
                    Region: ({location.x}, {location.y}, {location.width}×{location.height})
                  </span>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenModal(finding);
                    }}
                    className="p-1 rounded-lg bg-slate-100 hover:bg-[#0696D7] text-slate-600 hover:text-white transition"
                    title="Open Fullscreen Comparison"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Title & Description */}
              <div>
                <h3 className="text-sm font-bold text-slate-900 mb-1">
                  {finding.title}
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {finding.description}
                </p>
              </div>

              {/* Visual Side-by-Side Crop Snippets */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">

                {/* English Baseline */}
                <div className="p-3 rounded-xl bg-white border border-slate-200 space-y-1.5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-blue-700 uppercase tracking-wider">
                      English Reference
                    </span>
                    <span className="text-[10px] text-slate-400 font-semibold">Expected State</span>
                  </div>
                  <div className="h-20 bg-slate-50 rounded-lg overflow-hidden flex items-center justify-center p-1.5 border border-slate-200">
                    {finding.crop_baseline_b64 ? (
                      <img
                        src={finding.crop_baseline_b64}
                        alt="English Crop"
                        className="max-h-full max-w-full object-contain"
                      />
                    ) : (
                      <span className="text-[10px] text-slate-400">Crop not available</span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-600 line-clamp-1">
                    <strong>Expected:</strong> {finding.expected}
                  </p>
                </div>

                {/* Localized Defect */}
                <div className="p-3 rounded-xl bg-white border border-rose-200 space-y-1.5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-rose-700 uppercase tracking-wider">
                      Localized Flaw
                    </span>
                    <span className="text-[10px] font-bold text-rose-500">Detected Issue</span>
                  </div>
                  <div className="h-20 bg-slate-50 rounded-lg overflow-hidden flex items-center justify-center p-1.5 border border-rose-200">
                    {finding.crop_localized_b64 ? (
                      <img
                        src={finding.crop_localized_b64}
                        alt="Localized Crop"
                        className="max-h-full max-w-full object-contain"
                      />
                    ) : (
                      <span className="text-[10px] text-slate-400">Crop not available</span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-600 line-clamp-1">
                    <strong>Actual:</strong> {finding.actual}
                  </p>
                </div>

              </div>

              {/* Suggested Fix */}
              <div className="p-3 rounded-xl bg-sky-50 border border-sky-200 flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5">
                  <Code2 className="w-4 h-4 text-[#0696D7] shrink-0 mt-0.5" />
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-sky-800">
                      Recommended Engineering Fix
                    </span>
                    <p className="text-xs text-sky-950 font-medium mt-0.5">
                      {finding.remediation}
                    </p>
                  </div>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCopy(finding.remediation, finding.id);
                  }}
                  className="p-1.5 rounded-lg bg-sky-100 hover:bg-sky-200 text-sky-800 transition shrink-0"
                  title="Copy fix"
                >
                  {copiedId === finding.id ? (
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>

            </div>
          );
        })}
      </div>

    </div>
  );
}
