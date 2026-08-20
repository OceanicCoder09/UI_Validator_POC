import React from 'react';
import { CheckCircle2, AlertCircle, AlertTriangle, ShieldAlert, Layers } from 'lucide-react';

export default function Scorecard({ results }) {
  if (!results) return null;

  const { score, grade, grade_description, summary } = results;

  const getTheme = (g) => {
    if (g.startsWith('A')) return {
      card: 'bg-emerald-50 border-emerald-300 text-emerald-900',
      badge: 'bg-emerald-600 text-white',
      progress: 'bg-emerald-500',
      scoreText: 'text-emerald-700'
    };
    if (g.startsWith('B')) return {
      card: 'bg-sky-50 border-sky-300 text-sky-900',
      badge: 'bg-[#0696D7] text-white',
      progress: 'bg-[#0696D7]',
      scoreText: 'text-sky-700'
    };
    if (g.startsWith('C')) return {
      card: 'bg-amber-50 border-amber-300 text-amber-900',
      badge: 'bg-amber-500 text-white',
      progress: 'bg-amber-500',
      scoreText: 'text-amber-700'
    };
    return {
      card: 'bg-rose-50 border-rose-300 text-rose-900',
      badge: 'bg-rose-600 text-white',
      progress: 'bg-rose-500',
      scoreText: 'text-rose-700'
    };
  };

  const theme = getTheme(grade);

  return (
    <div className="space-y-4">
      
      {/* Big Bright Summary Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          
          {/* Main Score Box */}
          <div className="lg:col-span-5 flex items-center gap-5 border-b lg:border-b-0 lg:border-r border-slate-200 pb-6 lg:pb-0 lg:pr-6">
            <div className={`w-24 h-24 rounded-2xl flex flex-col items-center justify-center border-2 shadow-sm relative shrink-0 ${theme.card}`}>
              <span className={`text-3xl font-black ${theme.scoreText}`}>{score}</span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">out of 100</span>
              <div className={`absolute -top-2 -right-2 px-2 py-0.5 rounded-md text-[11px] font-black shadow ${theme.badge}`}>
                Grade {grade}
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                UI Quality Result
              </span>
              <h2 className="text-base font-bold text-slate-900 leading-tight">
                {grade_description}
              </h2>
              <div className="flex items-center gap-2 pt-1.5">
                <div className="w-28 h-2.5 rounded-full bg-slate-200 overflow-hidden">
                  <div 
                    className={`h-full ${theme.progress} transition-all duration-700`} 
                    style={{ width: `${score}%` }}
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
                  {summary.total_defects}
                </span>
                <span className="text-[10px] text-slate-400 ml-1 font-medium">Found</span>
              </div>
            </div>

            {/* Critical */}
            <div className={`p-3.5 rounded-xl border flex flex-col justify-between ${
              summary.critical_count > 0 
                ? 'bg-rose-50 border-rose-200 text-rose-800' 
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold">Critical</span>
                <ShieldAlert className="w-3.5 h-3.5" />
              </div>
              <div className="mt-1">
                <span className="text-2xl font-black text-rose-700">
                  {summary.critical_count}
                </span>
                <span className="text-[10px] text-slate-500 ml-1 font-medium">Missing / Clash</span>
              </div>
            </div>

            {/* Major */}
            <div className={`p-3.5 rounded-xl border flex flex-col justify-between ${
              summary.major_count > 0 
                ? 'bg-amber-50 border-amber-200 text-amber-800' 
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold">Major</span>
                <AlertTriangle className="w-3.5 h-3.5" />
              </div>
              <div className="mt-1">
                <span className="text-2xl font-black text-amber-700">
                  {summary.major_count}
                </span>
                <span className="text-[10px] text-slate-500 ml-1 font-medium">Layout Shifts</span>
              </div>
            </div>

            {/* Minor */}
            <div className={`p-3.5 rounded-xl border flex flex-col justify-between ${
              summary.minor_count > 0 
                ? 'bg-amber-50/60 border-amber-200 text-amber-800' 
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold">Minor</span>
                <AlertCircle className="w-3.5 h-3.5" />
              </div>
              <div className="mt-1">
                <span className="text-2xl font-black text-slate-800">
                  {summary.minor_count}
                </span>
                <span className="text-[10px] text-slate-500 ml-1 font-medium">Alignment</span>
              </div>
            </div>

          </div>

        </div>
      </div>

      {/* 5 Quality Checks Summary Bar */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 card-shadow">
        <div className="flex items-center justify-between mb-3 px-1">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-800 uppercase tracking-wider">
            <Layers className="w-4 h-4 text-[#0696D7]" />
            <span>OpenCV Quality Checks Checklist</span>
          </div>
          <span className="text-xs font-semibold text-slate-500">
            5 Checks Performed
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
          {summary.checks_performed.map((chk, i) => {
            const isPassed = chk.status === 'Passed';
            return (
              <div
                key={i}
                className={`p-3 rounded-xl border flex items-center justify-between ${
                  isPassed
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-rose-50 border-rose-200 text-rose-900'
                }`}
              >
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider block text-slate-500">
                    {chk.severity}
                  </span>
                  <h4 className="text-xs font-bold text-slate-900">{chk.name}</h4>
                </div>
                {isPassed ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-100 text-emerald-700 border border-emerald-300">
                    PASS
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-100 text-rose-700 border border-rose-300">
                    DEFECT
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

    </div>
  );
}
