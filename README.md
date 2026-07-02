# Smart Money Trading Strategy App

A multi-page Streamlit web application for backtesting and screening Smart Money Concepts (SMC) trading strategies.

## Pages

| Page | Description |
|------|-------------|
| 🏠 Home | Strategy overview and key metrics |
| 🔍 Backtester | Run backtest on any stocks |
| 📊 Results Analysis | Analyse performance by sector and stock |
| 🎯 Daily Screener | Scan stocks for active setups |
| 📐 Risk Calculator | Position sizing and trade planning |
| 📚 Strategy Guide | Complete strategy reference |

## Deploy to Streamlit Cloud (Free)

### Step 1: Create GitHub Repository
1. Go to https://github.com and sign in (or create free account)
2. Click **New Repository**
3. Name it: `smart-money-strategy`
4. Set to **Public**
5. Click **Create Repository**

### Step 2: Upload Files
Upload these files to your GitHub repository:
```
smart_money_app/
├── app.py
├── requirements.txt
├── README.md
└── pages/
    ├── __init__.py
    ├── home.py
    ├── backtest.py
    ├── results.py
    ├── screener.py
    ├── risk_calc.py
    └── guide.py
```

**Option A — Upload via GitHub website:**
1. Click **Add file → Upload files**
2. Drag all files from the `smart_money_app` folder
3. Click **Commit changes**

**Option B — Upload via Git (if installed):**
```bash
git clone https://github.com/YOUR_USERNAME/smart-money-strategy.git
cp -r smart_money_app/* smart-money-strategy/
cd smart-money-strategy
git add .
git commit -m "Initial upload"
git push
```

### Step 3: Deploy on Streamlit Cloud
1. Go to https://share.streamlit.io
2. Sign in with your GitHub account
3. Click **New app**
4. Select:
   - **Repository:** `YOUR_USERNAME/smart-money-strategy`
   - **Branch:** `main`
   - **Main file path:** `app.py`
5. Click **Deploy!**
6. Wait 2-3 minutes for deployment
7. Your app will be live at:
   `https://YOUR_USERNAME-smart-money-strategy-app-XXXXX.streamlit.app`

### Step 4: Share Your App
Copy the URL and share it with anyone!
The app is completely free on Streamlit Cloud.

## Local Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Strategy Performance (Backtested)

- **Stocks Tested:** 449 S&P 500 stocks
- **Win Rate:** 69.87% (full S&P 500) | 92% (optimised universe)
- **Avg RR:** 1.94x
- **Expected Value:** +1.054R per trade
- **Best Sectors:** Consumer Staples (77.9%), Industrials (74.1%)
- **Avoid:** Energy sector (54.5% win rate)

## Disclaimer

Past performance does not guarantee future results.
This tool is for educational purposes only.
Always manage risk responsibly.
