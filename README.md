# Marketing Automation System - Complete Setup Guide

## 🚀 Professional-Grade Marketing Automation with AI Agents

This system replaces an entire marketing team with AI-powered automation, featuring:

- **Simultaneous TODO Subagents** for parallel task execution
- **Facebook Ads Complete Integration** via MCP tools
- **Bayesian & Machine Learning** optimization
- **12h/24h Data Learning Cycles**
- **Telegram Approval Workflow** (nearly 100% automated with human oversight)
- **Redis Cache with Vectorization** and RAG
- **Focus on 1-Day Click/View Metrics**

## 📋 System Overview

This comprehensive marketing automation system uses:
- **Orchestrator**: N8N + OpenAI GPT-5.4-Mini
- **Subagents**: 4 specialized agents using GPT-5.4-Nano
- **Cache & Intelligence**: Redis with vectorization, tokenization, embedding, and RAG
- **ML Models**: Bayesian inference and gradient boosting for optimization
- **Data Pipeline**: Automated 12h and 24h learning cycles
- **Approval System**: Telegram bot for human-in-the-loop authorization

## 🏗️ Architecture

See `/docs/ARCHITECTURE.md` for the complete architecture with Mermaid diagrams.

**Key Components:**
1. **Creative Agent** - Generates ad creatives and copy
2. **Ads Manager Agent** - Creates and manages Facebook campaigns
3. **Analytics Agent** - Analyzes performance and optimizes
4. **Data Collector Agent** - Collects insights at scheduled intervals

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Redis 6.0+
- Node.js 16+ (for N8N)
- OpenAI API key
- Facebook Ads API access
- Telegram Bot token

### Installation

```bash
# Clone repository
git clone https://github.com/arturoromano974/20_03.git
cd 20_03

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start Redis
redis-server

# Start agents (in separate terminals)
python subagents/creative_agent/agent.py
python subagents/ads_manager_agent/agent.py
python subagents/analytics_agent/agent.py
python subagents/data_collector_agent/agent.py

# Start data pipeline
python scripts/data_pipeline.py

# Start N8N and import workflow
n8n start
# Import orchestrator/n8n_workflow.json
```

## 📖 Documentation

- **Architecture**: `/docs/ARCHITECTURE.md` - Complete system architecture with diagrams
- **Configuration**: `/config/config.json` - System configuration
- **Environment**: `.env.example` - Environment variables template

## 🔑 Key Features

### 1. Nearly 100% Automated
All actions require Telegram approval before execution, ensuring human oversight while maintaining automation.

### 2. Intelligent Learning
- Learns from data every 12 hours and 24 hours
- Bayesian inference for uncertainty handling
- ML models for pattern recognition and prediction

### 3. 1-Day Performance Focus
Optimizes specifically for 1-day click and view metrics with micro-change sensitivity.

### 4. No Raw LLM Analysis
All analysis through structured Python scripts and JSON processing to prevent hallucinations.

### 5. Complete Facebook Integration
- Campaign creation and management
- AdSet configuration with optimal targeting
- Ad creative deployment
- Real-time performance tracking

### 6. RAG System
Historical context retrieval by CAMPAIGN_ID, ADSET_ID, and ADS_ID for informed decision-making.

## 📊 Usage Example

```python
# Example: Create and optimize a campaign
from models.bayesian_model import create_bayesian_optimizer
from models.ml_optimizer import create_ml_optimizer

# Analyze performance
bayesian = create_bayesian_optimizer()
ml = create_ml_optimizer()

metrics = {
    'impressions': 10000,
    'clicks': 500,
    '1_day_clicks': 300,
    '1_day_views': 200
}

# Get predictions
prediction = ml.predict_performance(metrics)
budget_rec = ml.recommend_budget(metrics, current_budget=100.0)

print(f"Recommended action: {budget_rec['action']}")
```

## 🔧 Configuration

Edit `/config/config.json` to customize:
- Model parameters (temperature, tokens)
- Agent ports and capabilities
- Redis cache settings
- Data collection intervals
- ML model configuration

## 🐛 Troubleshooting

### Agents not starting
```bash
# Check Python version
python --version  # Should be 3.9+

# Verify dependencies
pip install -r requirements.txt

# Check ports are free
netstat -tulpn | grep 500[1-4]
```

### Redis connection failed
```bash
# Test Redis
redis-cli ping  # Should return "PONG"

# Check configuration
cat config/config.json | grep redis
```

## 🤝 Contributing

This is a professional-grade system. Contributions welcome for:
- Additional subagents
- Enhanced ML models
- Integration with other ad platforms
- Performance optimizations

## 📄 License

MIT License

---

**Built for professional marketing automation with AI**