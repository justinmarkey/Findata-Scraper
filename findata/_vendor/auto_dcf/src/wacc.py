def cost_of_equity(risk_free, beta, market_return):
    return risk_free + beta * (market_return - risk_free)


def cost_of_debt(interest_expense, total_debt):
    if total_debt == 0:
        return 0
    return interest_expense / total_debt


def calculate_wacc(market_cap, total_debt, cost_equity, cost_debt, tax_rate):
    total_value = market_cap + total_debt

    weight_equity = market_cap / total_value
    weight_debt = total_debt / total_value

    wacc = (weight_equity * cost_equity + weight_debt * cost_debt * (1 - tax_rate))

    return wacc