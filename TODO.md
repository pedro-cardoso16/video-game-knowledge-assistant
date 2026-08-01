# 🛠️ Project Enhancement Checklist

This document tracks improvements to make the **Video Game Knowledge Assistant** more presentable.

* [ ] Finish the search evaluation demonstration.
---

## 📁 1. README.md Improvements

### Visual Proof
- [x] Replace `<!-- Insert figure here -->` with actual screenshots of the Streamlit app
- [ ] Add a demo GIF showing the chat interface in action
- ~~[ ] Include a screenshot of the Grafana monitoring dashboard (when implemented)~~

## 🚀 Quick Start

```bash
docker compose up --build -d
# App available at http://localhost:8501
```


### Clean Up Incomplete Sections
- [ ] Change `TODO.md` references to "Future Enhancements" or "Roadmap"
- [ ] Frame incomplete items as "planned features" rather than "not done"

---

## 🔒 2. Security & Code Cleanup

### Remove Hardcoded Credentials
- [ ] Move `OPENSEARCH_PASSWORD` from `app.py` to environment variables only
- [ ] Verify `.env` is in `.gitignore`
- [ ] Add `info.json` to `.gitignore` (contains access tokens)

### Clean Commented Code
- [ ] Remove large blocks of commented-out code in `llm.py`
- [ ] Remove large blocks of commented-out code in `evaluation.py`
- [ ] Keep only active, production-ready code visible

---

## 📊 3. Portfolio Presentation

### Add to Portfolio Item
| Element | What to Include |
|---------|-----------------|
| **Screenshot** | Streamlit chat interface with a sample query |
| **Architecture Diagram** | Clean version of your mermaid graph |
| **Metrics** | Search evaluation scores (MRR, Hit Rate) |
| **Tech Stack** | Python, Streamlit, OpenSearch, PostgreSQL, Grafana, Gemini API |

### Add Live Demo Link
- [ ] Deploy to Streamlit Cloud or similar
- [ ] Add the URL to README.md and portfolio item

---

## 📝 4. TODO.md Reframe

Change the structure to show progress:

## ✅ Completed Features
- [x] IGDB & Wikipedia data ingestion
- [x] Hybrid search (lexical + semantic)
- [x] RAG pipeline with Gemini LLM
- [x] Ground truth generation & evaluation
- [x] Streamlit chat interface

## 🚧 Planned Enhancements
- [ ] Search boosting optimization
- [ ] Grafana monitoring integration
- [ ] User feedback collection UI

---

## 📄 5. Add DEMO.md File

Create a simple guide for clients to test the app:

# How to Test This Project

1. Clone the repository
2. Run `./setup.sh`
3. Add your API keys to `.env`
4. Run `docker compose up --build -d`
5. Visit http://localhost:8501

---

## 🎨 6. Additional Polish

### Add a `LICENSE` File
- [x] Choose an open-source license (MIT recommended for portfolio)

### Add a `CONTRIBUTING.md` File (Optional)
- [ ] Shows you understand collaborative development

### Add Badges to README.md
- [x] Python version badge
- [x] License badge
- [x] Streamlit badge

---

## 📋 Priority Order

| Priority | Task |
|----------|------|
| 🔴 High | Security fixes (remove hardcoded credentials) |
| 🔴 High | Add screenshots to README |
| 🟡 Medium | Clean commented code |
| 🟡 Medium | Create DEMO.md |
| 🟢 Low | Add badges and license |

---

## ✅ Completion Checklist

- [ ] All security issues resolved
- [ ] README.md updated with visuals
- [ ] Code cleaned up
- [ ] Portfolio item updated
- [ ] Live demo deployed (optional)

---