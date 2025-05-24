# 📈 AI-Powered Stock Analysis Tool

<div align="center">

![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

*Get real-time stock insights with AI-powered analysis combining market data and news sentiment*

[Features](#-features) •
[Installation](#-installation) •
[Usage](#-usage) •
[Configuration](#-configuration) •
[Contributing](#-contributing)

</div>

---

## 🌟 Features

### 🎯 **Smart Stock Identification**
- Automatically identifies company tickers from natural language queries
- Supports major stock exchanges and symbols
- Fuzzy matching for company names

### 💰 **Real-Time Market Data**
- Current stock prices in USD and INR
- Price change tracking with percentage calculations
- Historical comparison with previous close

### 📰 **News Integration**
- Fetches latest company news and headlines
- Analyzes news sentiment impact on stock prices
- Real-time news correlation with price movements

### 🤖 **AI-Powered Analysis**
- Uses Groq's LLaMA 3 model for intelligent analysis
- Combines market data with news sentiment
- Provides actionable insights and explanations

### 🌈 **Beautiful CLI Interface**
- Color-coded output for better readability
- Emoji indicators for quick visual scanning
- Clean, organized information display

---

## 🚀 Quick Start

### Prerequisites

```bash
Python 3.8+
pip package manager
```

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/stock-analyzer.git
   cd stock-analyzer
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run the analyzer**
   ```bash
   python stock_analyzer.py
   ```

---

## 🔧 Configuration

### Required API Keys

Create a `.env` file in the project root:

```env
FINNHUB_API_KEY=your_finnhub_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

### Getting API Keys

| Service | Purpose | How to Get |
|---------|---------|------------|
| **Finnhub** | Stock market data | [Register at finnhub.io](https://finnhub.io) |
| **Tavily** | News aggregation | [Get API key at tavily.com](https://tavily.com) |
| **Groq** | AI analysis | [Sign up at groq.com](https://groq.com) |

---

## 📱 Usage

### Interactive Mode

```bash
python stock_analyzer.py
```

### Example Queries

```
🔎 Enter your stock-related query: tesla
🔎 Enter your stock-related query: apple stock
🔎 Enter your stock-related query: MSFT
🔎 Enter your stock-related query: nvidia corporation
```

### Sample Output

```
🔍 Identified Ticker: TSLA for Company: Tesla Inc
💰 Current Price: $339.34 / ₹27825.88
📈 Price Change: -$1.70 / -₹139.40 (-0.50%)
📊 Ticker Analysis:
The recent decline in Tesla's stock price appears to be influenced by...

📈 Final Summary for Tesla Inc (TSLA):
✅ Price: $339.34 / ₹27825.88
📉 Change: -$1.70 / -₹139.40 (-0.50%)
🧠 Analysis:
[Detailed AI analysis here...]
```

---

## 🏗️ Project Structure

```
stock-analyzer/
├── stock_analyzer.py      # Main application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── .env                  # Your API keys (not in repo)
├── README.md             # This file
└── .gitignore           # Git ignore rules
```

---

## 📦 Dependencies

```txt
requests>=2.31.0
python-dotenv>=1.0.0
langchain-groq>=0.1.0
colorama>=0.4.6
```

---

## 🎨 Features in Detail

### Currency Conversion
- Automatic USD to INR conversion
- Configurable exchange rate (currently 1 USD = 82 INR)
- Dual currency display for all monetary values

### Error Handling
- Graceful handling of API failures
- Clear error messages for troubleshooting
- Fallback mechanisms for missing data

### News Analysis
- Fetches up to 5 recent news articles
- Combines headlines and descriptions
- AI correlation with price movements

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

### 🐛 Bug Reports
- Use GitHub Issues to report bugs
- Include steps to reproduce
- Provide sample output if possible

### 💡 Feature Requests
- Suggest new features via GitHub Issues
- Explain the use case and benefits
- Consider implementation complexity

### 🔧 Pull Requests
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Setup
```bash
git clone https://github.com/yourusername/stock-analyzer.git
cd stock-analyzer
pip install -r requirements.txt
# Make your changes
python stock_analyzer.py  # Test locally
```

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Finnhub** for reliable stock market data
- **Tavily** for comprehensive news aggregation
- **Groq** for fast AI inference
- **LangChain** for AI framework integration

---

## 📞 Support

- 📧 **Email**: aryaadityakumar222@gmail.com
- 🐛 **Issues**: [GitHub Issues](https://github.com/adityaarya1067/stock-analyzer/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/adityaarya1067/stock-analyzer/discussions)

---

<div align="center">

**⭐ Star this repo if you find it helpful!**

Made with ❤️ for the trading community

</div>
