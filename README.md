# backtesting

When selecting parameters by month, final backtesting results for the entire period do not correspond to the cumulative return by month. The problem is as follows:
- some transactions at the end of the month are not taken into account. It is necessary to add data on unclosed transactions (data is stored in equity_curve['Equity'])
