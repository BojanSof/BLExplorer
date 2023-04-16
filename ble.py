import asyncio
import threading

from bleak import BleakScanner


class Ble:
    def __init__(self):
        self.found_devices = {}
        self.found_new_device = False
        self.scanning = False
        self.event_loop = asyncio.new_event_loop()
        self.event_loop_thread = threading.Thread(
            target=self._asyncloop, daemon=True
        )
        self.event_loop_thread.start()
        self.found_new_device_lock = threading.Lock()

    def __del__(self):
        if self.scanning:
            self.stop_scan()
        self.event_loop_thread.join()

    def start_scan(self):
        self.scan_stop_event = asyncio.Event()
        asyncio.run_coroutine_threadsafe(
            self.bluetooth_scan(self.scan_stop_event), self.event_loop
        )
        self.scanning = True

    def stop_scan(self):
        if self.scanning:
            self.event_loop.call_soon_threadsafe(self.scan_stop_event.set)
            self.scanning = False
    
    def is_scanning(self):
        return self.scanning
    
    def has_found_new_device(self):
        ret_val = self.found_new_device
        return ret_val

    def get_found_devices(self):
        columns_names = ["Name", "Address", "RSSI"]
        columns = []
        for address, (device, advertisement_data) in self.found_devices.items():
            columns.append([device.name, address, advertisement_data.rssi])
        return columns, columns_names

    async def bluetooth_scan(self, stop_event):
        async with BleakScanner(
            detection_callback=self._detection_callback
        ) as scanner:
            await stop_event.wait()

    def _detection_callback(self, device, advertisement_data):
        self.found_devices[device.address] = (device, advertisement_data)
        self.found_new_device = True
    
    def _asyncloop(self):
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_forever()
