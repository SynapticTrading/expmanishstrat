"""
Quick script to close open positions
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from paper_trading.brokers.adapter.plugins.angelone import AngelOneAdapter
from paper_trading.core.contract_manager import ContractManager
from paper_trading.brokers.adapter.types import (
    OrderRequest, TransactionType, Exchange, ProductType, OrderType
)

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
    print("CLOSE OPEN POSITIONS")
    print("="*80)

    # Load credentials
    credentials = load_credentials()

    # Initialize
    contract_manager = ContractManager()
    adapter = AngelOneAdapter(credentials, contract_manager)

    # Connect
    print("\nConnecting to AngelOne...")
    if not adapter.connect():
        print("❌ Failed to connect")
        return

    print("✅ Connected\n")

    # Get positions
    print("="*80)
    print("CHECKING POSITIONS")
    print("="*80)

    try:
        # Get positions directly from smart API
        positions_data = adapter._smart_api.position()

        if positions_data and positions_data.get('status'):
            positions = positions_data.get('data', [])

            if not positions:
                print("\n✅ No open positions\n")
                adapter.disconnect()
                return

            print(f"\nFound {len(positions)} position(s):\n")

            for i, pos in enumerate(positions, 1):
                symbol = pos.get('tradingsymbol', '')
                qty = int(pos.get('netqty', 0))

                if qty == 0:
                    continue

                print(f"{i}. Symbol: {symbol}")
                print(f"   Net Qty: {qty}")
                print(f"   Product: {pos.get('producttype', '')}")
                print(f"   LTP: ₹{pos.get('ltp', 0)}")
                print(f"   P&L: ₹{pos.get('pnl', 0)}")
                print()

                # Ask to close
                print("="*80)
                response = input(f"Close this position? (yes/no): ").strip().lower()

                if response == 'yes':
                    print(f"\nClosing position for {symbol}...")

                    # Determine transaction type (opposite of current position)
                    if qty > 0:
                        trans_type = TransactionType.SELL  # Close long
                        order_qty = qty
                    else:
                        trans_type = TransactionType.BUY  # Close short
                        order_qty = abs(qty)

                    # Get token and expiry
                    token = pos.get('symboltoken')

                    # Parse symbol to get strike and option type
                    # Format: NIFTY10FEB2627500CE
                    if 'CE' in symbol:
                        option_type = 'CE'
                    elif 'PE' in symbol:
                        option_type = 'PE'
                    else:
                        print(f"❌ Cannot determine option type from {symbol}")
                        continue

                    # Extract strike from symbol (last 5 digits before CE/PE)
                    try:
                        if option_type == 'CE':
                            strike_str = symbol.split('CE')[0][-5:]
                        else:
                            strike_str = symbol.split('PE')[0][-5:]
                        strike = int(strike_str)
                    except:
                        print(f"❌ Cannot parse strike from {symbol}")
                        continue

                    # Get expiry from contract manager
                    expiry = contract_manager.get_options_expiry('current_week')

                    print(f"\nPlacing MARKET {trans_type.value} order:")
                    print(f"  Symbol: {symbol}")
                    print(f"  Strike: {strike}")
                    print(f"  Option Type: {option_type}")
                    print(f"  Expiry: {expiry}")
                    print(f"  Quantity: {order_qty}")
                    print(f"  Token: {token}")

                    # Place market order to close
                    order_request = OrderRequest(
                        underlying='NIFTY',
                        option_type=option_type,
                        strike=strike,
                        expiry=expiry,
                        exchange=Exchange.NFO,
                        transaction_type=trans_type,
                        order_type=OrderType.MARKET,
                        quantity=order_qty,
                        product_type=ProductType.INTRADAY,
                        tag='close_position'
                    )

                    response = adapter.place_order(order_request)

                    if response.success:
                        print(f"\n✅ ORDER PLACED SUCCESSFULLY!")
                        print(f"   Order ID: {response.order_id}")
                        print(f"   Position should be closed now")
                    else:
                        print(f"\n❌ ORDER FAILED!")
                        print(f"   Error: {response.message}")
                else:
                    print("Skipping...\n")

        else:
            print("\n❌ Could not fetch positions\n")

    except Exception as e:
        print(f"\n❌ Error: {e}\n")

    # Disconnect
    print("\n" + "="*80)
    adapter.disconnect()
    print("Disconnected from AngelOne")
    print("="*80)

if __name__ == "__main__":
    main()
