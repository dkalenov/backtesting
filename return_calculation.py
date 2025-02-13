unclosed transactions 


# Total PnL from closed trades
total_pnl = res._trades['PnL'].sum()

# Taking into account unclosed positions
open_pnl = res._equity_curve['Equity'].iloc[-1] - (1_000_000 + total_pnl)

# Correct Equity Final calculation
equity_final_manual = 1_000_000 + total_pnl + open_pnl

# Final Return [%]
return_manual = ((equity_final_manual - 1_000_000) / 1_000_000) * 100
print("Corrected Return [%]:", return_manual)
