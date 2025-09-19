import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from colorama import Fore, Style, init
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import asyncio
import aiohttp

load_dotenv()
init(autoreset=True)

# Initialize FastAPI app
app = FastAPI(
    title="Stock Analysis API",
    description="Real-time stock analysis with AI-powered insights",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq client
groq_client = ChatGroq(api_key=GROQ_API_KEY, model_name="llama-3.1-8b-instant")

# Pydantic models for request/response
class StockAnalysisRequest(BaseModel):
    query: str

class StockData(BaseModel):
    company: str
    ticker: str
    price: float
    price_inr: float
    change: float
    change_inr: float
    percent: float
    analysis: str
    news_articles: int
    timestamp: str

class StockAnalysisResponse(BaseModel):
    success: bool
    data: Optional[StockData] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    apis_configured: Dict[str, bool]

# Utility functions
def rupees_from_usd(usd_amount: float) -> float:
    conversion_rate = 82.0
    return round(usd_amount * conversion_rate, 2)

async def identify_ticker(query: str) -> tuple[Optional[str], Optional[str]]:
    """Async function to identify ticker symbol from query"""
    try:
        url = f'https://finnhub.io/api/v1/search?q={query}&token={FINNHUB_API_KEY}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                if data.get("count", 0) > 0:
                    symbol = data['result'][0]['symbol']
                    description = data['result'][0]['description']
                    return symbol, description
                return None, None
    except Exception as e:
        print(f"Error identifying ticker: {e}")
        return None, None

async def ticker_price(ticker: str) -> Optional[float]:
    """Async function to get ticker price"""
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                return data.get('c')
    except Exception as e:
        print(f"Error fetching price: {e}")
        return None

async def ticker_price_change(ticker: str) -> tuple[Optional[float], Optional[float]]:
    """Async function to get ticker price change"""
    try:
        url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                current_price = data.get('c')
                previous_close = data.get('pc')

                if current_price is None or previous_close is None:
                    raise ValueError("Price data missing in API response")

                change = current_price - previous_close
                percent_change = (change / previous_close) * 100
                return round(change, 2), round(percent_change, 2)
    except Exception as e:
        print(f"Error fetching price change: {e}")
        return None, None

async def ticker_news(company_name: str) -> tuple[str, list]:
    """Async function to get ticker news"""
    try:
        url = f"https://api.tavily.com/v1/news?query={company_name}&limit=5"
        headers = {"Authorization": f"Bearer {TAVILY_API_KEY}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                data = await response.json()
                articles = data.get("articles") or data.get("results", [])
                if not articles:
                    return "No recent news available.", []
                
                combined_text = " ".join([f"{a['title']}. {a.get('description', '')}" for a in articles])
                return combined_text, articles
    except Exception as e:
        print(f"Error fetching news: {e}")
        return "No news available.", []

def summarize_with_groq(news_text: str, price_change_info: str) -> str:
    """Function to get AI analysis using Groq"""
    try:
        prompt = f"""
You're a financial analyst providing insights for retail investors.

Analyze the recent price change of the company:
- {price_change_info}

Recent News Headlines and Context:
{news_text}

Provide a concise analysis (2-3 paragraphs) explaining:
1. The possible reasons for this price movement based on the news
2. Key factors that might be influencing the stock
3. What this might mean for potential investors

Keep the analysis professional but accessible to general investors. Don't introduce yourself in the response.
"""
        response = groq_client.invoke(prompt)
        
        if hasattr(response, "content"):
            return response.content
        elif isinstance(response, dict) and "content" in response:
            return response["content"]
        else:
            return str(response)
    except Exception as e:
        print(f"Error with Groq analysis: {e}")
        return "Unable to generate detailed analysis at this time. Please try again later."

async def analyze_stock_data(query: str) -> Dict[str, Any]:
    """Main async function that analyzes stock data and returns structured response"""
    try:
        # Step 1: Identify ticker
        ticker, company = await identify_ticker(query)
        if not ticker:
            return {
                "success": False,
                "error": "❌ Couldn't identify a valid company in your query. Please try a different company name or ticker symbol."
            }

        print(f"{Fore.CYAN}🔍 Identified Ticker: {ticker} for Company: {company}")

        # Step 2: Get current price
        price = await ticker_price(ticker)
        if price is None:
            return {
                "success": False,
                "error": "❌ Unable to fetch current price data. Please try again later."
            }

        price_inr = rupees_from_usd(price)
        print(f"{Fore.GREEN}💰 Current Price: ${price} / ₹{price_inr}")

        # Step 3: Get price change
        change_data = await ticker_price_change(ticker)
        if change_data[0] is None:
            return {
                "success": False,
                "error": "❌ Unable to fetch price change data. Please try again later."
            }

        change, percent = change_data
        change_inr = rupees_from_usd(change)
        print(f"{Fore.YELLOW}📈 Price Change: {change:+.2f}$ / {change_inr:+.2f}₹ ({percent:.2f}%)")

        # Step 4: Get news and analysis
        news_text, articles = await ticker_news(company)
        
        price_change_info = f"Price changed by {change} USD ({percent:.2f}%) for {company} ({ticker})"
        analysis = summarize_with_groq(news_text, price_change_info)
        
        print(f"{Fore.MAGENTA}📊 Analysis generated successfully")

        # Return structured response
        return {
            "success": True,
            "data": {
                "company": company,
                "ticker": ticker,
                "price": round(price, 2),
                "price_inr": price_inr,
                "change": round(change, 2),
                "change_inr": change_inr,
                "percent": round(percent, 2),
                "analysis": analysis,
                "news_articles": len(articles),
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        print(f"{Fore.RED}Error in analyze_stock_data: {e}")
        return {
            "success": False,
            "error": f"❌ An unexpected error occurred: {str(e)}"
        }

# HTML Content
def get_html_content():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Market Analyzer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
            overflow-x: hidden;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
            animation: fadeInDown 1s ease-out;
        }

        .header h1 {
            font-size: 3rem;
            color: white;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            margin-bottom: 10px;
        }

        .header p {
            color: rgba(255,255,255,0.9);
            font-size: 1.2rem;
        }

        .search-section {
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
            animation: fadeInUp 1s ease-out 0.3s both;
        }

        .search-box {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }

        .search-input {
            flex: 1;
            padding: 15px 20px;
            border: 2px solid #e1e8ed;
            border-radius: 50px;
            font-size: 1.1rem;
            outline: none;
            transition: all 0.3s ease;
            background: white;
        }

        .search-input:focus {
            border-color: #667eea;
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.2);
        }

        .search-btn {
            padding: 15px 30px;
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 50px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }

        .search-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }

        .search-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
            color: #667eea;
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }

        .results-section {
            display: none;
            animation: slideInUp 0.8s ease-out;
        }

        .stock-card {
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
            margin-bottom: 20px;
        }

        .stock-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
        }

        .stock-title {
            font-size: 2rem;
            color: #333;
            font-weight: 700;
        }

        .stock-ticker {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 1.1rem;
        }

        .price-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .price-card {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            transition: transform 0.3s ease;
        }

        .price-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }

        .price-label {
            color: #666;
            font-size: 0.9rem;
            margin-bottom: 8px;
            text-transform: uppercase;
            font-weight: 600;
        }

        .price-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #333;
        }

        .price-change {
            margin-top: 5px;
            font-size: 1.1rem;
            font-weight: 600;
        }

        .positive { color: #28a745; }
        .negative { color: #dc3545; }

        .analysis-section {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 15px;
            padding: 25px;
            margin-top: 20px;
        }

        .analysis-title {
            font-size: 1.5rem;
            color: #333;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .analysis-content {
            line-height: 1.6;
            color: #555;
            font-size: 1.1rem;
        }

        .error-message {
            background: #ffe6e6;
            color: #d63384;
            padding: 15px 20px;
            border-radius: 10px;
            border-left: 4px solid #d63384;
            margin: 20px 0;
            display: none;
        }

        .demo-section {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            margin-top: 20px;
            text-align: center;
        }

        .demo-title {
            color: white;
            font-size: 1.3rem;
            margin-bottom: 15px;
        }

        .demo-buttons {
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .demo-btn {
            padding: 10px 20px;
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.9rem;
        }

        .demo-btn:hover {
            background: rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }

        .api-info {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            text-align: center;
            color: white;
        }

        .api-links {
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 15px;
        }

        .api-link {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            text-decoration: none;
            transition: all 0.3s ease;
            font-size: 0.9rem;
        }

        .api-link:hover {
            background: rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }

        @keyframes fadeInDown {
            from {
                opacity: 0;
                transform: translateY(-30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 2rem;
            }
            
            .search-box {
                flex-direction: column;
            }
            
            .stock-header {
                flex-direction: column;
                gap: 15px;
                text-align: center;
            }
            
            .price-grid {
                grid-template-columns: 1fr;
            }

            .demo-buttons, .api-links {
                flex-direction: column;
                align-items: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📈 Stock Market Analyzer</h1>
            <p>Real-time stock analysis with AI-powered insights</p>
        </div>

        <div class="api-info">
            <div>🚀 <strong>FastAPI Backend Integration Active</strong></div>
            <div class="api-links">
                <a href="/docs" class="api-link" target="_blank">📖 API Documentation</a>
                <a href="/redoc" class="api-link" target="_blank">📘 Alternative Docs</a>
                <a href="/health" class="api-link" target="_blank">🏥 Health Check</a>
            </div>
        </div>

        <div class="search-section">
            <div class="search-box">
                <input 
                    type="text" 
                    id="searchInput" 
                    class="search-input" 
                    placeholder="Enter company name or ticker symbol (e.g., Apple, TSLA, Microsoft)"
                    onkeypress="handleEnter(event)"
                />
                <button id="searchBtn" class="search-btn" onclick="analyzeStock()">
                    🔍 Analyze Stock
                </button>
            </div>

            <div class="demo-section">
                <div class="demo-title">Try these examples:</div>
                <div class="demo-buttons">
                    <button class="demo-btn" onclick="fillSearch('Apple')">Apple</button>
                    <button class="demo-btn" onclick="fillSearch('Tesla')">Tesla</button>
                    <button class="demo-btn" onclick="fillSearch('Microsoft')">Microsoft</button>
                    <button class="demo-btn" onclick="fillSearch('Google')">Google</button>
                    <button class="demo-btn" onclick="fillSearch('Amazon')">Amazon</button>
                </div>
            </div>

            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>Analyzing stock data...</div>
            </div>

            <div class="error-message" id="errorMessage"></div>
        </div>

        <div class="results-section" id="results">
            <div class="stock-card">
                <div class="stock-header">
                    <div class="stock-title" id="companyName">Company Name</div>
                    <div class="stock-ticker" id="tickerSymbol">TICKER</div>
                </div>

                <div class="price-grid">
                    <div class="price-card">
                        <div class="price-label">💰 Current Price (USD)</div>
                        <div class="price-value" id="priceUSD">$0.00</div>
                    </div>
                    <div class="price-card">
                        <div class="price-label">💰 Current Price (INR)</div>
                        <div class="price-value" id="priceINR">₹0.00</div>
                    </div>
                    <div class="price-card">
                        <div class="price-label">📈 Change (USD)</div>
                        <div class="price-value price-change" id="changeUSD">$0.00</div>
                    </div>
                    <div class="price-card">
                        <div class="price-label">📈 Change (INR)</div>
                        <div class="price-value price-change" id="changeINR">₹0.00</div>
                    </div>
                </div>

                <div class="analysis-section">
                    <div class="analysis-title">
                        🧠 AI Analysis & Market Insights
                    </div>
                    <div class="analysis-content" id="analysisContent">
                        Analysis will appear here...
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Get the current host dynamically
        const API_BASE_URL = window.location.origin;

        async function analyzeStock() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) {
                showError('Please enter a company name or ticker symbol');
                return;
            }

            setLoading(true);
            hideError();

            try {
                const response = await fetch(`${API_BASE_URL}/analyze`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ query: query })
                });

                const result = await response.json();

                if (result.success) {
                    displayResults(result.data);
                } else {
                    showError(result.error || 'An error occurred while analyzing the stock');
                }
            } catch (error) {
                console.error('API Error:', error);
                showError('Network error: ' + error.message);
            } finally {
                setLoading(false);
            }
        }

        function displayResults(data) {
            document.getElementById('companyName').textContent = data.company;
            document.getElementById('tickerSymbol').textContent = data.ticker;
            document.getElementById('priceUSD').textContent = `$${data.price}`;
            document.getElementById('priceINR').textContent = `₹${data.price_inr}`;
            
            const changeUSDElement = document.getElementById('changeUSD');
            const changeINRElement = document.getElementById('changeINR');
            
            const changeSign = data.change >= 0 ? '+' : '';
            changeUSDElement.textContent = `${changeSign}$${data.change} (${data.percent}%)`;
            changeINRElement.textContent = `${changeSign}₹${data.change_inr} (${data.percent}%)`;
            
            // Apply color classes
            const colorClass = data.change >= 0 ? 'positive' : 'negative';
            changeUSDElement.className = `price-value price-change ${colorClass}`;
            changeINRElement.className = `price-value price-change ${colorClass}`;
            
            document.getElementById('analysisContent').textContent = data.analysis;
            document.getElementById('results').style.display = 'block';
        }

        function setLoading(isLoading) {
            const loadingElement = document.getElementById('loading');
            const searchBtn = document.getElementById('searchBtn');
            
            if (isLoading) {
                loadingElement.style.display = 'block';
                searchBtn.disabled = true;
                searchBtn.textContent = 'Analyzing...';
            } else {
                loadingElement.style.display = 'none';
                searchBtn.disabled = false;
                searchBtn.textContent = '🔍 Analyze Stock';
            }
        }

        function showError(message) {
            const errorElement = document.getElementById('errorMessage');
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }

        function hideError() {
            document.getElementById('errorMessage').style.display = 'none';
        }

        function handleEnter(event) {
            if (event.key === 'Enter') {
                analyzeStock();
            }
        }

        function fillSearch(company) {
            document.getElementById('searchInput').value = company;
        }

        // Health check for backend connection
        async function checkBackendHealth() {
            try {
                const response = await fetch(`${API_BASE_URL}/health`);
                const data = await response.json();
                console.log('Backend health:', data);
                return true;
            } catch (error) {
                console.warn('Backend health check failed:', error.message);
                return false;
            }
        }

        // Add some interactive effects
        document.addEventListener('DOMContentLoaded', function() {
            // Check backend health on page load
            checkBackendHealth().then(isHealthy => {
                if (isHealthy) {
                    console.log('✅ FastAPI backend is running and healthy!');
                } else {
                    showError('Backend health check failed. Some features may not work properly.');
                }
            });

            // Add focus effect to search input
            const searchInput = document.getElementById('searchInput');
            searchInput.addEventListener('focus', function() {
                this.parentElement.style.transform = 'scale(1.02)';
            });
            
            searchInput.addEventListener('blur', function() {
                this.parentElement.style.transform = 'scale(1)';
            });
        });
    </script>
</body>
</html>
"""

# FastAPI Routes

@app.get("/")
async def serve_frontend():
    """
    Serve the integrated HTML frontend
    """
    return HTMLResponse(content=get_html_content())

@app.post("/analyze", response_model=StockAnalysisResponse)
async def analyze_stock_endpoint(request: StockAnalysisRequest):
    """
    Analyze stock data for a given company or ticker
    
    - **query**: Company name or ticker symbol (e.g., "Apple", "TSLA", "Microsoft")
    
    Returns real-time stock data with AI-powered analysis
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty")

    print(f"{Fore.BLUE}🔎 API Request: Analyzing '{request.query}'")
    
    try:
        result = await analyze_stock_data(request.query.strip())
        
        if result["success"]:
            print(f"{Fore.GREEN}✅ Analysis completed successfully")
            return StockAnalysisResponse(
                success=True,
                data=StockData(**result["data"])
            )
        else:
            print(f"{Fore.RED}❌ Analysis failed: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])

    except HTTPException:
        raise
    except Exception as e:
        print(f"{Fore.RED}API Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint to verify API status and configuration"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        apis_configured={
            "finnhub": bool(FINNHUB_API_KEY),
            "tavily": bool(TAVILY_API_KEY),
            "groq": bool(GROQ_API_KEY)
        }
    )

# Original CLI function (preserved for backward compatibility)
def analyze_stock_cli(query: str):
    """Original function for CLI usage - runs async function in sync context"""
    result = asyncio.run(analyze_stock_data(query))
    
    if result["success"]:
        data = result["data"]
        print(f"{Fore.CYAN}🔍 Identified Ticker: {data['ticker']} for Company: {data['company']}")
        print(f"{Fore.GREEN}💰 Current Price: ${data['price']} / ₹{data['price_inr']}")
        
        change_symbol = "+" if data['change'] >= 0 else ""
        print(f"{Fore.YELLOW}📈 Price Change: {change_symbol}${data['change']} / {change_symbol}₹{data['change_inr']} ({data['percent']:.2f}%)")
        print(f"{Fore.MAGENTA}📊 Ticker Analysis:\n{data['analysis']}")
        
        print(Style.BRIGHT + f"\n📈 Final Summary for {data['company']} ({data['ticker']}):")
        print(f"✅ Price: ${data['price']} / ₹{data['price_inr']}")
        print(f"📉 Change: {change_symbol}${data['change']} / {change_symbol}₹{data['change_inr']} ({data['percent']:.2f}%)")
        print(f"🧠 Analysis:\n{data['analysis']}")
    else:
        print(Fore.RED + result["error"])

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Stock Analysis Tool with FastAPI and Integrated Frontend')
    parser.add_argument('--mode', choices=['api', 'cli'], default='api', 
                       help='Run in API mode with integrated frontend (default) or CLI mode')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8000)), 
                       help='Port for API mode (default from PORT env or 8000)')
    parser.add_argument('--host', default='0.0.0.0', 
                       help='Host for API mode (default: 0.0.0.0)')
    
    args = parser.parse_args()
    
    if args.mode == 'api':
        print(f"{Fore.GREEN}🚀 Starting Stock Analysis FastAPI Server with Integrated Frontend...")
        print(f"{Fore.CYAN}🌐 Frontend available at: http://{args.host}:{args.port}")
        print(f"{Fore.CYAN}📡 API Server running at: http://{args.host}:{args.port}")
        print(f"{Fore.CYAN}📋 Health check: http://{args.host}:{args.port}/health")
        print(f"{Fore.CYAN}📖 API Docs: http://{args.host}:{args.port}/docs")
        print(f"{Fore.CYAN}📘 ReDoc: http://{args.host}:{args.port}/redoc")
        print(f"{Fore.YELLOW}⚡ Ready to analyze stocks!")
        print(f"{Fore.MAGENTA}💡 Just open your browser and visit the URL above!")
        
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            log_level="info",
            reload=True  # Enable auto-reload during development
        )
    else:
        # CLI mode
        print(f"{Fore.GREEN}🚀 Stock Analysis CLI Mode")
        while True:
            query = input(Fore.BLUE + "🔎 Enter your stock-related query (or 'exit' to quit): ")
            if query.lower() == "exit":
                break
            analyze_stock_cli(query)
            print("\n" + "-" * 60 + "\n")