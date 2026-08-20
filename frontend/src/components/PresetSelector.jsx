import React from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, Play } from 'lucide-react';

export default function PresetSelector({ presets, activePresetId, onSelectPreset, isAnalyzing }) {
  if (!presets || !Array.isArray(presets)) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow space-y-4">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#0696D7]"></span>
            <h2 className="text-base font-bold text-slate-900">
              Interactive Demos: Click a Case Study Below
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Demonstrate real-world localized UI scenarios across German, Spanish, and Japanese Autodesk Helpdesk pages:
          </p>
        </div>
        <span className="text-xs font-bold px-3 py-1 rounded-full bg-sky-50 text-[#0696D7] border border-sky-200 self-start sm:self-auto">
          1-Click Demos
        </span>
      </div>

      {/* 4 Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {presets.map((p) => {
          const isSelected = activePresetId === p.id;
          const isPass = p.id === 'de_perfect';
          const isSevere = p.id === 'ja_shift_overlap' || p.id === 'es_missing_misaligned';

          return (
            <button
              key={p.id}
              onClick={() => onSelectPreset(p.id)}
              disabled={isAnalyzing}
              className={`text-left p-4 rounded-xl border-2 transition-all flex flex-col justify-between group ${
                isSelected
                  ? 'bg-sky-50/80 border-[#0696D7] ring-2 ring-sky-200 shadow-md'
                  : 'bg-slate-50/60 border-slate-200 hover:border-sky-300 hover:bg-white hover:shadow-sm'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <div>
                {/* Badge */}
                <div className="flex items-center justify-between mb-2.5">
                  <span className={`text-[11px] font-extrabold px-2.5 py-0.5 rounded-md ${
                    isPass 
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' 
                      : isSevere 
                        ? 'bg-rose-100 text-rose-800 border border-rose-300'
                        : 'bg-amber-100 text-amber-800 border border-amber-300'
                  }`}>
                    {isPass ? '✓ Clean UI (100%)' : isSevere ? '✕ Defect Present' : '! Overflow'}
                  </span>

                  {isPass ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  ) : isSevere ? (
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  )}
                </div>

                {/* Title */}
                <h3 className="text-xs font-extrabold text-slate-900 group-hover:text-[#0696D7] transition">
                  {p.title}
                </h3>
                <p className="text-[11px] text-slate-600 mt-2 line-clamp-2 leading-relaxed">
                  {p.description}
                </p>
              </div>

              {/* Action label */}
              <div className="mt-3.5 pt-2.5 border-t border-slate-200/80 flex items-center justify-between text-[11px]">
                <span className="font-bold text-slate-400">
                  {p.language || p.expected_result || 'Test Preset'}
                </span>
                <span className={`flex items-center gap-1 font-bold ${
                  isSelected ? 'text-[#0696D7]' : 'text-slate-600 group-hover:text-[#0696D7]'
                }`}>
                  <Play className={`w-3 h-3 ${isSelected ? 'fill-[#0696D7]' : ''}`} />
                  <span>{isSelected ? 'Currently Viewing' : 'Run Demo'}</span>
                </span>
              </div>
            </button>
          );
        })}
      </div>

    </div>
  );
}
