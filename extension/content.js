// Injected into every webpage — reads selected text and detects page type.
// Never modifies the host page DOM or makes any network requests.

// ── 1. Message listener ───────────────────────────────────────────────────────
// Listens for messages from popup.js and responds with the currently selected
// text on the page, trimmed and cleaned of extra whitespace.

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === "getSelectedText") {
    let raw = window.getSelection()?.toString() || "";
    
    // If no text is selected, capture the whole page
    if (!raw.trim()) {
      raw = document.body.innerText || "";
    }
    
    // Clean up excessive whitespace
    const cleaned = raw.trim()
      .replace(/\s{2,}/g, " ")       // Multiple spaces -> single space
      .replace(/\n{3,}/g, "\n\n");   // Multiple newlines -> max 2
      
    sendResponse({ selectedText: cleaned });
    return true;
  }
});

// ── 2. Page type detection ────────────────────────────────────────────────────
// Checks the current URL to classify the page, then notifies popup.js so it
// can auto-switch to the relevant tab or pre-fill fields.

function detectPageType() {
  const url = window.location.href;
  if (url.includes("youtube.com/watch"))                               return "youtube";
  if (url.includes("codeforces.com/problemset") ||
      url.includes("codeforces.com/contest"))                          return "codeforces";
  if (url.endsWith(".pdf") || url.includes(".pdf?"))                   return "pdf";
  return "webpage";
}

// Fire-and-forget — popup may not be open yet, so we silently ignore errors
chrome.runtime.sendMessage(
  { action: "pageType", type: detectPageType() },
  () => void chrome.runtime.lastError   // Suppress "no listener" console error
);
