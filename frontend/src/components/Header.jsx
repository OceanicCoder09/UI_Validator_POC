import React from 'react';
import { HelpCircle, RefreshCw, FileText, CheckCircle2 } from 'lucide-react';

export default function Header({ onOpenDocs, isAnalyzing, onReset }) {
  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#0696D7] flex items-center justify-center shadow-md shadow-sky-500/25">
            <svg viewBox="0 0 32 32" className="w-6 h-6 fill-white">
              <path d="M7 23 L15 7 L23 23 L18 23 L15 14 L12 23 Z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-black tracking-wider text-slate-900 text-sm">AUTODESK</span>
              <span className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-sky-100 text-sky-800 border border-sky-200">
                UI Quality Checker
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium">
              Automated Visual Quality Validation for Localized Helpdesk Portals
            </p>
          </div>
        </div>

        {/* Top actions */}
        <div className="flex items-center gap-2.5">
          
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs font-bold text-emerald-700">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>CV Engine Active</span>
          </div>

          {onReset && (
            <button
              onClick={onReset}
              disabled={isAnalyzing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition active:scale-95 disabled:opacity-50"
              title="Reset View"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isAnalyzing ? 'animate-spin' : ''}`} />
              <span>Reset</span>
            </button>
          )}

          <button
            onClick={onOpenDocs}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-[#0696D7] hover:bg-[#0284C7] text-white shadow-sm transition active:scale-95"
          >
            <HelpCircle className="w-4 h-4" />
            <span>How It Works</span>
          </button>

        </div>

      </div>
    </header>
  );
}
