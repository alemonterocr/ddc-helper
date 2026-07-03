// Tiny 220px popup that Chrome opens on the toolbar icon.
// Its only job is to open the full-app tab at index.html.
// Colors kept literal (not CSS variables) because this document is
// standalone HTML with no Tailwind / shadcn context.
// Values match DESIGN.md's Steady Teal primary and Console tokens.

const BG_BASE = "#0f0f12";          // Console Ink (matches popup.html body bg)
const PRIMARY = "#1a5f70";          // Steady Teal, sRGB approximation of oklch(0.45 0.085 224.283)
const PRIMARY_HOVER = "#154e5c";    // one lightness step down
const FG = "#f5f5f5";               // Console Ivory
const BORDER = "rgba(255,255,255,0.10)";

const button = document.createElement("button");

button.textContent = "Open DDC Helper";
button.style.cssText = [
  "width:100%",
  "padding:10px 12px",
  `background:${PRIMARY}`,
  `color:${FG}`,
  `border:1px solid ${BORDER}`,
  "border-radius:6px",
  "cursor:pointer",
  "font-size:13px",
  "font-family:'Inter Variable',ui-sans-serif,system-ui,sans-serif",
  "font-weight:500",
  "letter-spacing:normal",
  "transition:background 120ms ease",
].join(";");

button.onmouseenter = () => {
  button.style.background = PRIMARY_HOVER;
};
button.onmouseleave = () => {
  button.style.background = PRIMARY;
};
button.onfocus = () => {
  button.style.outline = `2px solid ${PRIMARY}`;
  button.style.outlineOffset = "2px";
};
button.onblur = () => {
  button.style.outline = "none";
};
button.onclick = () =>
  chrome.tabs.create({ url: chrome.runtime.getURL("index.html") });

document.body.style.background = BG_BASE;
document.getElementById("popup-root")!.appendChild(button);
