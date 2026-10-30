import yfinance as yf


def get_company_data(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)

    info = ticker.info
    balance = ticker.balance_sheet
    income = ticker.income_stmt
    cashflow = ticker.cashflow

    data = {}

    # Beta
    data["beta"] = info.get("beta")

    # Market cap
    data["market_cap"] = info.get("marketCap")

    # Shares outstanding
    data["shares_outstanding"] = info.get("sharesOutstanding")

    # Total debt
    try:
        total_debt = balance.loc["Total Debt"][0]
    except:
        total_debt = 0

    # Cash
    try:
        cash = balance.loc["Cash And Cash Equivalents"][0]
    except:
        cash = 0

    data["total_debt"] = total_debt
    data["cash"] = cash
    data["net_debt"] = total_debt - cash

    # Interest expense
    try:
        data["interest_expense"] = abs(income.loc["Interest Expense"][0])
    except:
        data["interest_expense"] = 0

    # Free cash flow
    try:
        data["fcf"] = cashflow.loc["Free Cash Flow"][0]
    except:
        data["fcf"] = None

    return data