# LangChain Research Assistant with Human-in-the-Loop

An intelligent web research assistant that combines LangChain agents with interactive human approval workflows. Search the web, review results, and generate AI summaries—all with full human control at critical decision points.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![LangChain](https://img.shields.io/badge/LangChain-1.3.1-green.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.57.0-red.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Key Features

- **🎯 Dual-Stage Human Approval**
  - Review and approve search queries before execution
  - Interactive source selection with visual cards and checkboxes
  
- **🔍 Intelligent Web Search** - Powered by Tavily API for high-quality results

- **🤖 LangChain Agent Architecture** - Uses `HumanInTheLoopMiddleware` for transparent AI workflows

- **📝 AI-Powered Summarization** - Generate summaries from curated sources using OpenAI

- **🔌 Mock Mode** - Test the UI without API keys (zero cost development)

## 🏗️ How It Works

```
User Input (Topic)
      ↓
Agent Generates Search Query
      ↓
🛑 APPROVAL #1: Review Query → [Approve/Reject]
      ↓
Tavily Search Executes
      ↓
Agent Formats Results
      ↓
🛑 APPROVAL #2: Select Sources → [Checkboxes UI]
      ↓
Approved Sources Displayed
      ↓
Optional: Generate AI Summary
```

**Human-in-the-Loop Implementation:**
- **Checkpoint #1**: Approve search queries before they execute
- **Checkpoint #2**: Select which sources to keep using an interactive UI with expandable cards

The workflow uses LangChain's `HumanInTheLoopMiddleware` to pause execution at critical points, ensuring full transparency and control.

## 🛠️ Technologies

- **LangChain** - Agent orchestration and HITL middleware
- **LangGraph** - State management with checkpointing
- **Streamlit** - Interactive web UI
- **Tavily API** - Web search
- **OpenAI GPT-3.5** - Summarization
- **Python 3.8+**

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/langchain-hitl-research.git
cd langchain-hitl-research

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Add your API keys to .env:
# OPENAI_API_KEY=sk-...
# TAVILY_API_KEY=tvly-...
# MODEL=openai:gpt-3.5-turbo
```

**Get API Keys:**
- OpenAI: https://platform.openai.com/api-keys
- Tavily: https://tavily.com/

### Run

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## 📖 Usage Example

1. **Enter Topic**: "How AI will change the future"
2. **Approve Search**: Review the generated query → Click "Submit approval"
3. **Select Sources**: Review 5 results in expandable cards → Check/uncheck sources → Click "✅ Approve Selected Sources"
4. **View Results**: See your curated source list with clickable links
5. **Summarize**: Click "Summarize approved sources" for an AI-generated synthesis

### Mock Mode

No API keys? No problem! The app runs in mock mode with sample data—perfect for testing the UI without costs.

## 📁 Project Structure

```
.
├── src/
│   └── agent.py          # Agent logic (RealAgent + MockAgent)
├── app.py                # Streamlit UI
├── requirements.txt      # Dependencies
├── .env.example          # Environment template
└── README.md
```

## 🔮 Future Enhancements

- **Export** - Save sources and summaries as PDF/Markdown
- **Persistence** - Database storage for research sessions
- **Advanced Filtering** - Filter by date, domain, relevance
- **Multi-Model Support** - Claude, Gemini, local LLMs
- **Collaboration** - Multi-user approval workflows
- **Docker Deployment** - Containerized setup

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

Built with [LangChain](https://langchain.com/), [Tavily](https://tavily.com/), [Streamlit](https://streamlit.io/), and [OpenAI](https://openai.com/).

---

**Built with ❤️ using LangChain and Human-in-the-Loop AI**
