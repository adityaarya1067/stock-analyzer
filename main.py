import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from colorama import Fore, Style, init
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    docs_url="/docs",  # Swagger UI available at /docs
    redoc_url="/redoc"  # ReDoc available at /redoc
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
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

# FastAPI Routes
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

@app.get("/")
async def root():
    """Basic info endpoint"""
    return {
        "message": "Stock Analysis API with FastAPI",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "/analyze": "POST - Analyze stock data",
            "/health": "GET - Health check",
            "/docs": "GET - Interactive API documentation",
            "/redoc": "GET - Alternative API documentation"
        }
    }

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
    
    parser = argparse.ArgumentParser(description='Stock Analysis Tool with FastAPI')
    parser.add_argument('--mode', choices=['api', 'cli'], default='api', 
                       help='Run in API mode (default) or CLI mode')
    parser.add_argument('--port', type=int, default=8000, 
                       help='Port for API mode (default: 8000)')
    parser.add_argument('--host', default='0.0.0.0', 
                       help='Host for API mode (default: 127.0.0.1)')
    
    args = parser.parse_args()
    
    if args.mode == 'api':
        print(f"{Fore.GREEN}🚀 Starting Stock Analysis FastAPI Server...")
        print(f"{Fore.CYAN}📡 Server running at: http://{args.host}:{args.port}")
        print(f"{Fore.CYAN}📋 Health check: http://{args.host}:{args.port}/health")
        print(f"{Fore.CYAN}📖 API Docs: http://{args.host}:{args.port}/docs")
        print(f"{Fore.CYAN}📘 ReDoc: http://{args.host}:{args.port}/redoc")
        print(f"{Fore.YELLOW}⚡ Ready to analyze stocks!")
        
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            reload=True,  # Auto-reload on code changes
            log_level="info"
        )
    else:
        # Original CLI mode
        print(f"{Fore.GREEN}🚀 Stock Analysis CLI Mode")
        while True:
            query = input(Fore.BLUE + "🔎 Enter your stock-related query (or 'exit' to quit): ")
            if query.lower() == "exit":
                break
            analyze_stock_cli(query)
            print("\n" + "-" * 60 + "\n")