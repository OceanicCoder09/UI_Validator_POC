import React from 'react';
import { X, CheckCircle2, AlertTriangle, Info, ShieldCheck, FileCheck } from 'lucide-react';

export default function DocumentationModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl max-h-[90vh] bg-white border border-slate-200 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-sky-100 text-[#0696D7]">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">How the Localization UI Quality Checker Works</h2>
              <p className="text-xs text-slate-500">Autonomous Computer Vision & Geometric Heuristics</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-5 text-sm text-slate-700">
          
          {/* Concept Banner */}
          <div className="p-4 rounded-xl bg-sky-50 border border-sky-200 flex items-start gap-3">
            <Info className="w-5 h-5 text-[#0696D7] shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-sky-950 text-xs uppercase tracking-wider">UI Quality vs Translation Validation</h4>
              <p className="text-xs text-sky-900 mt-1 leading-relaxed">
                This tool is built to check <strong>Visual UI Quality</strong>, not translation text spelling.
                It knows that text is supposed to change (e.g. <em>"Submit"</em> → <em>"Senden"</em>), but buttons should NOT break, layout should NOT shift, and elements should NOT overlap.
              </p>
            </div>
          </div>

          {/* Expected vs Defects */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            
            <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-200">
              <div className="flex items-center gap-2 text-emerald-800 font-bold mb-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Normal Changes (NOT Defects)</span>
              </div>
              <ul className="space-y-1.5 text-xs text-slate-600">
                <li>• Button label text (*Submit* → *Fall übermitteln*)</li>
                <li>• Navigation tab labels</li>
                <li>• Form field labels & placeholders</li>
                <li>• Help messages & descriptions</li>
              </ul>
            </div>

            <div className="p-4 rounded-xl bg-rose-50/70 border border-rose-200">
              <div className="flex items-center gap-2 text-rose-800 font-bold mb-2">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
                <span>Flagged Quality Defects</span>
              </div>
              <ul className="space-y-1.5 text-xs text-slate-600">
                <li>• Missing buttons or missing icons</li>
                <li>• Text overflowing outside button boundaries</li>
                <li>• Components overlapping or colliding</li>
                <li>• Misaligned form inputs & ragged margins</li>
                <li>• Header or container layout shifts</li>
              </ul>
            </div>

          </div>

          {/* 5 Quality Checks */}
          <div className="space-y-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              5 Core Quality Checks
            </h3>
            
            <div className="space-y-2 text-xs">
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start gap-2.5">
                <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-bold shrink-0">MAJOR</span>
                <p><strong>1. Layout Shift Detection:</strong> Flags headers or navigation moved from their expected position.</p>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start gap-2.5">
                <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800 font-bold shrink-0">CRITICAL</span>
                <p><strong>2. Missing Component Detection:</strong> Detects buttons (like <em>Attach Log File</em>) or icons present in English but missing in localized UI.</p>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start gap-2.5">
                <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-800 font-bold shrink-0">MINOR</span>
                <p><strong>3. Alignment Validation:</strong> Checks for misaligned input fields or uneven margins.</p>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start gap-2.5">
                <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800 font-bold shrink-0">CRITICAL</span>
                <p><strong>4. Overlap Detection:</strong> Flags elements that overlap or collide with neighboring widgets.</p>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-start gap-2.5">
                <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800 font-bold shrink-0">CRITICAL</span>
                <p><strong>5. Localization Expansion Impact:</strong> Catches long German/Spanish text bursting out of buttons or getting truncated.</p>
              </div>
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-bold rounded-lg bg-[#0696D7] hover:bg-[#0284C7] text-white transition shadow-sm"
          >
            Got It
          </button>
        </div>

      </div>
    </div>
  );
}
