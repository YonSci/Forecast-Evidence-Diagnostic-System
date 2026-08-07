import { useState, createContext, useContext } from "react";
import type { ReactNode } from "react";

interface LightboxState {
  src: string;
  caption: string;
}

const LightboxContext = createContext<(state: LightboxState) => void>(() => {});

export function useLightbox() {
  return useContext(LightboxContext);
}

export function LightboxProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LightboxState | null>(null);

  return (
    <LightboxContext.Provider value={setState}>
      {children}
      <div className={`lightbox${state ? " open" : ""}`} onClick={() => setState(null)}>
        <button className="lb-close" aria-label="Close" onClick={() => setState(null)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
        {state && (
          <div onClick={(e) => e.stopPropagation()}>
            <img src={state.src} alt={state.caption} />
            <div className="lb-cap">{state.caption}</div>
          </div>
        )}
      </div>
    </LightboxContext.Provider>
  );
}
