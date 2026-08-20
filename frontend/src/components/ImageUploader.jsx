import React, { useRef } from 'react';
import { UploadCloud, CheckCircle2, X, Play, ArrowRight, Image as ImageIcon } from 'lucide-react';

export default function ImageUploader({
  englishImage,
  localizedImage,
  onEnglishUpload,
  onLocalizedUpload,
  onAnalyze,
  isAnalyzing,
  onClear
}) {
  const enInputRef = useRef(null);
  const locInputRef = useRef(null);

  const handleFileChange = (e, type) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const dataUrl = event.target.result;
        if (type === 'en') {
          onEnglishUpload(file, dataUrl);
        } else {
          onLocalizedUpload(file, dataUrl);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const isReady = englishImage && localizedImage;

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow space-y-6">
      
      {/* Section Title */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">
            Step 1: Upload Screenshots
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Select an English reference image and the localized screenshot to compare:
          </p>
        </div>
        {isReady && (
          <button
            onClick={onClear}
            disabled={isAnalyzing}
            className="text-xs font-semibold text-slate-500 hover:text-rose-600 transition px-2.5 py-1 rounded-lg hover:bg-rose-50"
          >
            Clear Images
          </button>
        )}
      </div>

      {/* Upload Zone Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* 1. English Reference Upload */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span>
              English Baseline (Reference)
            </span>
            {englishImage && (
              <span className="text-[11px] font-bold text-emerald-600 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Ready
              </span>
            )}
          </div>

          <div
            onClick={() => !englishImage && enInputRef.current?.click()}
            className={`relative h-52 rounded-xl border-2 border-dashed transition flex flex-col items-center justify-center p-4 text-center overflow-hidden ${
              englishImage
                ? 'border-slate-300 bg-slate-100'
                : 'border-slate-300 hover:border-[#0696D7] bg-slate-50 hover:bg-sky-50/40 cursor-pointer group'
            }`}
          >
            <input
              type="file"
              ref={enInputRef}
              onChange={(e) => handleFileChange(e, 'en')}
              accept="image/png, image/jpeg, image/webp"
              className="hidden"
            />

            {englishImage ? (
              <div className="relative w-full h-full group">
                <img
                  src={englishImage.preview}
                  alt="English Baseline"
                  className="w-full h-full object-contain rounded-lg"
                />
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onEnglishUpload(null, null);
                  }}
                  className="absolute top-2 right-2 p-1.5 rounded-lg bg-slate-900/80 hover:bg-rose-600 text-white transition shadow"
                  title="Remove image"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="absolute bottom-2 left-2 px-2.5 py-1 rounded bg-slate-900/80 text-[11px] text-white font-medium shadow">
                  {englishImage.name || 'en_baseline.png'}
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mx-auto group-hover:scale-110 transition">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-xs font-bold text-slate-800">
                    Upload English Reference Screenshot
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Click to browse or drag and drop (PNG, JPG)
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 2. Localized Screenshot Upload */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#0696D7]"></span>
              Localized Screenshot (Target Test)
            </span>
            {localizedImage && (
              <span className="text-[11px] font-bold text-emerald-600 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> Ready
              </span>
            )}
          </div>

          <div
            onClick={() => !localizedImage && locInputRef.current?.click()}
            className={`relative h-52 rounded-xl border-2 border-dashed transition flex flex-col items-center justify-center p-4 text-center overflow-hidden ${
              localizedImage
                ? 'border-slate-300 bg-slate-100'
                : 'border-slate-300 hover:border-[#0696D7] bg-slate-50 hover:bg-sky-50/40 cursor-pointer group'
            }`}
          >
            <input
              type="file"
              ref={locInputRef}
              onChange={(e) => handleFileChange(e, 'loc')}
              accept="image/png, image/jpeg, image/webp"
              className="hidden"
            />

            {localizedImage ? (
              <div className="relative w-full h-full group">
                <img
                  src={localizedImage.preview}
                  alt="Localized Screenshot"
                  className="w-full h-full object-contain rounded-lg"
                />
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onLocalizedUpload(null, null);
                  }}
                  className="absolute top-2 right-2 p-1.5 rounded-lg bg-slate-900/80 hover:bg-rose-600 text-white transition shadow"
                  title="Remove image"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="absolute bottom-2 left-2 px-2.5 py-1 rounded bg-slate-900/80 text-[11px] text-white font-medium shadow">
                  {localizedImage.name || 'localized_screenshot.png'}
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="w-12 h-12 rounded-full bg-sky-100 text-[#0696D7] flex items-center justify-center mx-auto group-hover:scale-110 transition">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-xs font-bold text-slate-800">
                    Upload Localized Screenshot (DE, ES, JA, etc.)
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Click to browse or drag and drop (PNG, JPG)
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Step 2: Compare Action Button */}
      <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
        <div className="text-xs text-slate-600 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>
            {isReady
              ? 'Both images are ready. Click below to run OpenCV comparison.'
              : 'Pick a preset above or upload two images to begin.'}
          </span>
        </div>

        <button
          onClick={onAnalyze}
          disabled={!isReady || isAnalyzing}
          className={`w-full sm:w-auto px-8 py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2.5 shadow-md transition active:scale-95 ${
            isReady && !isAnalyzing
              ? 'bg-[#0696D7] hover:bg-[#0284C7] text-white button-glow cursor-pointer'
              : 'bg-slate-200 text-slate-400 cursor-not-allowed'
          }`}
        >
          {isAnalyzing ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
              <span>Running Computer Vision Checks...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-white" />
              <span>Compare & Check UI Quality</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </div>

    </div>
  );
}
