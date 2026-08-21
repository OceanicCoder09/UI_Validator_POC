import React, { useState } from 'react';
import { Split, Layers, Flame } from 'lucide-react';

export default function DiffViewer({ 
  images, 
  findings, 
  selectedFindingId, 
  onSelectFinding 
}) {
  const [viewMode, setViewMode] = useState('side_by_side'); // 'side_by_side', 'annotated', 'heatmap'

  if (!images) return null;

  const { baseline_image, localized_image, annotated_diff_image, heatmap_image } = images;

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow space-y-4">
      
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-200">
        
        {/* View Mode Buttons */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-slate-100 border border-slate-200">
          
          <button
            onClick={() => setViewMode('side_by_side')}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
              viewMode === 'side_by_side'
                ? 'bg-[#0696D7] text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
          >
            <Split className="w-3.5 h-3.5" />
            <span>Side-by-Side Comparison</span>
          </button>

          <button
            onClick={() => setViewMode('annotated')}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
              viewMode === 'annotated'
                ? 'bg-[#0696D7] text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Defects Highlighted</span>
            {findings?.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[10px] font-black">
                {findings.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setViewMode('heatmap')}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
              viewMode === 'heatmap'
                ? 'bg-[#0696D7] text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-white'
            }`}
          >
            <Flame className="w-3.5 h-3.5" />
            <span>Difference Heatmap</span>
          </button>

        </div>

        <div className="text-xs text-slate-400 font-medium">
          Visual Quality Inspector
        </div>

      </div>

      {/* Main Image Display Viewport */}
      <div className="bg-slate-50 rounded-xl border border-slate-200 select-none p-3">

        {/* 1. SIDE BY SIDE */}
        {viewMode === 'side_by_side' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            
            {/* English Baseline */}
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span>
                  English Baseline Reference
                </span>
                <span className="text-[11px] text-slate-500 font-medium">Standard UI</span>
              </div>
              
              <div className="rounded-lg overflow-hidden border border-slate-300 bg-white shadow-sm">
                <img
                  src={baseline_image}
                  alt="English Baseline"
                  className="w-full h-auto object-contain block"
                />
              </div>
            </div>

            {/* Localized Image with Defect Highlights */}
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-bold text-[#0696D7] flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#0696D7]"></span>
                  Localized Screenshot (with defect boxes)
                </span>
                <span className="text-[11px] font-bold text-rose-600">
                  {findings?.length || 0} issues marked
                </span>
              </div>

              <div className="rounded-lg overflow-hidden border border-slate-300 bg-white shadow-sm">
                <img
                  src={annotated_diff_image}
                  alt="Localized Screenshot"
                  className="w-full h-auto object-contain block"
                />
              </div>
            </div>

          </div>
        )}

        {/* 2. ANNOTATED FULL VIEW */}
        {viewMode === 'annotated' && (
          <div className="space-y-2 p-1">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-bold text-slate-900">
                Visual Defect Map: Colored boxes highlight structural and boundary issues
              </span>
              <span className="text-xs font-bold text-rose-600">
                {findings?.length} Defects Detected
              </span>
            </div>
            <div className="max-w-5xl mx-auto rounded-lg overflow-hidden border border-slate-300 bg-white shadow-md">
              <img
                src={annotated_diff_image}
                alt="Annotated Difference"
                className="w-full h-auto object-contain block"
              />
            </div>
          </div>
        )}

        {/* 3. HEATMAP VIEW */}
        {viewMode === 'heatmap' && (
          <div className="space-y-2 p-1">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-bold text-slate-900">
                Structural Difference Heatmap (JET Colormap)
              </span>
              <span className="text-xs text-slate-500 font-medium">
                Red/Yellow = Structural Changes & Shifted Areas
              </span>
            </div>
            <div className="max-w-5xl mx-auto rounded-lg overflow-hidden border border-slate-300 bg-black shadow-md">
              <img
                src={heatmap_image}
                alt="Difference Heatmap"
                className="w-full h-auto object-contain block"
              />
            </div>
          </div>
        )}

      </div>

    </div>
  );
}
