def calculate_budget_utilization(spent, budget):
    """Returns spend as a percentage of budget. 0 when budget is not positive."""
    return (spent / budget) * 100 if budget and budget > 0 else 0
