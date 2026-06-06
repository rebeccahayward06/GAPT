import asyncio
from bleak import BleakScanner

async def run():
    print("Scanning for Xsens DOT...")
    devices = await BleakScanner.discover()
    for d in devices:
        if d.name and "DOT" in d.name:
            print(f"FOUND: {d.name} | ADDRESS: {d.address}")

if __name__ == "__main__":
    asyncio.run(run())