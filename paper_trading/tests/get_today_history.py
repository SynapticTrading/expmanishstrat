"""
Get complete history from AngelOne for today:
- All orders (pending, completed, cancelled, rejected)
- All positions (open and closed)
- All trades (executed)
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter
from paper_trading.core.contract_manager import ContractManager

def load_credentials():
    """Load AngelOne credentials."""
    creds_file = Path(__file__).parent.parent / "config" / "credentials_angelone.txt"

    credentials = {}
    with open(creds_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                credentials[key.strip()] = value.strip()

    return {
        'api_key': credentials.get('api_key'),
        'username': credentials.get('username'),
        'password': credentials.get('password'),
        'totp_token': credentials.get('totp_token')
    }

def main():
    print("="*80)
    print("ANGELONE HISTORY - TODAY")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("="*80)

    # Load credentials
    credentials = load_credentials()

    # Initialize adapter
    contract_manager = ContractManager()
    adapter = AngelOneAdapter(credentials, contract_manager)

    # Connect (this might take 10-30 seconds)
    print("\nConnecting to AngelOne (please wait 10-30 seconds)...")
    if not adapter.connect():
        print("❌ Failed to connect to AngelOne")
        return

    print("✅ Connected successfully\n")

    # ============================================================================
    # 1. ORDER BOOK - All orders from today
    # ============================================================================
    print("="*80)
    print("ORDER BOOK - ALL ORDERS")
    print("="*80)

    try:
        order_book = adapter._smart_api.orderBook()

        if order_book and order_book.get('status'):
            orders = order_book.get('data', [])

            if orders:
                print(f"\nFound {len(orders)} order(s):\n")

                # Group by status
                statuses = {}
                for order in orders:
                    status = order.get('orderstatus', 'unknown')
                    if status not in statuses:
                        statuses[status] = []
                    statuses[status].append(order)

                # Print summary
                print("Summary by status:")
                for status, order_list in statuses.items():
                    print(f"  {status.upper()}: {len(order_list)}")
                print()

                # Print detailed list
                for i, order in enumerate(orders, 1):
                    print(f"\n{i}. Order ID: {order.get('orderid')}")
                    print(f"   Symbol: {order.get('tradingsymbol')}")
                    print(f"   Transaction: {order.get('transactiontype')}")
                    print(f"   Order Type: {order.get('ordertype')}")
                    print(f"   Product: {order.get('producttype')}")
                    print(f"   Status: {order.get('orderstatus')}")
                    print(f"   Quantity: {order.get('quantity')} (Filled: {order.get('filledshares', 0)})")
                    print(f"   Price: ₹{order.get('price', 0)}")
                    if order.get('triggerprice'):
                        print(f"   Trigger Price: ₹{order.get('triggerprice')}")
                    if order.get('averageprice'):
                        print(f"   Average Price: ₹{order.get('averageprice')}")
                    print(f"   Order Time: {order.get('ordertime', 'N/A')}")
                    print(f"   Update Time: {order.get('updatetime', 'N/A')}")
                    if order.get('text'):
                        print(f"   Message: {order.get('text')}")

                # Show pending orders that can be cancelled
                pending_orders = [
                    o for o in orders
                    if o.get('orderstatus') in ['open', 'pending', 'trigger pending']
                ]

                if pending_orders:
                    print("\n" + "="*80)
                    print(f"⚠️  {len(pending_orders)} PENDING ORDER(S) FOUND")
                    print("="*80)
                    for order in pending_orders:
                        print(f"  Order ID: {order.get('orderid')} - {order.get('tradingsymbol')} - Status: {order.get('orderstatus')}")

                    print("\n" + "="*80)
                    cancel = input("Do you want to CANCEL all pending orders? (yes/no): ").strip().lower()

                    if cancel == 'yes':
                        print("\nCancelling orders...")
                        for order in pending_orders:
                            order_id = order.get('orderid')
                            variety = order.get('variety', 'NORMAL')
                            try:
                                # Cancel using smart API directly
                                result = adapter._smart_api.cancelOrder(order_id, variety)
                                if result and result.get('status'):
                                    print(f"✅ Cancelled order {order_id}")
                                else:
                                    print(f"❌ Failed to cancel {order_id}: {result.get('message', 'Unknown error')}")
                            except Exception as e:
                                print(f"❌ Error cancelling {order_id}: {e}")
                        print("\n✅ Cancellation complete")

            else:
                print("\n✅ No orders today\n")
        else:
            print("\n❌ Could not fetch order book\n")

    except Exception as e:
        print(f"\n❌ Error getting order book: {e}\n")

    # ============================================================================
    # 2. POSITIONS - All positions
    # ============================================================================
    print("\n" + "="*80)
    print("POSITIONS")
    print("="*80)

    try:
        positions = adapter.get_positions()

        if positions:
            print(f"\nFound {len(positions)} position(s):\n")
            total_pnl = 0
            for i, pos in enumerate(positions, 1):
                print(f"{i}. Symbol: {pos.symbol}")
                print(f"   Quantity: {pos.quantity}")
                print(f"   Product: {pos.product_type.value if hasattr(pos.product_type, 'value') else pos.product_type}")
                print(f"   Average Price: ₹{pos.average_price:.2f}")
                print(f"   LTP: ₹{pos.ltp:.2f}")
                print(f"   P&L: ₹{pos.pnl:.2f}")
                total_pnl += pos.pnl
                print()

            print(f"Total P&L: ₹{total_pnl:.2f}")
        else:
            print("\n✅ No open positions\n")

    except Exception as e:
        print(f"\n❌ Error getting positions: {e}\n")

    # ============================================================================
    # 3. TRADE BOOK - All executed trades
    # ============================================================================
    print("\n" + "="*80)
    print("TRADE BOOK - EXECUTED TRADES")
    print("="*80)

    try:
        trade_book = adapter._smart_api.tradeBook()

        if trade_book and trade_book.get('status'):
            trades = trade_book.get('data', [])

            if trades:
                print(f"\nFound {len(trades)} executed trade(s):\n")

                total_buy_value = 0
                total_sell_value = 0

                for i, trade in enumerate(trades, 1):
                    trans_type = trade.get('transactiontype', '')
                    quantity = int(trade.get('quantity', 0))
                    price = float(trade.get('price', 0))
                    value = quantity * price

                    print(f"{i}. Trade ID: {trade.get('tradeid')}")
                    print(f"   Order ID: {trade.get('orderid')}")
                    print(f"   Symbol: {trade.get('tradingsymbol')}")
                    print(f"   Transaction: {trans_type}")
                    print(f"   Quantity: {quantity}")
                    print(f"   Price: ₹{price:.2f}")
                    print(f"   Value: ₹{value:.2f}")
                    print(f"   Time: {trade.get('filltime', 'N/A')}")
                    print()

                    if trans_type == 'BUY':
                        total_buy_value += value
                    elif trans_type == 'SELL':
                        total_sell_value += value

                print(f"Total BUY value: ₹{total_buy_value:.2f}")
                print(f"Total SELL value: ₹{total_sell_value:.2f}")
                print(f"Net: ₹{total_sell_value - total_buy_value:.2f}")

            else:
                print("\n✅ No trades executed today\n")
        else:
            print("\n❌ Could not fetch trade book\n")

    except Exception as e:
        print(f"\n❌ Error getting trade book: {e}\n")

    # Disconnect
    print("\n" + "="*80)
    adapter.disconnect()
    print("Disconnected from AngelOne")
    print("="*80)

if __name__ == "__main__":
    main()
