import React, { useState } from 'react';
import { Upload, ArrowRight, RefreshCw, Globe, Image as ImageIcon, Sparkles, Network } from 'lucide-react';

export default function ImageUploader({
  englishImage,
  localizedImage,
  onEnglishUpload,
  onLocalizedUpload,
  onAnalyze,
  isAnalyzing,
  onClear,
  onUrlAnalyze,
  isUrlAnalyzing,
  onCrawl,
  isCrawling
}) {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload' | 'url' | 'crawl'
  const [englishUrl, setEnglishUrl] = useState('');
  const [localizedUrl, setLocalizedUrl] = useState('');
  const [rootUrl, setRootUrl] = useState('');
  const [baselineRootUrl, setBaselineRootUrl] = useState('');
  const [maxDepth, setMaxDepth] = useState(2);
  const [maxPages, setMaxPages] = useState(10);
  const [checkLinks, setCheckLinks] = useState(true);
  const [checkImages, setCheckImages] = useState(true);
  const [checkInteractions, setCheckInteractions] = useState(true);
  const [safeInteractionsOnly, setSafeInteractionsOnly] = useState(true);

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
            Quality Validation Mode
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {activeTab === 'upload'
              ? 'Upload the English baseline reference and Localized target screenshot'
              : activeTab === 'url'
                ? 'Enter live web URLs for automated single-page headless browser capture'
                : 'Crawl entire website and compare matching pages against English baseline'}
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
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('crawl')}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
              activeTab === 'crawl'
                ? 'bg-white text-[#0696D7] shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>2-Language Site Crawl</span>
            <span className="px-1.5 py-0.2 text-[9px] bg-emerald-100 text-emerald-700 rounded font-bold">LQA</span>
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
                        accept="image/*,.bmp"
                        onChange={(e) => handleFile(e, true)}
                        className="hidden"
                      />
                    </label>
                  </div>
                ) : (
                  <label className="w-full h-full flex flex-col items-center justify-center cursor-pointer space-y-2">
                    <div className="w-10 h-10 rounded-full bg-[#0696D7]/10 flex items-center justify-center text-[#0696D7]">
                      <Upload className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-700">Upload Reference Image</p>
                      <p className="text-[11px] text-slate-400">PNG, JPG, WebP, or BMP</p>
                    </div>
                    <input
                      type="file"
                      accept="image/*,.bmp"
                      onChange={(e) => handleFile(e, true)}
                      className="hidden"
                    />
                  </label>
                )}
              </div>
            </div>

            {/* Localized Target Box */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-slate-700">2. Localized Target (To Test)</span>
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
                      alt="Localized Target"
                      className="max-h-full max-w-full object-contain rounded"
                    />
                    <label className="absolute inset-0 bg-slate-900/60 text-white flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition cursor-pointer text-xs font-semibold gap-1.5 backdrop-blur-[2px]">
                      <Upload className="w-5 h-5" />
                      <span>Change Localized Image</span>
                      <input
                        type="file"
                        accept="image/*,.bmp"
                        onChange={(e) => handleFile(e, false)}
                        className="hidden"
                      />
                    </label>
                  </div>
                ) : (
                  <label className="w-full h-full flex flex-col items-center justify-center cursor-pointer space-y-2">
                    <div className="w-10 h-10 rounded-full bg-[#0696D7]/10 flex items-center justify-center text-[#0696D7]">
                      <Upload className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-700">Upload Target Image</p>
                      <p className="text-[11px] text-slate-400">German, Spanish, French, etc.</p>
                    </div>
                    <input
                      type="file"
                      accept="image/*,.bmp"
                      onChange={(e) => handleFile(e, false)}
                      className="hidden"
                    />
                  </label>
                )}
              </div>
            </div>

          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClear}
              disabled={!englishImage && !localizedImage}
              className="text-xs text-slate-500 hover:text-slate-800 font-semibold disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reset Selection</span>
            </button>

            <button
              type="button"
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
                  <span>Analyzing Layout Quality...</span>
                </>
              ) : (
                <>
                  <span>Analyze Screenshots</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </>
      )}

      {/* TAB 2: LIVE URL AUTO-CAPTURE */}
      {activeTab === 'url' && (
        <form onSubmit={handleUrlSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                English Baseline Web URL (Reference)
              </label>
              <input
                type="url"
                required
                value={englishUrl}
                onChange={(e) => setEnglishUrl(e.target.value)}
                placeholder="https://help.autodesk.com/view/ACD/2026/ENU/"
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-blue-50/20"
              />
              <p className="text-[11px] text-slate-400">Reference URL rendered in headless Chromium (1280x800)</p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#0696D7]"></span>
                Localized Target Web URL (To Test)
              </label>
              <input
                type="url"
                required
                value={localizedUrl}
                onChange={(e) => setLocalizedUrl(e.target.value)}
                placeholder="https://help.autodesk.com/view/ACD/2026/DEU/"
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#0696D7] bg-slate-50"
              />
              <p className="text-[11px] text-slate-400">Target localized URL in German, Spanish, French, Japanese, etc.</p>
            </div>

          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-slate-100">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Sparkles className="w-4 h-4 text-[#0696D7]" />
              <span>Headless browser will automatically navigate, capture both pages, and analyze visual localization consistency.</span>
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

      {/* TAB 3: 2-LANGUAGE SITE CRAWL & LOCALIZATION VALIDATOR */}
      {activeTab === 'crawl' && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!rootUrl || !onCrawl) return;
            onCrawl({
              root_url: rootUrl,
              baseline_root_url: baselineRootUrl || undefined,
              max_depth: Number(maxDepth),
              max_pages: Number(maxPages),
              same_origin_only: true,
              viewport_width: 1280,
              viewport_height: 800,
              wait_seconds: 1.0,
              check_links: checkLinks,
              check_images: checkImages,
              check_interactions: checkInteractions,
              safe_interactions_only: safeInteractionsOnly
            });
          }}
          className="space-y-5"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-800 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span>
                  1. English Baseline Root URL (Reference)
                </span>
                <span className="text-[10px] text-blue-700 bg-blue-50 px-2 py-0.5 rounded font-bold border border-blue-200">
                  Passed Standard
                </span>
              </label>
              <input
                type="url"
                value={baselineRootUrl}
                onChange={(e) => setBaselineRootUrl(e.target.value)}
                placeholder="https://help.autodesk.com/view/ACD/2026/ENU/"
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-blue-50/20"
              />
              <p className="text-[11px] text-slate-400">English reference root URL to compare every crawled page against.</p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-800 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#0696D7]"></span>
                  2. Localized Target Root URL (To Test)
                </span>
                <span className="text-[10px] text-rose-700 bg-rose-50 px-2 py-0.5 rounded font-bold border border-rose-200">
                  Target To Test
                </span>
              </label>
              <input
                type="url"
                required
                value={rootUrl}
                onChange={(e) => setRootUrl(e.target.value)}
                placeholder="https://help.autodesk.com/view/ACD/2026/DEU/"
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-[#0696D7] bg-slate-50"
              />
              <p className="text-[11px] text-slate-400">Localized root URL (German, Spanish, French, Japanese, etc.) to crawl.</p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700">Max Crawl Depth</label>
              <input
                type="number"
                min="0"
                max="5"
                value={maxDepth}
                onChange={(e) => setMaxDepth(e.target.value)}
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 bg-slate-50"
              />
              <p className="text-[10px] text-slate-400">0 = Root page only, 1 = 1 hop, 2 = 2 hops (recommended: 2)</p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700">Max Pages Limit</label>
              <input
                type="number"
                min="1"
                max="50"
                value={maxPages}
                onChange={(e) => setMaxPages(e.target.value)}
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 bg-slate-50"
              />
              <p className="text-[10px] text-slate-400">Caps total crawl volume to prevent infinite loops (max 50)</p>
            </div>
          </div>

          {/* Validation Checks & Safety Options */}
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5">
            <div className="text-xs font-bold text-slate-700">Active Quality Checks & Safety Rules</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={checkLinks}
                  onChange={(e) => setCheckLinks(e.target.checked)}
                  className="rounded text-[#0696D7] focus:ring-[#0696D7]"
                />
                <span className="font-semibold text-slate-700">Broken Links Check</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={checkImages}
                  onChange={(e) => setCheckImages(e.target.checked)}
                  className="rounded text-[#0696D7] focus:ring-[#0696D7]"
                />
                <span className="font-semibold text-slate-700">Broken Images Check</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={checkInteractions}
                  onChange={(e) => setCheckInteractions(e.target.checked)}
                  className="rounded text-[#0696D7] focus:ring-[#0696D7]"
                />
                <span className="font-semibold text-slate-700">Element State Checks</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={safeInteractionsOnly}
                  onChange={(e) => setSafeInteractionsOnly(e.target.checked)}
                  className="rounded text-[#0696D7] focus:ring-[#0696D7]"
                />
                <span className="font-semibold text-slate-700">Destructive Protection</span>
              </label>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-slate-100">
            <p className="text-xs text-slate-500">
              Recursively crawls matching pages in both languages, compares visual localization defects (truncations, overlaps), tests links/images, and exports multi-format reports.
            </p>
            <button
              type="submit"
              disabled={isCrawling || !rootUrl}
              className={`w-full sm:w-auto px-6 py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition active:scale-95 ${
                isCrawling || !rootUrl
                  ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-[#0696D7] hover:bg-[#0284C7] text-white shadow-sky-200 hover:shadow-md'
              }`}
            >
              {isCrawling ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  <span>Crawling & Comparing 2 Languages...</span>
                </>
              ) : (
                <>
                  <Network className="w-4 h-4" />
                  <span>Start 2-Language Crawl & Compare</span>
                </>
              )}
            </button>
          </div>
        </form>
      )}

    </div>
  );
}
