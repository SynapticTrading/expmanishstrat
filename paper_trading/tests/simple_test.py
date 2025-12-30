"""
Simple AngelOne Connection Test
Direct test using your credentials - runs exactly as provided
"""

from SmartApi import SmartConnect
import pyotp

# Your credentials
api_key = "GuULp2XA"
username = "N182640"
pwd = "7531"
token = "4CDGR2KJ2Y3ESAYCIAXPYP2JAY"

print("="*80)
print("ANGELONE SMARTAPI - SIMPLE CONNECTION TEST")
print("="*80)

# Initialize SmartConnect
print("\n1. Initializing SmartConnect...")
smartApi = SmartConnect(api_key)
print("   ✓ SmartConnect initialized")

# Generate TOTP
print("\n2. Generating TOTP...")
totp = pyotp.TOTP(token).now()
print(f"   ✓ TOTP generated: {totp}")

# Generate Session
print("\n3. Connecting to AngelOne...")
try:
    data = smartApi.generateSession(username, pwd, totp)
    print("   ✓ Session generated successfully!")
    print(f"\n   Response: {data}")

    # Extract tokens
    authToken = data['data']['jwtToken']
    refreshToken = data['data']['refreshToken']
    feedToken = smartApi.getfeedToken()

    print(f"\n   Auth Token: {authToken[:50]}...")
    print(f"   Refresh Token: {refreshToken[:50]}...")
    print(f"   Feed Token: {feedToken}")

except Exception as e:
    print(f"   ✗ Connection failed: {str(e)}")
    exit(1)

# Get Profile
print("\n4. Fetching user profile...")
try:
    res = smartApi.getProfile(refreshToken)
    print("   ✓ Profile retrieved successfully!")
    print(f"\n   Profile: {res}")
except Exception as e:
    print(f"   ✗ Failed to get profile: {str(e)}")

# Get Historical Data
print("\n5. Fetching historical candle data...")
try:
    historicParam = {
        "exchange": "NSE",
        "symboltoken": "3045",
        "interval": "ONE_MINUTE",
        "fromdate": "2021-02-08 09:00",
        "todate": "2021-02-08 09:16"
    }
    stockData = smartApi.getCandleData(historicParam)
    print("   ✓ Historical data retrieved successfully!")
    print(f"\n   Stock Data: {stockData}")

    # Show number of candles
    if stockData.get('status') and stockData.get('data'):
        print(f"\n   Number of candles: {len(stockData['data'])}")
        if len(stockData['data']) > 0:
            print(f"   First candle: {stockData['data'][0]}")

except Exception as e:
    print(f"   ✗ Failed to get candle data: {str(e)}")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
