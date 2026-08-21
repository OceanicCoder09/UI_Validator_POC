import React, { useState } from 'react';
import { X, ShieldAlert, AlertTriangle, AlertCircle, Copy, Check, Crosshair, Code2 } from 'lucide-react';

export default function FindingModal({ finding, onClose }) {
  const [copied, setCopied] = useState(false);

  if (!finding) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(finding.remediation);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isCritical = finding.severity === 'Critical';
  const isMajor = finding.severity === 'Major';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-white border border-slate-200 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 rounded bg-slate-900 text-white font-mono text-xs font-bold">
              {finding.id}
            </span>
            <span className="px-2 py-0.5 rounded bg-sky-100 text-sky-900 border border-sky-200 text-xs font-extrabold uppercase tracking-wider">
              {finding.category}
            </span>
            <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 ${
              isCritical
                ? 'bg-rose-100 text-rose-800 border border-rose-200'
                : isMajor
                  ? 'bg-amber-100 text-amber-800 border border-amber-200'
                  : 'bg-slate-100 text-slate-800 border border-slate-200'
            }`}>
              {isCritical ? <ShieldAlert className="w-3.5 h-3.5" /> : isMajor ? <AlertTriangle className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
              {finding.severity}
            </span>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 text-sm text-slate-800">
          
          {/* Title & Description */}
          <div className="space-y-1">
            <h2 className="text-lg font-bold text-slate-900">
              {finding.title}
            </h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              {finding.description}
            </p>
          </div>

          {/* Coordinate Details */}
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-700">
              <Crosshair className="w-4 h-4 text-[#0696D7]" />
              <span>Bounding Box:</span>
              <strong className="text-slate-900">X={finding.location.x}px</strong>
              <span>|</span>
              <strong className="text-slate-900">Y={finding.location.y}px</strong>
              <span>|</span>
              <strong className="text-slate-900">W={finding.location.width}px</strong>
              <span>|</span>
              <strong className="text-slate-900">H={finding.location.height}px</strong>
            </div>

            <span className="text-[11px] font-bold text-[#0696D7] bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
              OpenCV Region
            </span>
          </div>

          {/* Large Side-by-Side Comparison */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            
            {/* English Baseline */}
            <div className="space-y-2 p-4 rounded-xl bg-slate-50 border border-slate-200">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-blue-700 uppercase tracking-wider">
                  English Baseline Reference
                </span>
                <span className="text-[10px] text-slate-500 font-semibold">Expected State</span>
              </div>
              <div className="h-48 bg-white rounded-lg overflow-hidden flex items-center justify-center p-2 border border-slate-200 shadow-sm">
                {finding.crop_baseline_b64 ? (
                  <img
                    src={finding.crop_baseline_b64}
                    alt="English Baseline Crop"
                    className="max-h-full max-w-full object-contain rounded"
                  />
                ) : (
                  <span className="text-xs text-slate-400">Baseline crop not available</span>
                )}
              </div>
            </div>

            {/* Localized Defect */}
            <div className="space-y-2 p-4 rounded-xl bg-slate-50 border border-slate-200">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">
                  Localized Defect View
                </span>
                <span className="text-[10px] text-rose-600 font-semibold">Actual Flaw</span>
              </div>
              <div className="h-48 bg-white rounded-lg overflow-hidden flex items-center justify-center p-2 border border-slate-200 shadow-sm">
                {finding.crop_localized_b64 ? (
                  <img
                    src={finding.crop_localized_b64}
                    alt="Localized Defect Crop"
                    className="max-h-full max-w-full object-contain rounded"
                  />
                ) : (
                  <span className="text-xs text-slate-400">Localized crop not available</span>
                )}
              </div>
            </div>

          </div>

          {/* Root Cause & Remediation */}
          <div className="space-y-3">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Expected vs Actual UI Behavior
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="font-semibold text-slate-600 block">Expected:</span>
                  <p className="text-slate-800 mt-0.5">{finding.expected}</p>
                </div>
                <div>
                  <span className="font-semibold text-slate-600 block">Actual:</span>
                  <p className="text-rose-700 font-medium mt-0.5">{finding.actual}</p>
                </div>
              </div>
            </div>

            {/* CSS Fix Box */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <Code2 className="w-4 h-4 text-[#0696D7]" />
                  <span>Recommended CSS Fix</span>
                </h4>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 text-xs font-bold text-[#0696D7] hover:text-[#0284C7]"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied!' : 'Copy Code'}</span>
                </button>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto select-all">
                <code className="text-emerald-400">{finding.remediation}</code>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
