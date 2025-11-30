## Intraday Momentum OI Unwinding – Issues & Fixes Log

This document summarizes the major issues encountered while implementing and backtesting the **Intraday Momentum OI Unwinding** strategy in Backtrader, and how each was resolved.

---

### 1. Timezone Mismatches (tz-aware vs tz-naive)

- **Symptoms**
  - `TypeError: Cannot subtract tz-naive and tz-aware datetime-like objects`
  - `TypeError: Invalid comparison between dtype=datetime64[ns, Asia/Kolkata] and Timestamp`
  - Errors appeared in both `data_loader.py` and `oi_analyzer.py` when comparing or subtracting `datetime` and `expiry`.
- **Root Cause**
  - CSV timestamps were loaded as timezone-aware IST.
  - Backtrader internally converts feed datetimes to UTC, exposing **tz-naive** `datetime` objects.
  - We were mixing tz-aware (`Asia/Kolkata`) series with tz-naive `Timestamp` objects in comparisons and differences.
- **Fix**
  - Load data as IST, filter by date range in IST.
  - Then explicitly **strip timezone while preserving wall-clock time**:
    - Convert to string via `dt.strftime('%Y-%m-%d %H:%M:%S')` and then back to `datetime` (no `tz_localize(None)`).
  - Standardize everything to **timezone-naive “market local time” (IST wall-clock)** in:
    - `src/data_loader.py` for `spot_df['datetime']`, `options_df['datetime']`, `options_df['expiry']`.
    - `src/oi_analyzer.py` and `strategies/intraday_momentum_oi.py` (all `pd.Timestamp(dt)` created as tz-naive).

---

### 2. No Trades Due to Strict Timestamp Matching

- **Symptoms**
  - Backtest ran without errors but **0 trades**.
  - Logs showed successful daily analysis, but OI/price lookups in `oi_analyzer` frequently returned empty.
- **Root Cause**
  - `calculate_oi_change`, `get_option_price_data`, and `get_strikes_near_spot` required **exact timestamp matches** between Backtrader bar times and options data.
  - Any tiny mismatch in seconds/milliseconds caused no data to be found.
- **Fix**
  - Introduced `get_options_data_at_timestamp(timestamp, expiry_date)` to:
    - Filter options for the same date + expiry.
    - Find the **nearest available timestamp within that day** using `abs(datetime - timestamp)` and `idxmin()`.
  - Updated:
    - `calculate_oi_change`
    - `get_option_price_data`
    - `get_strikes_near_spot`
  - Result: OI and price lookups now work reliably, even when timestamps don’t align perfectly.

---

### 3. VWAP Not Anchored to Opening

- **Symptoms**
  - VWAP used for entry checks did not strictly start at market open.
  - User requirement: **VWAP anchored to 9:15 AM IST**.
- **Root Cause**
  - VWAP was calculated over all available intraday history up to current time, not from the session open.
- **Fix**
  - In `strategies/intraday_momentum_oi.py` (`check_entry_conditions`):
    - Define `market_open_today = dt_ts.replace(hour=9, minute=15, second=0, microsecond=0)`.
    - Filter option history with:
      - `datetime >= market_open_today`
      - `datetime <= current time`
      - same `date`, `strike`, `option_type`, and `expiry`.
  - Compute VWAP using this **intraday slice from 9:15** only.

---

### 4. `check_entry_conditions` Not Being Called / Daily Analysis Gaps

- **Symptoms**
  - Logs showed:
    - `✓ Daily Analysis Complete` at 09:15.
    - `next()` and `is_trading_time` logs during the day.
  - But **no “Checking entry…” logs** and no trades on certain days.
- **Root Causes & Fixes**
  1. **Daily analysis state not tracked correctly**
     - Initially, there was logic depending on a daily analysis flag, which wasn’t being set consistently.
     - We simplified by:
       - Running `analyze_market(dt)` once per new day in `next()`.
       - Relying on `daily_direction`, `daily_strike`, `daily_expiry` being non-`None` to allow entries.
  2. **Hidden crashes inside logging**
     - Logging line `self.daily_expiry.date()` would raise if `daily_expiry` was `None`, and Backtrader swallowed the exception.
     - Fix:
       - Guarded `daily_expiry` with `expiry_str = self.daily_expiry.date() if self.daily_expiry else 'None'`.
       - Added more defensive checks and detailed logging for the daily state.

---

### 5. Incorrect Use of Manual `active_trades` Counter

- **Symptoms**
  - Logs showed `⚠️ Max positions reached: 1/1` even though **no entry signal / trade** was visible earlier.
  - Strategy stopped checking for new entries after the first “phantom” trade.
- **Root Cause**
  - A custom `self.active_trades` counter was incremented in `notify_order`, but Backtrader’s actual position lifecycle doesn’t always align perfectly with this simple counter.
  - Once `active_trades` reached `max_positions`, **further entries were blocked**, even when no true open position remained (or no trade actually executed).
- **Fix**
  - Removed `self.active_trades` entirely.
  - Replaced with **Backtrader’s built-in position tracking**:
    - Use `self.position.size != 0` to determine if we are already in a position.
  - Updated:
    - Entry gating in `check_entry_conditions` → checks `has_position = (self.position.size != 0)`.
    - EOD exit and position management in `next()` → also check `self.position.size`.

---

### 6. Trading Spot Index Instead of Options

- **Symptoms**
  - Logs originally showed:
    - Expected option price (e.g. `103.50`), but
    - `BUY EXECUTED` at prices like `23621.05` (NIFTY spot).
  - This meant Backtrader was placing orders on the **spot data feed**, not on option prices.
- **Root Cause**
  - Backtrader’s `self.buy()` operates on the attached data feed (`datas[0]` = spot).
  - Options prices lived only in a Pandas DataFrame (`options_df`), not as Backtrader data feeds.
- **Fix (Hybrid Approach)**
  - Kept Backtrader’s spot feed only for **time progression**.
  - Switched P&L and risk logic to use **actual option prices** from `options_df` via `oi_analyzer`:
    - On BUY (entry):
      - In `notify_order` (when `order.isbuy()`):
        - Call `get_option_price_data(...)` with `daily_strike`, `option_type`, `daily_expiry`, and `dt`.
        - Use `option_data['close']` as the **true entry price**.
        - Store `strike`, `option_type`, `expiry`, `entry_price`, `stop_loss`, `highest_price`, `trailing_stop` in `positions_dict`.
    - On SELL (exit):
      - In `notify_order` (sell branch):
        - Fetch option price at exit timestamp via `get_option_price_data(...)`.
        - Compute P&L purely from **option entry vs option exit**.
        - Log as:
          - `🔵 BUY OPTION EXECUTED: ...`
          - `🔴 SELL OPTION EXECUTED: ... | P&L: ₹X (Y%)`
  - Result: Strategy now **conceptually trades options**, even though Backtrader’s underlying mechanism uses the spot feed as a time axis.

---

### 7. Stop Loss & Trailing Stop Re-triggering on Every Bar

- **Symptoms**
  - Multiple identical stop-loss logs in consecutive minutes (e.g. repeated `🛑 STOP LOSS HIT` for the same CE 24200 position).
  - Indicated that `self.close()` had been called, but the same position kept being checked and re-closed.
- **Root Cause**
  - `manage_positions()`:
    - Checked SL / trailing-stop on every bar.
    - Called `self.close()` when condition hit.
    - But Backtrader executes orders on the **next bar**, and until then, `self.position` remains open.
    - Without a guard, the same SL condition fired repeatedly before the exit order actually executed.
- **Fix**
  - Introduced `self.pending_exit` flag:
    - Set `pending_exit = True` immediately after calling `self.close()` for SL or trailing stop.
    - `manage_positions()` returns early if `pending_exit` is `True` (no further exit checks).
    - Once the corresponding SELL is executed in `notify_order`, we:
      - Remove the position from `positions_dict`.
      - Reset `pending_exit = False`.
  - Also guarded EOD forced exits in `next()`:
    - Only call `close()` if `self.position.size != 0` **and** `not self.pending_exit`.

---

### 8. Reporting Errors with Zero Trades

- **Symptoms**
  - `KeyError: 'Winning Trades'` when **no trades** were executed.
  - Occurred in `src/reporter.py` when printing metrics.
- **Root Cause**
  - Report generation assumed that trade-related keys (`Winning Trades`, `Losing Trades`, etc.) existed even when `Total Trades == 0`.
- **Fix**
  - Added a safe guard in `print_metrics`:
    - Always print `Total Trades`.
    - If `Total Trades > 0`, print detailed win/loss stats.
    - Else print `"No trades executed."` and skip missing keys.

---

### 9. Position Sizing and Max Positions Behaviour

- **Symptoms**
  - Initially, `max_positions` was 1, and the strategy appeared to stop taking new signals after a single trade.
  - After switching to Backtrader’s `self.position`, further entries were still constrained to one open position at a time.
- **Fix**
  - Updated `config/strategy_config.yaml`:
    - `risk_management.max_positions: 2`
  - Logic-wise, we still use **one Backtrader position per instrument**, but entries are now controlled by:
    - `self.position.size` (already in a trade or not).
    - The strategy logic can be extended later if we introduce multiple data feeds to truly support multiple concurrent option positions.

---

### 10. High-Level Outcome

- **Current State**
  - Strategy:
    - Uses **1-minute** NIFTY spot candles as the time axis.
    - Derives option strikes and expiries from weekly options data.
    - Computes OI changes with robust timestamp matching.
    - Uses VWAP **anchored to 9:15 AM IST**.
    - Enters when:
      - Correct CALL/PUT decision based on OI distances.
      - OI is **unwinding** (short covering / long unwinding).
      - Option price is **above** its anchored VWAP.
    - Manages exits via:
      - Initial 25% stop loss.
      - 10% trailing stop after 10% profit.
      - EOD forced close.
  - Logging:
    - Rich, time-stamped logs for:
      - Daily analysis.
      - Entry checks and OI diagnostics.
      - VWAP vs price.
      - Buy/sell executions with option prices and P&L.
      - Stop loss and trailing stop triggers.

This log should be kept up to date as new issues are found and resolved, so we maintain a clear history of design decisions and fixes for this strategy.

---

### 11. Trades Executing But Not Being Saved to CSV

- **Symptoms**
  - Backtest logs showed `TRADE PROFIT` messages indicating trades were executing.
  - Final report showed "0 trades" even though trades were clearly happening.
  - `trades.csv` file was not being created or remained empty.
  - `🔴 SELL OPTION EXECUTED` messages were not appearing in logs.
- **Root Cause**
  - **Critical Discovery**: Backtrader creates **different `order.ref` values** for BUY and SELL orders.
  - The code used `order.ref` as the dictionary key to store position information on BUY.
  - When SELL order executed, it tried to look up position info using the SELL order's `order.ref`.
  - Since SELL order had a different ref than BUY order, the lookup failed → no position info found → trade recording code never executed.
- **Fix**
  - Added `self.current_position` variable to directly track the currently open position.
  - On BUY order execution:
    - Store all position info (entry price, strike, expiry, stop loss, etc.) in `self.current_position`.
    - Also keep backward compatibility by storing in `positions_dict[order.ref]`.
  - On SELL order execution:
    - Use `self.current_position` directly instead of `positions_dict[order.ref]` lookup.
    - Write trade record to CSV **immediately** using `csv.DictWriter` with append mode.
    - Set `self.current_position = None` after recording.
  - Result: Trade recording now works reliably regardless of Backtrader's order ref behavior.

---

### 12. Trades Logged But Not Saved to CSV File

- **Symptoms**
  - Trade logs appeared on terminal showing BUY/SELL executions with P&L.
  - But `reports/trades.csv` remained empty or wasn't created.
  - Even after backtest completed successfully, no trade records in file.
- **Root Cause**
  - Trades were being stored in memory (`self.trade_log` list) but not written to disk.
  - CSV file was only created with headers in `__init__`, but trade records were never appended.
- **Fix**
  - Modified `notify_order()` SELL branch to write trades immediately:
    ```python
    # After creating trade_record dictionary
    self.trade_log.append(trade_record)  # Store in memory

    # ✅ WRITE TO DISK IMMEDIATELY - NO DATA LOSS!
    with open(self.trade_log_file, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[...])
        writer.writerow(trade_record)
    ```
  - This ensures each trade is written to disk **as soon as it completes**, not at end of backtest.
  - Benefit: Even if backtest is interrupted (Ctrl+C), all completed trades are already saved.

---

### 13. No Terminal Output Logging to File

- **Symptoms**
  - User wanted all terminal output saved to timestamped log files.
  - Running `python backtest_runner.py` only showed output on screen, nothing saved.
  - After backtest completed, no way to review what happened.
- **Root Cause**
  - Python script only printed to stdout/stderr with no file capture.
  - User needed both real-time terminal viewing AND permanent log file storage.
- **Fix**
  - Created `run_backtest.sh` script that:
    1. Generates timestamp: `TIMESTAMP=$(date +"%Y%m%d_%H%M%S")`
    2. Creates unique log file: `LOG_FILE="reports/backtest_log_${TIMESTAMP}.txt"`
    3. Deletes old trades.csv to ensure fresh start
    4. Runs backtest with `tee` for dual output:
       ```bash
       python -u backtest_runner.py 2>&1 | tee "$LOG_FILE"
       ```
       - `python -u`: Unbuffered output (real-time)
       - `2>&1`: Capture both stdout and stderr
       - `| tee`: Show on terminal AND save to file simultaneously
  - Created documentation: `README_LOGGING.md` and `HOW_TO_RUN.md`

---

### 14. Multiple Duplicate BUY Orders for Same Position

- **Symptoms**
  - Logs showed multiple `📈 PLACING BUY ORDER` messages within seconds of each other.
  - System was trying to enter same position multiple times.
  - Led to confusion and potentially multiple orders being placed.
- **Root Cause**
  - `check_entry_conditions()` was called on every bar (every minute).
  - When entry signal appeared, `self.buy()` was called.
  - But the order didn't execute until next bar, so `self.position.size` remained 0.
  - Next bar: Still no position (order pending), so `check_entry_conditions()` triggered again → another `self.buy()` call.
- **Fix**
  - Added `self.pending_entry` flag:
    - Set `pending_entry = True` immediately after calling `self.buy()`.
    - In `check_entry_conditions()`, added check:
      ```python
      if has_position or self.pending_entry:
          return None  # Don't check for new entries
      ```
    - Reset `pending_entry = False` when BUY order executes in `notify_order()`.
  - Result: Only one entry order per signal, no duplicates.

---

### 15. Graceful Shutdown and Summary Files Not Generated on Ctrl+C

- **Symptoms**
  - User pressed Ctrl+C to stop backtest.
  - Trades.csv had completed trades (due to immediate writing).
  - But `trade_summary.txt` and `trade_summary.json` were not created.
  - No final statistics available.
- **Root Cause**
  - Summary files were only generated in `stop()` method, which runs when backtest completes normally.
  - Ctrl+C (SIGINT) or `kill` (SIGTERM) interrupted execution before `stop()` was called.
- **Fix**
  - Added signal handlers in `__init__()`:
    ```python
    import signal
    import sys

    def signal_handler(sig, frame):
        print('\n\n⚠️  Interrupt received! Saving summary...')
        self.save_summary_to_file()
        print('✓ Files saved. Exiting...')
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill command
    ```
  - Created `save_summary_to_file()` method to generate both text and JSON summaries.
  - Called from both `stop()` (normal completion) and signal handlers (interruption).
  - Result: Summary files always generated, even on forced exit.

---

### 16. Strike Not Updating Dynamically (PDF Requirement Violation)

- **Symptoms**
  - Fewer trades than expected.
  - Many entry signals appearing but not being taken.
  - Example: Jan 6th showed 83 entry signals but only 4 trades executed.
  - Strike remained constant throughout the day (e.g., always checking 24000 even when spot moved to 23800).
- **Root Cause**
  - **PDF Strategy Requirement**: *"Keep on Updating CallStrike/PutStrike till entry is found"*
  - **Current Implementation**: Strike was calculated **once at 9:15 AM** in `analyze_market()` and never updated.
  - As spot price moved during the day, the strike became increasingly irrelevant (too far from spot).
  - Entry signals appeared on the static strike, but that strike was no longer "nearest to spot" as required.
- **PDF Strategy Quote**:
  > "If Call (Long Entry)
  > - Choose CallStrike as nearest to Nifty Spot on the upper side (For e.g. if Spot is 25965 choose 26000). **Keep on Updating CallStrike till entry is found**"
  >
  > "If Put (Short Entry)
  > - Choose PutStrike as nearest to Nifty Spot on the lower side (For e.g. if Spot is 25965 choose 25950). **Keep on Updating PutStrike till entry is found**"
- **Fix**
  - Modified `check_entry_conditions()` to update strike dynamically before checking entry:
    ```python
    # ✅ DYNAMIC STRIKE UPDATE - As per PDF requirement
    # Get current spot price (not 9:15 AM spot!)
    spot_price = self.get_spot_price()

    # Get strikes near CURRENT spot
    options_near_spot, selected_strikes = self.params.oi_analyzer.get_strikes_near_spot(
        spot_price=spot_price,  # Current spot, not opening spot
        timestamp=pd.Timestamp(dt),
        expiry_date=self.daily_expiry,
        num_strikes_above=self.params.strikes_above_spot,
        num_strikes_below=self.params.strikes_below_spot
    )

    # Update strike to nearest based on CURRENT spot and direction
    updated_strike = self.params.oi_analyzer.get_nearest_strike(
        spot_price, self.daily_direction, selected_strikes
    )

    # Log when strike changes
    if updated_strike != self.daily_strike:
        self.log(f'📍 STRIKE UPDATED: {self.daily_strike} → {updated_strike} (Spot: {spot_price:.2f})')
        self.daily_strike = updated_strike
    ```
  - Result:
    - Strike now updates every minute based on current spot price.
    - Strategy correctly trades options "nearest to spot" as per PDF.
    - Example logs: `📍 STRIKE UPDATED: 24200 → 24150 (Spot: 24130.85)`
    - Multiple different strikes traded per day (e.g., Jan 6th: PE 24000, 23900, 23750, 23650).
    - More relevant entry opportunities as strike follows market movement.

---

### 17. Strategy Now Fully Aligned with PDF Specification

- **Current State After All Fixes**
  - ✅ Trades are executed and recorded immediately to CSV
  - ✅ All terminal output saved to timestamped log files
  - ✅ Summary files generated on any exit (normal or Ctrl+C)
  - ✅ No duplicate order placement
  - ✅ Strike updates dynamically following spot price (PDF compliant)
  - ✅ Direction determined once per day (PDF compliant)
  - ✅ VWAP anchored to 9:15 AM market open
  - ✅ OI unwinding detection working
  - ✅ Stop loss and trailing stop functioning correctly
  - ✅ Clean position management with no phantom trades

- **Trade Execution Example (Jan 6th with Dynamic Strikes)**
  ```
  [09:39] 📍 Strike: 24000, Entry: PE 24000 @ ₹207.05
  [10:09] 🛑 STOP LOSS HIT, Exit: PE 24000 @ ₹151.30
  [10:33] 📍 STRIKE UPDATED: 24000 → 23900 (Spot moved down)
  [10:34] Entry: PE 23900 @ ₹140.15
  [11:32] Exit: PE 23900 @ ₹245.55 | P&L: ₹105.40 (+75.21%)
  [11:40] 📍 STRIKE UPDATED: 23900 → 23750 (Spot moved down)
  [11:40] Entry: PE 23750 @ ₹186.85
  ```

- **Files Generated Per Run**
  - `reports/trades.csv` - All completed trades with full details
  - `reports/trade_summary.txt` - Human-readable summary statistics
  - `reports/trade_summary.json` - Machine-readable summary
  - `reports/backtest_log_YYYYMMDD_HHMMSS.txt` - Complete terminal output
  - `reports/backtest_metrics.json` - Detailed analytics from reporter

This comprehensive fix log captures the evolution from initial implementation issues through to a fully functional, PDF-compliant strategy with robust logging and data persistence.




