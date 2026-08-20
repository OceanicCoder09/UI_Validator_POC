import React, { useState } from 'react';
import { Upload, ArrowRight, RefreshCw, Globe, Image as ImageIcon, Sparkles } from 'lucide-react';

export default function ImageUploader({
  englishImage,
  localizedImage,
  onEnglishUpload,
  onLocalizedUpload,
  onAnalyze,
  isAnalyzing,
  onClear,
  onUrlAnalyze,
  isUrlAnalyzing
}) {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'url'
  const [englishUrl, setEnglishUrl] = useState('https://help.autodesk.com/view/OARX/2024/ENU/');
  const [localizedUrl, setLocalizedUrl] = useState('https://help.autodesk.com/view/OARX/2024/DEU/');

  const handleFile = (e, isEnglish) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      if (isEnglish) {
        onEnglishUpload(file, reader.result);
      } else {
        onLocalizedUpload(file, reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e, isEnglish) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      if (isEnglish) {
        onEnglishUpload(file, reader.result);
      } else {
        onLocalizedUpload(file, reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleUrlSubmit = (e) => {
    e.preventDefault();
    if (!englishUrl || !localizedUrl) return;
    if (onUrlAnalyze) {
      onUrlAnalyze(englishUrl, localizedUrl);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 card-shadow space-y-6">
      
      {/* Mode Switcher Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div>
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#0696D7]"></span>
            Screenshot Comparison Input
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {activeTab === 'upload'
              ? 'Upload manual screenshots or select a test scenario above'
              : 'Enter live web URLs for automated headless browser capture'}
          </p>
        </div>

        <div className="flex items-center gap-2 bg-slate-100 p-1 rounded-xl">
          <button
            type="button"
            onClick={() => setActiveTab('upload')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === 'upload'
                ? 'bg-white text-[#0696D7] shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <ImageIcon className="w-3.5 h-3.5" />
            <span>Upload Images</span>
          </button>
          
          <button
            type="button"
            onClick={() => setActiveTab('url')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              activeTab === 'url'
                ? 'bg-white text-[#0696D7] shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            <span>Auto-Capture URL</span>
            <span className="px-1.5 py-0.2 text-[9px] bg-emerald-100 text-emerald-700 rounded font-bold">New</span>
          </button>
        </div>
      </div>

      {/* TAB 1: MANUAL IMAGE UPLOAD */}
      {activeTab === 'upload' && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* English Baseline Box */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-700">1. English Baseline (Reference)</span>
                {englishImage && (
                  <span className="text-slate-400 truncate max-w-[200px]">
                    {englishImage.name}
                  </span>
                )}
              </div>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => handleDrop(e, true)}
                className={`relative border-2 border-dashed rounded-xl h-56 flex flex-col items-center justify-center text-center p-4 transition ${
                  englishImage
                    ? 'border-[#0696D7]/40 bg-[#0696D7]/5'
                    : 'border-slate-300 hover:border-[#0696D7]/50 bg-slate-50'
                }`}
              >
                {englishImage?.preview ? (
                  <div className="relative w-full h-full flex items-center justify-center group overflow-hidden rounded-lg">
                    <img
                      src={englishImage.preview}
                      alt="English Baseline"
                      className="max-h-full max-w-full object-contain rounded"
                    />
                    <label className="absolute inset-0 bg-slate-900/60 text-white flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition cursor-pointer text-xs font-semibold gap-1.5 backdrop-blur-[2px]">
                      <Upload className="w-5 h-5" />
                      <span>Change Baseline Image</span>
                      <input
                        type="file"
                        accept="image/png, image/jpeg, image/webp"
                        className="hidden"
                        onChange={(e) => handleFile(e, true)}
                      />
                    </label>
                  </div>
                ) : (
                  <label className="cursor-pointer flex flex-col items-center justify-center gap-2 text-slate-500 hover:text-[#0696D7] transition">
                    <div className="w-10 h-10 rounded-full bg-slate-200/70 flex items-center justify-center text-slate-600">
                      <Upload className="w-5 h-5" />
                    </div>
                    <span className="text-xs font-bold text-slate-700">
                      Drop English Screenshot Here
                    </span>
                    <span className="text-[11px] text-slate-400">
                      or click to browse from files
                    </span>
                    <input
                      type="file"
                      accept="image/png, image/jpeg, image/webp"
                      className="hidden"
                      onChange={(e) => handleFile(e, true)}
                    />
                  </label>
                )}
              </div>
            </div>

            {/* Localized Screenshot Box */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-700">2. Localized Screenshot (Target)</span>
                {localizedImage && (
                  <span className="text-slate-400 truncate max-w-[200px]">
                    {localizedImage.name}
                  </span>
                )}
              </div>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => handleDrop(e, false)}
                className={`relative border-2 border-dashed rounded-xl h-56 flex flex-col items-center justify-center text-center p-4 transition ${
                  localizedImage
                    ? 'border-[#0696D7]/40 bg-[#0696D7]/5'
                    : 'border-slate-300 hover:border-[#0696D7]/50 bg-slate-50'
                }`}
              >
                {localizedImage?.preview ? (
                  <div className="relative w-full h-full flex items-center justify-center group overflow-hidden rounded-lg">
                    <img
                      src={localizedImage.preview}
                      alt="Localized UI"
                      className="max-h-full max-w-full object-contain rounded"
                    />
                    <label className="absolute inset-0 bg-slate-900/60 text-white flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition cursor-pointer text-xs font-semibold gap-1.5 backdrop-blur-[2px]">
                      <Upload className="w-5 h-5" />
                      <span>Change Localized Image</span>
                      <input
                        type="file"
                        accept="image/png, image/jpeg, image/webp"
                        className="hidden"
                        onChange={(e) => handleFile(e, false)}
                      />
                    </label>
                  </div>
                ) : (
                  <label className="cursor-pointer flex flex-col items-center justify-center gap-2 text-slate-500 hover:text-[#0696D7] transition">
                    <div className="w-10 h-10 rounded-full bg-slate-200/70 flex items-center justify-center text-slate-600">
                      <Upload className="w-5 h-5" />
                    </div>
                    <span className="text-xs font-bold text-slate-700">
                      Drop Localized Screenshot Here
                    </span>
                    <span className="text-[11px] text-slate-400">
                      or click to browse from files
                    </span>
                    <input
                      type="file"
                      accept="image/png, image/jpeg, image/webp"
                      className="hidden"
                      onChange={(e) => handleFile(e, false)}
                    />
                  </label>
                )}
              </div>
            </div>

          </div>

          {/* Action Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
            <button
              onClick={onClear}
              type="button"
              className="text-xs font-medium text-slate-500 hover:text-slate-800 flex items-center gap-1.5 px-3 py-2 rounded-lg hover:bg-slate-100 transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reset Selection</span>
            </button>

            <button
              onClick={onAnalyze}
              disabled={!englishImage || !localizedImage || isAnalyzing}
              className={`w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition active:scale-95 ${
                !englishImage || !localizedImage || isAnalyzing
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-[#0696D7] hover:bg-[#0284C7] text-white shadow-sky-200 hover:shadow-md'
              }`}
            >
              {isAnalyzing ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  <span>Running Computer Vision Analysis...</span>
                </>
              ) : (
                <>
                  <span>Compare & Check UI Quality</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </>
      )}

      {/* TAB 2: LIVE URL AUTO-CAPTURE */}
      {activeTab === 'url' && (
        <form onSubmit={handleUrlSubmit} className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                English Baseline Web URL
              </label>
              <input
                type="url"
                required
                value={englishUrl}
                onChange={(e) => setEnglishUrl(e.target.value)}
                placeholder="https://example.com/en/support"
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#0696D7] bg-slate-50"
              />
              <p className="text-[11px] text-slate-400">Reference URL rendered in headless Chromium (1280x800)</p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#0696D7]"></span>
                Localized Target Web URL
              </label>
              <input
                type="url"
                required
                value={localizedUrl}
                onChange={(e) => setLocalizedUrl(e.target.value)}
                placeholder="https://example.com/de/support"
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#0696D7] bg-slate-50"
              />
              <p className="text-[11px] text-slate-400">Target localized URL in German, Spanish, French, etc.</p>
            </div>

          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-slate-100">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Sparkles className="w-4 h-4 text-[#0696D7]" />
              <span>Headless browser will automatically navigate, capture both pages, and analyze layout consistency.</span>
            </div>

            <button
              type="submit"
              disabled={isUrlAnalyzing || !englishUrl || !localizedUrl}
              className={`w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition active:scale-95 ${
                isUrlAnalyzing || !englishUrl || !localizedUrl
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-[#0696D7] hover:bg-[#0284C7] text-white shadow-sky-200 hover:shadow-md'
              }`}
            >
              {isUrlAnalyzing ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  <span>Capturing Pages & Analyzing...</span>
                </>
              ) : (
                <>
                  <Globe className="w-4 h-4" />
                  <span>Auto-Capture & Analyze</span>
                </>
              )}
            </button>
          </div>
        </form>
      )}

    </div>
  );
}
