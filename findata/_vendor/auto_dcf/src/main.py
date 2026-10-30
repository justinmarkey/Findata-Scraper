from src.data_fetch import get_company_data
from src.wacc import cost_of_equity, cost_of_debt, calculate_wacc
from src.dcf import calculate_dcf

def main ():
    
    ticker = "AMZN"
    #model assumptions
    risk_free = 0.042 # 10y US Treasury yield
    market_return = 0.095 # S&p 500 average return
    tax_rate = 0.21
    growth_rate = 0.08          # FCF growth for projection
    terminal_growth = 0.025     # long-term growth
    projection_years = 7

    # fetch company data
    data = get_company_data(ticker)

    beta = data["beta"]
    market_cap = data["market_cap"]
    total_debt = data["total_debt"]
    interest_expense = data["interest_expense"]
    net_debt = data["net_debt"]
    shares_outstanding = data["shares_outstanding"]
    initial_fcf = data["fcf"]

    # Compute WACC
    ke = cost_of_equity(risk_free, beta, market_return)
    kd = cost_of_debt(interest_expense, total_debt)

    wacc = calculate_wacc(
        market_cap,
        total_debt,
        ke,
        kd,
        tax_rate
    )

    # Compute DCF
    intrinsic_value = calculate_dcf(
        initial_fcf=initial_fcf,
        growth_rate=growth_rate,
        wacc=wacc,
        terminal_growth=terminal_growth,
        years=projection_years,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding
    )

    print("Ticker:", ticker)
    print("WACC:", round(wacc * 100, 2), "%")
    print("Intrinsic value per share: $", round(intrinsic_value, 2))

if __name__ == "__main__":
    main()