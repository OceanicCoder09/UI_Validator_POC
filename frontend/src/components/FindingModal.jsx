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
            <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 ${isCritical
                ? 'bg-rose-100 text-rose-800 border border-rose-200'
                : isMajor
                  ? 'bg-amber-100 text-amber-800 border border-amber-200'
                  : 'bg-slate-100 text-slate-800 border border-slate-200'
              }`}>
              {isCritical ? <ShieldAlert className="w-3.5 h-3.5" /> : isMajor ? <AlertTriangle className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
              {finding.severity}
            </span>
            <span className="text-xs font-bold text-slate-600">
              {finding.category}
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
                {finding.crop_baseline_b64 && (
                  <img
                    src={finding.crop_baseline_b64}
                    alt="English Baseline Crop"
                    className="max-h-full max-w-full object-contain rounded"
                  />
                )}
              </div>
              <p className="text-xs text-slate-700">
                <strong>Expected:</strong> {finding.expected}
              </p>
            </div>

            {/* Localized Finding */}
            <div className="space-y-2 p-4 rounded-xl bg-rose-50/50 border border-rose-200">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-rose-700 uppercase tracking-wider">
                  Localized Defect Area
                </span>
                <span className="text-[10px] text-rose-600 font-bold">Detected Flaw</span>
              </div>
              <div className="h-48 bg-white rounded-lg overflow-hidden flex items-center justify-center p-2 border border-rose-200 shadow-sm">
                {finding.crop_localized_b64 && (
                  <img
                    src={finding.crop_localized_b64}
                    alt="Localized Crop"
                    className="max-h-full max-w-full object-contain rounded"
                  />
                )}
              </div>
              <p className="text-xs text-slate-700">
                <strong>Actual:</strong> {finding.actual}
              </p>
            </div>

          </div>

          {/* Remediation Fix */}
          <div className="p-4 rounded-xl bg-sky-50 border border-sky-200 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-sky-900 flex items-center gap-1.5">
                <Code2 className="w-4 h-4 text-[#0696D7]" />
                <span>Recommended Engineering Fix</span>
              </span>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-lg bg-white hover:bg-sky-100 text-sky-800 border border-sky-300 transition"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied!' : 'Copy Fix'}</span>
              </button>
            </div>
            <p className="text-xs font-medium text-slate-800 bg-white p-3 rounded-lg border border-sky-200 leading-relaxed shadow-sm">
              {finding.remediation}
            </p>
          </div>

        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-bold rounded-lg bg-slate-800 hover:bg-slate-900 text-white transition"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}
