import asyncio

from bleak import BleakScanner

found_devices = {}


def detection_callback(device, advertisement_data):
    global found_devices
    found_devices[device.address] = (device, advertisement_data)
    print(f"New BLE device or ADV update: {device.address}")


async def bluetooth_scan(stop_event):
    async with BleakScanner(detection_callback) as scanner:
        await stop_event.wait()
        data = scanner.discovered_devices_and_advertisement_data


async def main():
    scanner_stop_event = asyncio.Event()
    ble_scanner_task = asyncio.create_task(bluetooth_scan(scanner_stop_event))
    await asyncio.sleep(5)
    scanner_stop_event.set()
    await ble_scanner_task


if __name__ == "__main__":
    print("Starting main event loop")
    asyncio.run(main())
    print(f"Found {len(found_devices)} devices")
    # print found devices
    for addr in found_devices:
        dev = found_devices[addr][0]
        print(f"Device address: {dev.address} | Device name: {dev.name}")
