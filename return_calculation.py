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






import pandas as pd
from datetime import datetime
from hyperopt import fmin, tpe, hp, Trials
import backtesting
from dateutil.relativedelta import relativedelta
import traceback

def generate_monthly_intervals(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m")
    end = datetime.strptime(end_date, "%Y-%m")
    intervals = []
    while start <= end:
        next_month = start + relativedelta(months=1)
        intervals.append((start.strftime("%Y-%m"), next_month.strftime("%Y-%m")))
        start = next_month
    return intervals

def full_period_backtest(strategy, data, initial_capital=1_000_000):
    data.index = pd.to_datetime(data.index).tz_localize(None)
    test = backtesting.Backtest(data, strategy, cash=initial_capital, commission=0.0005)
    res = test.run()
    trades = res._trades.copy()
    # print(res)
    return trades, res

from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

def analyze_monthly_results(trades, intervals, initial_capital, equity_curve):
    trades['ExitTime'] = pd.to_datetime(trades['ExitTime']).dt.tz_localize(None)
    trades['Close Time'] = pd.to_datetime(trades['ExitTime'])
    trades.set_index('Close Time', inplace=True)
    trades['Trade Duration'] = (trades['ExitTime'] - trades['EntryTime']).dt.total_seconds()

    monthly_results = {}
    total_pnl = 0
    profit_months = 0
    loss_months = 0
    total_trade_duration = 0
    total_trades = len(trades)
    
    capital = initial_capital  
    last_interval = intervals[-1]  # Последний месяц

    for start, end in intervals:
        start_date = datetime.strptime(start, "%Y-%m")
        end_date = datetime.strptime(end, "%Y-%m") + relativedelta(months=1, days=-1, hours=23, minutes=59, seconds=59)

        monthly_trades = trades[(trades.index >= start_date) & (trades.index <= end_date)]

        if monthly_trades.empty:
            monthly_results[start] = (0.0, 0)
            continue

        # PnL за месяц
        monthly_pnl = monthly_trades['PnL'].sum()
        capital += monthly_pnl  # Обновляем капитал только на PnL

        # Если это последний месяц, учитываем открытые позиции
        if (start, end) == last_interval and not equity_curve.empty:
            last_equity = equity_curve['Equity'].iloc[-1]  # Финальная Equity
            open_pnl = last_equity - capital  # Открытые позиции
            capital += open_pnl  # Учитываем их в капитале

        # Итоговый процент профита за месяц
        prev_capital = capital - monthly_pnl  # Капитал до учета текущего месяца
        monthly_pnl_percent = ((capital - prev_capital) / prev_capital) * 100 if prev_capital != 0 else 0

        # Средняя длительность сделки (в часах)
        avg_trade_duration = monthly_trades['Trade Duration'].mean() / 3600 if len(monthly_trades) > 0 else 0

        monthly_results[start] = (round(monthly_pnl_percent, 8), round(avg_trade_duration, 2))

        total_pnl += monthly_pnl
        total_trade_duration += monthly_trades['Trade Duration'].sum()

        if monthly_pnl_percent > 0:
            profit_months += 1
        else:
            loss_months += 1

    avg_trade_duration_total = (total_trade_duration / total_trades) / 3600 if total_trades > 0 else 0
    total_months = profit_months + loss_months
    profit_month_ratio = (profit_months / total_months * 100) if total_months > 0 else 0

    # Итоговый Return [%]
    total_return = ((capital - initial_capital) / initial_capital) * 100

    return total_return, profit_months, loss_months, monthly_results, avg_trade_duration_total, profit_month_ratio



def generate_search_space(params_to_optimize):
    space = {}
    for param, settings in params_to_optimize.items():
        if settings['type'] == 'quniform':
            space[param] = hp.quniform(param, settings['range'][0], settings['range'][1], settings.get('q', 1))
        elif settings['type'] == 'uniform':
            space[param] = hp.uniform(param, settings['range'][0], settings['range'][1])
        else:
            raise ValueError(f"Неизвестный тип параметра: {settings['type']}")
    return space

def optimize_strategy(data, symbol, interval, start_date, end_date, shared_folder_path, max_evals, params_to_optimize, fixed_params):
    intervals = generate_monthly_intervals(start_date, end_date)
    trials = Trials()
    space = generate_search_space(params_to_optimize)
    results = []

    print(f"Общее количество строк в загруженных данных: {len(data)}")
    print(f"Диапазон дат: {data.index.min()} - {data.index.max()}")
    print(f"Оптимизация для {symbol} ({interval}) с {start_date} по {end_date} началась...\n")

    def objective(params):
        for key, value in fixed_params.items():
            setattr(SlopingStrategy, key, value)

        for key, value in params.items():
            setattr(SlopingStrategy, key, int(value) if 'length' in key else value)

        print(f"Параметры: {params}, {fixed_params}")

        try:
            trades, res = full_period_backtest(SlopingStrategy, data, 1_000_000)

            total_pnl, profit_months, loss_months, monthly_results, avg_trade_duration, profit_month_ratio = analyze_monthly_results(
                trades, intervals, 1_000_000, res._equity_curve
            )

            print(f"Общий профит: {total_pnl:.2f}%, Профитные месяцы: {profit_months}, Убыточные месяцы: {loss_months}, Процент профитных месяцев: {profit_month_ratio:.2f}%")
            print(f"Результаты по месяцам: {[(month, pnl) for month, (pnl, _) in monthly_results.items()]}\n")

            row = {
                'symbol': symbol,
                'interval': interval,
                **{key: fixed_params.get(key, None) for key in fixed_params},
                **{key: (int(value) if 'length' in key else value) for key, value in params.items()},
                'total_pnl%': total_pnl,
                'avg_trade_duration_hours': avg_trade_duration,
                'profit_month_count': profit_months,
                'loss_month_count': loss_months,
                'profit_month_ratio%': profit_month_ratio
            }

            for month, (pnl, _) in monthly_results.items():
                row[month] = pnl

            results.append(row)
            return {'loss': -total_pnl, 'status': 'ok', 'params': params}

        except Exception as e:
            print("Ошибка в objective:", e)
            print(traceback.format_exc())  # Логирование полной трассировки ошибки
            return {'loss': float('inf'), 'status': 'fail', 'params': params}

    try:
        fmin(objective, space, algo=tpe.suggest, max_evals=max_evals, trials=trials)
    except Exception as e:
        print("Ошибка при выполнении fmin:", e)
        print(traceback.format_exc())
        return None

    results_df = pd.DataFrame(results)
    save_results_to_csv(results_df, shared_folder_path, "hyperopt_optimization_results.csv")

    if trials.trials:
        best_trial = min(trials.trials, key=lambda x: x['result']['loss'])
        best_params = best_trial['result']['params']
        best_loss = best_trial['result']['loss']
        return best_params, -best_loss
    else:
        print("Не удалось найти лучшие параметры.")
        return None


# best_params, total_pnl = optimize_strategy(
#     data=df,
#     symbol=symbol,
#     interval=interval,
#     start_date=start_date,
#     end_date=end_date,
#     max_evals=max_evals,
#     shared_folder_path=shared_folder_path,
#     params_to_optimize=params_to_optimize,
#     fixed_params=fixed_params
# )

# # Настройка стратегии с оптимизированными параметрами
# SlopingStrategy.window_length = fixed_params.get('window_length') or int(best_params['window_length'])
# SlopingStrategy.min_space = fixed_params.get('min_space') or int(best_params['min_space'])
# SlopingStrategy.sloping_atr_length = fixed_params.get('sloping_atr_length') or int(best_params['sloping_atr_length'])
# SlopingStrategy.take_profit_multiplier = fixed_params.get('take_profit_multiplier') or best_params['take_profit_multiplier']
# SlopingStrategy.stop_loss_multiplier = fixed_params.get('stop_loss_multiplier') or best_params['stop_loss_multiplier']

# print("\nНастройка стратегии завершена.")

# # Тестируем стратегию
# test = backtesting.Backtest(data=df, strategy=SlopingStrategy, cash=1_000_000, commission=0.0005)
# res = test.run()

# print(symbol)
# print()
# print("Результаты с оптимизированными параметрами:", res)
# print('Window length', SlopingStrategy.window_length)
# print('Min space', SlopingStrategy.min_space)
# print('Sloping atr length', SlopingStrategy.sloping_atr_length)
# print('Take profit multiplier', SlopingStrategy.take_profit_multiplier)
# print('Stop loss multiplier', SlopingStrategy.stop_loss_multiplier)
