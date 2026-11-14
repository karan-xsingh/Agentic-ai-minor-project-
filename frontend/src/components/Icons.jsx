const base = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };

export const Check = (p) => <svg {...base} {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>;
export const Alert = (p) => <svg {...base} {...p}><path d="M12 7v6M12 17h.01" /></svg>;
export const Cross = (p) => <svg {...base} {...p}><path d="M7 7l10 10M17 7L7 17" /></svg>;
export const Chat = (p) => <svg {...base} {...p}><path d="M4 5h16v11H9l-5 4V5z" /></svg>;
export const Plan = (p) => <svg {...base} {...p}><path d="M5 6h3M5 12h3M5 18h3M12 6h7M12 12h7M12 18h7" /></svg>;
export const Calc = (p) => <svg {...base} {...p}><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M8 7h8M8 12h2M14 12h2M8 16h2M14 16h2" /></svg>;
export const Shield = (p) => <svg {...base} {...p}><path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3z" /><path d="M9 12l2 2 4-4" /></svg>;
export const Sun = (p) => <svg {...base} {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5" /></svg>;
export const Moon = (p) => <svg {...base} {...p}><path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z" /></svg>;

export function BrandMark() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" aria-hidden="true">
      <rect x="1" y="1" width="34" height="34" rx="8" fill="#ffffff" />
      <path d="M1 12.5h34M1 23.5h34M12.5 1v34M23.5 1v34" stroke="#16213a" strokeOpacity="0.16" />
      <path d="M9 19.5l5.5 5.5L27 11" stroke="#176b4d" strokeWidth="3.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
