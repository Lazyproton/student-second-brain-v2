// Background service worker (Manifest V3) — manages extension lifecycle and storage

// ── 1. Install listener ────────────────────────────────────────────────────────
// When the extension is first installed or updated, log a message and save
// the default Flask backend URL to local storage.

chrome.runtime.onInstalled.addListener(() => {
  console.log("Student Second Brain installed");
  chrome.storage.local.set({ backendUrl: "http://localhost:5000" });
});

// ── 2. Tab update listener ─────────────────────────────────────────────────────
// When a tab finishes loading, check if it's a YouTube or Codeforces page.
// If it is, notify the content.js script on that tab.

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url) {
    if (tab.url.includes("youtube.com/watch") || tab.url.includes("codeforces.com")) {
      try {
        await chrome.tabs.sendMessage(tabId, {
          action: "pageDetected",
          url: tab.url,
        });
      } catch (err) {
        // Content script might not be injected yet or frame might be rendering
        console.log(`[background] Could not message tab ${tabId}:`, err);
      }
    }
  }
});

// ── 3. Message listener ────────────────────────────────────────────────────────
// Listens for cross-extension messages. Currently used to fetch the stored
// backend URL, allowing popup.js to configure itself dynamically.

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "getBackendUrl") {
    chrome.storage.local.get(["backendUrl"], (data) => {
      sendResponse({ backendUrl: data.backendUrl || "http://localhost:5000" });
    });
    return true; // Keep message channel open for async sendResponse
  }
});
