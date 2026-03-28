# 🧠 Student Second Brain V2

> One-click capture for your entire academic life: web articles, YouTube lectures, Codeforces problems, and Exams directly connected to Notion and Google Calendar.

![Python 3.9](https://img.shields.io/badge/Python-3.9-blue.svg)
![Flask](https://img.shields.io/badge/Flask-Backend-black.svg?logo=flask)
![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-green.svg?logo=google-chrome)
![Notion MCP](https://img.shields.io/badge/Notion-MCP-lightgrey.svg?logo=notion)
![Google Calendar](https://img.shields.io/badge/Google-Calendar-4285F4.svg?logo=google-calendar)

Student Second Brain V2 is the ultimate study companion designed to solve the problem of scattered knowledge. By seamlessly integrating a Chrome Extension with a Python Flask backend and the powerful Notion MCP (Model Context Protocol), it transforms any webpage, YouTube lecture transcript, or Codeforces problem into structured, AI-summarized notes with a single click. Unlike other generic bookmarking tools, it actively processes your content using Gemini 2.0 Flash to generate concise summaries, tags, and topics, and smartly routes them into dynamic, subject-specific Notion databases while instantly syncing your upcoming exams to Google Calendar.

## 🌟 Core Features

### 📄 Smart Page Capture
- Captures full page or selected text with one click
- AI generates summary and tags automatically
- Choose which subject database to save to

### 🎥 YouTube Lecture Capture
- Detects YouTube automatically
- Captures full transcript
- AI summarizes the lecture content
- Saves with video title to Notion

### 💻 Codeforces Problem Tracker
- Detects Codeforces problems automatically
- Captures problem statement only (no solutions)
- Mark as solved or unsolved
- Tracks all problems in CP Tracker database

### 🗂️ Dynamic Subject Databases
- Create a new Notion database per subject with one click
- Mathematics, Physics, DSA — each gets its own database
- Master Index tracks all subject databases automatically

### 🔍 Natural Language Search
- Search all your Notion notes from the extension
- AI converts your query to smart search terms

### 📅 Exam Dashboard + Google Calendar Sync
- Shows upcoming exams from Notion Calendar
- Automatically syncs exams to Google Calendar
- Real reminders on your phone

## 🏗️ System Architecture

```text
Chrome Extension → Flask Backend (localhost:5000)
                 → OpenRouter LLM (Gemini 2.0 Flash)
                 → Notion MCP → Subject Databases
                 → Google Calendar API → Phone Notifications
```

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Extension** | HTML5, CSS3, Vanilla JS | Chrome Extension UI and content capturing |
| **Backend** | Python, Flask, Flask-CORS | API server connecting all services together |
| **LLM** | OpenRouter (Gemini 2) | Generates summaries, topic tags, and smart search queries |
| **Notion** | Notion-Client + Notion MCP | Reads and writes structured data to subject databases |
| **Calendar** | Google Calendar API | Syncs upcoming exam dates to your phone |
| **Parsers** | BeautifulSoup4, PyMuPDF, yt-api | Scrapes DOM, PDF text, and YouTube captions |

## 🚀 Setup Instructions

1. **Clone the repo**  
   Clone this repository to your local machine.
2. **Create virtual environment and install dependencies**  
   Navigate to the backend folder (`cd backend`), create a virtual environment (`python3 -m venv venv`), activate it, and install dependencies with `pip install -r requirements.txt`.
3. **Set up Notion integration and databases**  
   Create a Notion Internal Integration token, and set up your Master Index, CP Tracker, and Calendar databases (Note down their IDs).
4. **Set up OpenRouter API key**  
   Get a free Gemini 2.0 Flash API key from OpenRouter.
5. **Set up Google Calendar credentials**  
   Place your `credentials.json` file inside the `backend/` folder.
6. **Fill in `.env` file**  
   Copy `.env.example` to `.env` in the root (or `backend/`) and fill in all your tokens, keys, and Notion Database IDs.
7. **Run the backend**  
   Start the Flask server by running `python app.py` inside the `backend/` directory.
8. **Load the Chrome extension**  
   Open Chrome, go to `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and select the `extension/` folder from this repository.

## 🏆 Built For
**Notion + MLH Hackathon Challenge**  
_"Build the most impressive system using Notion MCP"_

## 📜 License
MIT License