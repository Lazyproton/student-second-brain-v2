// Handles all popup interactions — communicates with the Flask backend only via fetch()

const BACKEND = "http://localhost:5000";

// ── Section 1: Tab switching ───────────────────────────────────────────────────
// On load, the Capture tab is active. Clicking any tab button hides all panels
// and shows only the one matching data-tab, updating the active class accordingly.

const tabBtns   = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");

document.addEventListener("DOMContentLoaded", () => {
  loadSubjects();
});

tabBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabBtns.forEach((b)   => b.classList.remove("active"));
    tabPanels.forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");

    // Auto-load exams whenever the Dashboard tab is opened
    if (btn.dataset.tab === "dashboard") loadExams();
  });
});

// ── Section 7: Helper functions ───────────────────────────────────────────────
// Shared utilities used by every tab section below.

/** Returns the currently active Chrome tab. */
async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

/** Asks content.js for the selected text on the current page. Returns "" if none or error. */
async function getSelectedText(tabId) {
  return new Promise((resolve) => {
    try {
      chrome.tabs.sendMessage(tabId, { action: "getSelectedText" }, (response) => {
        if (chrome.runtime.lastError) {
          console.warn("[SB] getSelectedText warning:", chrome.runtime.lastError.message);
          resolve(""); // Return empty string on error (e.g. content script not injected)
        } else {
          resolve(response?.selectedText || "");
        }
      });
    } catch (err) {
      console.warn("[SB] getSelectedText err:", err);
      resolve("");
    }
  });
}

/**
 * showStatus(tabName, message, type)
 * Displays a message in the status div of the given tab.
 * type: "success" | "error" | "loading"
 * Auto-hides after 3 seconds for success/error.
 */
function showStatus(tabName, message, type = "success") {
  const el = document.getElementById(`status-${tabName}`);
  if (!el) return;
  el.textContent = message;
  el.className = `status visible ${type}`;
  if (type !== "loading") {
    setTimeout(() => { el.className = "status"; }, 3000);
  }
}

/** Converts "YYYY-MM-DD" → "Mon DD, YYYY" */
function formatDate(dateString) {
  const [y, m, d] = dateString.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

/** Returns the number of whole days from today until dateString (YYYY-MM-DD). */
function daysUntil(dateString) {
  const [y, m, d] = dateString.split("-").map(Number);
  const target = new Date(y, m - 1, d);
  const today  = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target - today) / (1000 * 60 * 60 * 24));
}

// ── Section 2: Capture tab ────────────────────────────────────────────────────
// Gets the current tab's URL, title, and any selected text from content.js,
// then POSTs to /capture (or /capture/subject) so the backend can save to Notion.

const subjectSelect = document.getElementById("subject-select");
const newSubjectRow = document.getElementById("new-subject-input");
const newSubjectName = document.getElementById("new-subject-name");
const confirmNewSubjectBtn = document.getElementById("confirm-new-subject");

// Load existing subjects from backend
async function loadSubjects() {
  try {
    const res = await fetch(`${BACKEND}/subjects`);
    const data = await res.json();
    if (data.success && data.subjects) {
      // Create options for each subject
      data.subjects.forEach(sub => {
        const option = document.createElement("option");
        option.value = sub.subject_name;
        option.textContent = sub.subject_name;
        // Insert right before the last option ("+ New Subject")
        subjectSelect.insertBefore(option, subjectSelect.lastElementChild);
      });
    }
  } catch (err) {
    console.error("[SB] Failed to load subjects:", err);
  }
}

// Show/hide new subject row
subjectSelect.addEventListener("change", () => {
  if (subjectSelect.value === "new") {
    newSubjectRow.classList.add("visible");
    newSubjectName.focus();
  } else {
    newSubjectRow.classList.remove("visible");
  }
});

// Create new subject
confirmNewSubjectBtn.addEventListener("click", async () => {
  const name = newSubjectName.value.trim();
  if (!name) {
    showStatus("capture", "❌ Please enter a subject name", "error");
    return;
  }

  showStatus("capture", "Creating subject...", "loading");
  try {
    const res = await fetch(`${BACKEND}/subjects/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_name: name })
    });
    const data = await res.json();

    if (data.success) {
      // Add to dropdown
      const option = document.createElement("option");
      option.value = data.subject_name;
      option.textContent = data.subject_name;
      subjectSelect.insertBefore(option, subjectSelect.lastElementChild);
      
      // Select it & clean up
      subjectSelect.value = data.subject_name;
      newSubjectRow.classList.remove("visible");
      newSubjectName.value = "";
      showStatus("capture", `✅ Created subject '${data.subject_name}'`, "success");
    } else {
      showStatus("capture", `❌ ${data.error || "Failed to create subject"}`, "error");
    }
  } catch (err) {
    showStatus("capture", `❌ ${err.message}`, "error");
  }
});

document.getElementById("btn-capture").addEventListener("click", async () => {
  showStatus("capture", "Saving to Notion…", "loading");
  try {
    const tab          = await getCurrentTab();
    let selectedText   = await getSelectedText(tab.id);

    // ISSUE 2: Full page capture fallback if nothing selected
    if (!selectedText) {
      showStatus("capture", "Reading full page...", "loading");
      try {
        const injection = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: () => document.body.innerText
        });
        if (injection && injection[0]?.result) {
          selectedText = injection[0].result.slice(0, 5000); // Trim to 5000 chars
        }
      } catch (scriptErr) {
        console.warn("[SB] Failed to read full page:", scriptErr);
      }
    }

    if (!selectedText && !tab.url) {
      showStatus("capture", "❌ Cannot capture this page", "error");
      return;
    }

    const subject = subjectSelect.value;
    const endpoint = (subject && subject !== "new") 
      ? `${BACKEND}/capture/subject` 
      : `${BACKEND}/capture`;
      
    const payload = {
      content: selectedText,
      url:     tab.url,
      title:   tab.title,
    };
    if (subject && subject !== "new") {
      payload.subject_name = subject;
    }

    const res = await fetch(endpoint, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (data.success) {
      const dbName = (subject && subject !== "new") ? subject : "Notion";
      showStatus("capture", `✅ Saved to ${dbName}!`, "success");
    } else {
      showStatus("capture", `❌ ${data.error || "Unknown error"}`, "error");
    }
  } catch (err) {
    showStatus("capture", `❌ ${err.message}`, "error");
  }
});

// ── Section 3: YouTube tab ────────────────────────────────────────────────────
// Validates that the current tab is a YouTube watch page, then POSTs the URL
// to /youtube so the backend can fetch the transcript and save it to Notion.

document.getElementById("btn-youtube").addEventListener("click", async () => {
  showStatus("youtube", "Fetching transcript…", "loading");
  try {
    const tab = await getCurrentTab();

    if (!tab.url.includes("youtube.com/watch")) {
      showStatus("youtube", "❌ Not a YouTube page", "error");
      return;
    }

    const res = await fetch(`${BACKEND}/youtube`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_url: tab.url }),
    });
    const data = await res.json();

    if (data.success) {
      showStatus("youtube", "✅ Transcript saved to Notion!", "success");
    } else {
      showStatus("youtube", `❌ ${data.error || "Unknown error"}`, "error");
    }
  } catch (err) {
    showStatus("youtube", `❌ ${err.message}`, "error");
  }
});

// ── Section 4: Codeforces tab ─────────────────────────────────────────────────
// Validates that the current tab is a Codeforces problem page, then POSTs to
// /codeforces with the appropriate solved/unsolved status.

async function captureCodeforces(status) {
  showStatus("codeforces", "Adding to CP Tracker…", "loading");
  try {
    const tab = await getCurrentTab();

    if (!tab.url.includes("codeforces.com")) {
      showStatus("codeforces", "❌ Not a Codeforces page", "error");
      return;
    }

    let problemName = tab.title;
    let problemStatement = "";

    try {
      const injection = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          const titleEl = document.querySelector(".problem-statement .title");
          const statementEl = document.querySelector(".problem-statement");
          
          let title = titleEl ? titleEl.innerText.trim() : document.title;
          let statement = "";
          
          if (statementEl) {
            const rawText = statementEl.innerText || statementEl.textContent || "";
            const headerEl = statementEl.querySelector(".header");
            const headerText = headerEl ? (headerEl.innerText || headerEl.textContent || "") : "";
            
            // Remove the header text from the beginning implicitly
            statement = rawText.replace(headerText, "").trim();
            // Fix isolated numbers (e.g. from inline math blocks) splitting into newlines
            // Matches a word/punctuation, a newline, a number, and a newline, then merges them
            statement = statement.replace(/([a-zA-Z,.:;])\s*\n\s*(\d+)\s*\n/g, "$1 $2\n");
            // Also handle cases where the number is followed by punctuation or text
            statement = statement.replace(/\n\s*(\d+)\s*\n\s*([a-zA-Z,.:;])/g, "\n$1 $2");
            // Do a final cleanup for any remaining isolated numbers surrounded by words
            statement = statement.replace(/([a-zA-Z,.:;])\s*\n\s*(\d+)\s*\n\s*([a-zA-Z,.:;])/g, "$1 $2 $3");
            
            statement = statement.slice(0, 5000);
          }
          return { title, statement };
        }
      });
      if (injection && injection[0]?.result) {
        problemName = injection[0].result.title || tab.title;
        problemStatement = injection[0].result.statement || "";
      }
    } catch (e) {
      console.warn("Failed to scrape codeforces DOM", e);
    }

    const res = await fetch(`${BACKEND}/codeforces`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        problem_url: tab.url, 
        problem_name: problemName, 
        notes: problemStatement,
        status 
      }),
    });
    const data = await res.json();

    if (data.success) {
      showStatus("codeforces", `✅ Marked as ${status} in Notion!`, "success");
    } else {
      showStatus("codeforces", `❌ ${data.error || "Unknown error"}`, "error");
    }
  } catch (err) {
    showStatus("codeforces", `❌ ${err.message}`, "error");
  }
}

document.getElementById("btn-cf-solved").addEventListener("click",   () => captureCodeforces("solved"));
document.getElementById("btn-cf-unsolved").addEventListener("click", () => captureCodeforces("unsolved"));

// ── Section 5: Query tab ──────────────────────────────────────────────────────
// Sends the search query to /query and renders each result as a clickable card
// showing the title (bold), summary, and a link to the source URL.

document.getElementById("btn-query").addEventListener("click", async () => {
  const q         = document.getElementById("input-query").value.trim();
  const resultsEl = document.getElementById("results-query");

  if (!q) {
    resultsEl.innerHTML = `<p class="empty-hint" style="color:#f87171">Please enter a search term.</p>`;
    return;
  }

  resultsEl.innerHTML = `<p class="empty-hint">Searching…</p>`;

  try {
    const res  = await fetch(`${BACKEND}/query?q=${encodeURIComponent(q)}`);
    const data = await res.json();

    const results = data.results || [];
    if (results.length === 0) {
      resultsEl.innerHTML = `<p class="empty-hint">No results found.</p>`;
      return;
    }

    resultsEl.innerHTML = results.map((r) => `
      <a class="result-card" href="${r.url}" target="_blank">
        <div>
          <div style="font-weight:600;margin-bottom:3px">${r.title || "Untitled"}</div>
          ${r.summary ? `<div style="font-size:11px;color:#888;line-height:1.4">${r.summary}</div>` : ""}
        </div>
        <span style="font-size:18px;flex-shrink:0">↗</span>
      </a>
    `).join("");

  } catch (err) {
    resultsEl.innerHTML = `<p class="empty-hint" style="color:#f87171">❌ ${err.message}</p>`;
  }
});

// Also trigger search on Enter key in the input
document.getElementById("input-query").addEventListener("keydown", (e) => {
  if (e.key === "Enter") document.getElementById("btn-query").click();
});

// ── Section 6: Dashboard tab ──────────────────────────────────────────────────
// Loads upcoming exams from /calendar and renders each as a card with name,
// subject, formatted date, and days-away count. Cards within 3 days are red.

async function loadExams() {
  const listEl = document.getElementById("exams-list");
  listEl.innerHTML = `<p class="empty-hint">Loading…</p>`;

  try {
    const res  = await fetch(`${BACKEND}/calendar`);
    const data = await res.json();

    const exams = data.exams || [];
    if (exams.length === 0) {
      listEl.innerHTML = `<p class="empty-hint">No upcoming exams 🎉</p>`;
      return;
    }

    listEl.innerHTML = exams.map((exam) => {
      const days    = daysUntil(exam.date);
      const urgent  = days <= 3;
      const daysStr = days === 0 ? "Today!" : days === 1 ? "Tomorrow!" : `${days} days away`;
      const cardStyle = urgent
        ? "border-color:#f8717155;background:#2a1010"
        : "";

      return `
        <div class="result-card" style="${cardStyle}">
          <div>
            <div style="font-weight:600;margin-bottom:2px">${exam.exam_name || "Exam"}</div>
            ${exam.subject ? `<div style="font-size:11px;color:#888">${exam.subject}</div>` : ""}
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div class="card-date">${formatDate(exam.date)}</div>
            <div style="font-size:11px;color:${urgent ? "#f87171" : "#6366f1"};font-weight:600">${daysStr}</div>
          </div>
        </div>
      `;
    }).join("");

  } catch (err) {
    listEl.innerHTML = `<p class="empty-hint" style="color:#f87171">❌ ${err.message}</p>`;
  }
}

document.getElementById("btn-refresh-exams").addEventListener("click", loadExams);
