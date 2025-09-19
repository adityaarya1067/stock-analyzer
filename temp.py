import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from colorama import Fore, Style, init
load_dotenv()
init(autoreset=True)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    
groq_client = ChatGroq(api_key=GROQ_API_KEY, model_name="llama-3.1-8b-instant")
# print(GROQ_API_KEY)

def rupees_from_usd(usd_amount):
    conversion_rate = 82.0
    return round(usd_amount * conversion_rate, 2)

def identify_ticker(query):
    url = f'https://finnhub.io/api/v1/search?q={query}&token={FINNHUB_API_KEY}'
    data = requests.get(url).json()
    if data.get("count", 0) > 0:
        symbol = data['result'][0]['symbol']
        description = data['result'][0]['description']
        return symbol, description
    return None, None

def ticker_price(ticker):
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}"
    r = requests.get(url).json()
    return r.get('c')

def ticker_price_change(ticker):
    url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}'
    data = requests.get(url).json()
    current_price = data.get('c')
    previous_close = data.get('pc')

    if current_price is None or previous_close is None:
        raise ValueError("Price data missing in API response")

    change = current_price - previous_close
    percent_change = (change / previous_close) * 100
    return round(change, 2), round(percent_change, 2)

def ticker_news(company_name):
    url = f"https://api.tavily.com/v1/news?query={company_name}&limit=5"
    headers = {"Authorization": f"Bearer {TAVILY_API_KEY}"}
    response = requests.get(url, headers=headers)

    try:
        data = response.json()
    except Exception:
        print("❌ Failed to parse Tavily response:", response.text)
        return "No news available.", []

    articles = data.get("articles") or data.get("results", [])
    if not articles:
        return "No recent news available.", []
    
    combined_text = " ".join([f"{a['title']}. {a.get('description', '')}" for a in articles])
    return combined_text, articles


def summarize_with_groq(news_text, price_change_info):
    prompt = f"""
You're a financial analyst.

Analyze the recent price change of the company:
- {price_change_info}
- Recent News Headlines:

{news_text}

Explain the possible reasons for this price movement based on the headlines and news summaries and don't introduce yourself in the response.
"""
    response = groq_client.invoke(prompt)
    # Ensure correct parsing
    if hasattr(response, "content"):
        return response.content
    elif isinstance(response, dict) and "content" in response:
        return response["content"]
    else:
        return str(response)


def ticker_analysis(company, ticker, news_text, articles, change, percent):
    news_points = "\n".join([f"- {a['title']}" for a in articles])
    price_change_info = f"Price changed by {change} USD ({percent}%) for {company} ({ticker})"
    
    # Fixed: Now properly calling summarize_with_groq with both required arguments
    analysis = summarize_with_groq(news_points, price_change_info)
    return analysis

def analyze_stock(query):
    ticker, company = identify_ticker(query)
    if not ticker:
        print(Fore.RED + "❌ Couldn't identify a valid company in your query.")
        return

    print(f"{Fore.CYAN}🔍 Identified Ticker: {ticker} for Company: {company}")

    try:
        price = ticker_price(ticker)
        price_inr = rupees_from_usd(price)
        print(f"{Fore.GREEN}💰 Current Price: ${price} / ₹{price_inr}")
    except Exception as e:
        print(Fore.RED + f"Error fetching price: {e}")
        return

    try:
        change, percent = ticker_price_change(ticker)
        change_inr = rupees_from_usd(change)
        # Fixed: Handle negative changes properly in display
        change_symbol = "+" if change >= 0 else ""
        print(f"{Fore.YELLOW}📈 Price Change: {change_symbol}${change} / {change_symbol}₹{change_inr} ({percent:.2f}%)")
    except Exception as e:
        print(Fore.RED + f"Error fetching price change: {e}")
        return

    try:
        news_text, articles = ticker_news(company)
        analysis = ticker_analysis(company, ticker, news_text, articles, change, percent)
        print(f"{Fore.MAGENTA}📊 Ticker Analysis:\n{analysis}")
    except Exception as e:
        print(Fore.RED + f"Error fetching or analyzing news: {e}")
        return

    print(Style.BRIGHT + f"\n📈 Final Summary for {company} ({ticker}):")
    print(f"✅ Price: ${price} / ₹{price_inr}")
    change_symbol = "+" if change >= 0 else ""
    print(f"📉 Change: {change_symbol}${change} / {change_symbol}₹{change_inr} ({percent:.2f}%)")
    print(f"🧠 Analysis:\n{analysis}")

if __name__ == "__main__":
    while True:
        query = input(Fore.BLUE + "🔎 Enter your stock-related query (or 'exit' to quit): ")
        if query.lower() == "exit":
            break
        analyze_stock(query)
        print("\n" + "-" * 60 + "\n")
        