def project_fcf(initial_fcf, growth_rate, years):
    """
    Projects free cash flow for a number of years.
    """
    fcfs = []
    fcf = initial_fcf

    for _ in range(years):
        fcf *= (1 + growth_rate)
        fcfs.append(fcf)

    return fcfs


def terminal_value(last_fcf, wacc, terminal_growth):
    """
    Gordon Growth terminal value.
    """
    return last_fcf * (1 + terminal_growth) / (wacc - terminal_growth)


def discount_cash_flows(fcfs, wacc):
    """
    Discounts a list of cash flows.
    """
    discounted = []

    for i, fcf in enumerate(fcfs, start=1):
        discounted.append(fcf / (1 + wacc) ** i)

    return sum(discounted)


def calculate_dcf(initial_fcf, growth_rate, wacc, terminal_growth, years, net_debt,  shares_outstanding):

    # Project future FCF
    fcfs = project_fcf(initial_fcf, growth_rate, years)

    # Discount the projected FCF
    pv_fcfs = discount_cash_flows(fcfs, wacc)

    # Calculate terminal value and discount it
    tv = terminal_value(fcfs[-1], wacc, terminal_growth)
    pv_tv = tv / (1 + wacc) ** years

    # Calculate enterprise value
    enterprise_value = pv_fcfs + pv_tv

    #Calculate equity value
    equity_value = enterprise_value - net_debt

    # Calculate intrinsic value per share
    intrinsic_value = equity_value / shares_outstanding

    return intrinsic_value