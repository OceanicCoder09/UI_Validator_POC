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
          All translated labels fit within their buttons, no elements were lost, and layout alignment is completely preserved.
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
            Autodesk LQA standardized defect codes, pixel bounding boxes, and remediation CSS:
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
              className="pl-8 pr-3 py-1.5 text-xs rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-[#0696D7] focus:bg-white text-slate-800 w-44"
            />
          </div>

          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl">
            {['ALL', 'CRITICAL', 'MAJOR', 'MINOR'].map((lvl) => (
              <button
                key={lvl}
                onClick={() => setSeverityFilter(lvl)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition ${
                  severityFilter === lvl
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>

        </div>
      </div>

      {/* Findings Cards List */}
      <div className="space-y-3">
        {filteredFindings.map((f) => {
          const isSelected = selectedFindingId === f.id;
          const isCopied = copiedId === f.id;

          return (
            <div
              key={f.id}
              onClick={() => onSelectFinding && onSelectFinding(f.id)}
              className={`p-4 rounded-xl border transition cursor-pointer relative ${
                isSelected
                  ? 'bg-sky-50/60 border-[#0696D7] shadow-md ring-1 ring-[#0696D7]'
                  : 'bg-white border-slate-200 hover:border-slate-300 hover:shadow-sm'
              }`}
            >
              
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                
                <div className="space-y-1.5 flex-1">
                  
                  {/* Autodesk Standard Code + Category Badges */}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="px-2.5 py-0.5 rounded bg-slate-900 text-white font-mono text-xs font-bold tracking-wide">
                      {f.id}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-sky-100 text-sky-900 border border-sky-200 text-[10px] font-extrabold uppercase tracking-wider">
                      {f.category}
                    </span>
                    {getBadge(f.severity)}
                  </div>

                  {/* Title & Description */}
                  <h3 className="text-sm font-bold text-slate-900 pt-0.5">
                    {f.title}
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {f.description}
                  </p>

                  {/* Coordinate and Dimensions Tag */}
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                      BBox: X={f.location.x}px, Y={f.location.y}px, W={f.location.width}px, H={f.location.height}px
                    </span>
                  </div>

                  {/* Remediation Snippet */}
                  <div className="mt-2.5 p-2.5 rounded-lg bg-slate-900 text-slate-100 text-xs font-mono flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 overflow-x-auto">
                      <Code2 className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                      <span className="text-emerald-400 font-semibold shrink-0">Fix:</span>
                      <code className="text-slate-200 text-[11px] truncate select-all">
                        {f.remediation}
                      </code>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopy(f.remediation, f.id);
                      }}
                      className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition shrink-0"
                      title="Copy Fix"
                    >
                      {isCopied ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>

                </div>

                {/* Inspect Details Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onOpenModal) onOpenModal(f);
                  }}
                  className="sm:self-center flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 transition active:scale-95 shrink-0"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Inspect</span>
                </button>

              </div>

            </div>
          );
        })}
      </div>

    </div>
  );
}
