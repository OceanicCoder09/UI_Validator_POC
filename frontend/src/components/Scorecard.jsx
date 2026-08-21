import React from 'react';
import { ShieldAlert, AlertTriangle, AlertCircle } from 'lucide-react';

export default function Scorecard({ results }) {
  if (!results) return null;

  const score = results?.score ?? 0;
  const grade_description = results?.grade_description || 'Analysis completed';
  const summary = results?.summary || {
    total_defects: 0,
    critical_count: 0,
    major_count: 0,
    minor_count: 0
  };

  const getScoreTheme = (s) => {
    if (s >= 90) return {
      card: 'bg-emerald-50 border-emerald-300 text-emerald-900',
      progress: 'bg-emerald-500',
      scoreText: 'text-emerald-700'
    };
    if (s >= 70) return {
      card: 'bg-sky-50 border-sky-300 text-sky-900',
      progress: 'bg-[#0696D7]',
      scoreText: 'text-sky-700'
    };
    if (s >= 50) return {
      card: 'bg-amber-50 border-amber-300 text-amber-900',
      progress: 'bg-amber-500',
      scoreText: 'text-amber-700'
    };
    return {
      card: 'bg-rose-50 border-rose-300 text-rose-900',
      progress: 'bg-rose-500',
      scoreText: 'text-rose-700'
    };
  };

  const theme = getScoreTheme(score);

  return (
    <div className="space-y-4">
      
      {/* Big Summary Score Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          
          {/* Main Score Box (Scores kept, Grade removed) */}
          <div className="lg:col-span-5 flex items-center gap-5 border-b lg:border-b-0 lg:border-r border-slate-200 pb-6 lg:pb-0 lg:pr-6">
            <div className={`w-24 h-24 rounded-2xl flex flex-col items-center justify-center border-2 shadow-sm shrink-0 ${theme.card}`}>
              <span className={`text-3xl font-black ${theme.scoreText}`}>{score}</span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">out of 100</span>
            </div>

            <div className="space-y-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Quality Score
              </span>
              <h2 className="text-base font-bold text-slate-900 leading-tight">
                {score === 100 ? "Clean UI — No Visual Defects Detected" : grade_description}
              </h2>
              <div className="flex items-center gap-2 pt-1.5">
                <div className="w-28 h-2.5 rounded-full bg-slate-200 overflow-hidden">
                  <div 
                    className={`h-full ${theme.progress} transition-all duration-700`} 
                    style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                  ></div>
                </div>
                <span className="text-xs font-bold text-slate-700">{score}% Integrity</span>
              </div>
            </div>
          </div>

          {/* 4 Summary Metric Cards */}
          <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-4 gap-3">
            
            {/* Total Issues */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex flex-col justify-between">
              <span className="text-[11px] font-bold text-slate-500">Total Defects</span>
              <div className="mt-1">
                <span className="text-2xl font-black text-slate-900">
                  {summary.total_defects ?? 0}
                </span>
                <span className="text-[10px] text-slate-400 ml-1 font-medium">Found</span>
              </div>
            </div>

            {/* Critical */}
            <div className={`p-3.5 rounded-xl border flex flex-col justify-between ${
              (summary.critical_count ?? 0) > 0 
                ? 'bg-rose-50 border-rose-200 text-rose-800' 
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold">Critical</span>
                <ShieldAlert className="w-3.5 h-3.5" />
              </div>
              <div className="mt-1">
                <span className="text-2xl font-black text-rose-700">
                  {summary.critical_count ?? 0}
                </span>
                <span className="text-[10px] text-slate-500 ml-1 font-medium">Missing / Overflow</span>
              </div>
            </div>

            {/* Major */}
            <div className={`p-3.5 rounded-xl border flex flex-col justify-between ${
              (summary.major_count ?? 0) > 0 
                ? 'bg-amber-50 border-amber-200 text-amber-800' 
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold">Major</span>
                <AlertTriangle className="w-3.5 h-3.5" />
              </div>
              <div className="mt-1">
                <span className="text-2xl font-black text-amber-700">
                  {summary.major_count ?? 0}
                </span>
                <span className="text-[10px] text-slate-500 ml-1 font-medium">Layout Shifts</span>
              </div>
            </div>

            {/* Minor */}
            <div className={`p-3.5 rounded-xl border flex flex-col justify-between ${
              (summary.minor_count ?? 0) > 0 
                ? 'bg-amber-50/60 border-amber-200 text-amber-800' 
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold">Minor</span>
                <AlertCircle className="w-3.5 h-3.5" />
              </div>
              <div className="mt-1">
                <span className="text-2xl font-black text-slate-800">
                  {summary.minor_count ?? 0}
                </span>
                <span className="text-[10px] text-slate-500 ml-1 font-medium">Alignment</span>
              </div>
            </div>

          </div>

        </div>
      </div>

    </div>
  );
}
