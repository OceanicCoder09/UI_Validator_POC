import React from 'react';

export default function AutodeskLogo({ className = "h-7 w-auto", dark = false, iconOnly = false }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      {/* Official Sharp Geometric Autodesk Symbol */}
      <svg 
        viewBox="0 0 100 100" 
        className="h-full aspect-square shrink-0 block" 
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect width="100" height="100" fill="#000000" />
        <path 
          d="M 18 69 L 18 51 L 54 28 L 78 28 L 78 69 L 55 69 C 55 61 58 56 74 47 L 55 47 L 18 69 Z" 
          fill="#FFFFFF" 
        />
      </svg>
      
      {!iconOnly && (
        <span 
          className={`font-black text-base tracking-widest leading-none ${dark ? 'text-white' : 'text-slate-950'}`}
          style={{ letterSpacing: '0.08em' }}
        >
          AUTODESK
        </span>
      )}
    </div>
  );
}
