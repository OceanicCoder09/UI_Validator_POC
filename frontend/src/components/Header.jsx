import React from 'react';
import { HelpCircle, RefreshCw } from 'lucide-react';
import AutodeskLogo from './AutodeskLogo';

export default function Header({ onOpenDocs, isAnalyzing, onReset }) {
  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        
        {/* Brand with Sharp Autodesk Logo */}
        <div className="flex items-center gap-3.5">
          <AutodeskLogo className="h-7 w-auto" />
          
          <div className="h-6 w-px bg-slate-200 hidden sm:block"></div>

          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 text-[11px] font-bold bg-slate-900 text-white tracking-wide">
                UI Quality Checker
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium hidden md:block">
              Automated Visual Quality Validation for Localized Helpdesk Portals
            </p>
          </div>
        </div>

        {/* Top actions */}
        <div className="flex items-center gap-2.5">
          
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 border border-emerald-200 text-xs font-bold text-emerald-700">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>CV Engine Active</span>
          </div>

          {onReset && (
            <button
              onClick={onReset}
              disabled={isAnalyzing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 transition active:scale-95 disabled:opacity-50"
              title="Reset View"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isAnalyzing ? 'animate-spin' : ''}`} />
              <span>Reset</span>
            </button>
          )}

          <button
            onClick={onOpenDocs}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-bold bg-[#0696D7] hover:bg-[#0284C7] text-white shadow-sm transition active:scale-95"
          >
            <HelpCircle className="w-4 h-4" />
            <span>How It Works</span>
          </button>

        </div>

      </div>
    </header>
  );
}
