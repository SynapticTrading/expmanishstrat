"""
Quick script to check for open positions and pending orders in AngelOne
"""

import sys
from pathlib import Path

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
    print("CHECKING ANGELONE POSITIONS AND ORDERS")
    print("="*80)

    # Load credentials
    credentials = load_credentials()

    # Initialize adapter
    contract_manager = ContractManager()
    adapter = AngelOneAdapter(credentials, contract_manager)

    # Connect
    print("\nConnecting to AngelOne...")
    if not adapter.connect():
        print("❌ Failed to connect to AngelOne")
        return

    print("✅ Connected successfully\n")

    # Check positions
    print("="*80)
    print("OPEN POSITIONS")
    print("="*80)

    try:
        positions = adapter.get_positions()
        if positions:
            print(f"\nFound {len(positions)} position(s):\n")
            for i, pos in enumerate(positions, 1):
                print(f"{i}. Symbol: {pos.symbol}")
                print(f"   Quantity: {pos.quantity}")
                print(f"   Product: {pos.product_type}")
                print(f"   P&L: ₹{pos.pnl:.2f}")
                print()
        else:
            print("\n✅ No open positions\n")
    except Exception as e:
        print(f"\n❌ Error getting positions: {e}\n")

    # Check orders
    print("="*80)
    print("PENDING ORDERS")
    print("="*80)

    try:
        # Get order book directly from smart API
        order_book = adapter._smart_api.orderBook()

        if order_book and order_book.get('status'):
            orders = order_book.get('data') or []

            # Filter for pending/open orders
            pending_orders = [
                o for o in orders
                if o.get('orderstatus') in ['open', 'pending', 'trigger pending']
            ]

            if pending_orders:
                print(f"\n⚠️  Found {len(pending_orders)} pending order(s):\n")
                for i, order in enumerate(pending_orders, 1):
                    print(f"{i}. Order ID: {order.get('orderid')}")
                    print(f"   Symbol: {order.get('tradingsymbol')}")
                    print(f"   Type: {order.get('ordertype')}")
                    print(f"   Status: {order.get('orderstatus')}")
                    print(f"   Quantity: {order.get('quantity')}")
                    print(f"   Price: ₹{order.get('price', 0)}")
                    if order.get('triggerprice'):
                        print(f"   Trigger: ₹{order.get('triggerprice')}")
                    print()

                # Ask if user wants to cancel
                print("="*80)
                cancel = input("Do you want to CANCEL all pending orders? (yes/no): ").strip().lower()

                if cancel == 'yes':
                    print("\nCancelling orders...")
                    for order in pending_orders:
                        order_id = order.get('orderid')
                        try:
                            result = adapter.cancel_order(order_id)
                            if result.success:
                                print(f"✅ Cancelled order {order_id}")
                            else:
                                print(f"❌ Failed to cancel {order_id}: {result.message}")
                        except Exception as e:
                            print(f"❌ Error cancelling {order_id}: {e}")
                    print("\n✅ Done")
                else:
                    print("\n⚠️  Orders remain pending. Cancel manually if needed.")
            else:
                print("\n✅ No pending orders\n")
        else:
            print("\n❌ Could not fetch order book\n")

    except Exception as e:
        print(f"\n❌ Error getting orders: {e}\n")

    # Disconnect
    print("="*80)
    adapter.disconnect()
    print("Disconnected from AngelOne")
    print("="*80)

if __name__ == "__main__":
    main()
