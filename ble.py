import asyncio
import enum
import threading
import queue

from bleak import BleakScanner, BleakClient


class ConnectionStatus(enum.Enum):
    Disconnected = enum.auto()
    Connecting = enum.auto()
    Connected = enum.auto()
    Disconnecting = enum.auto()


class Ble:
    def __init__(self):
        self.found_devices = {}
        self.found_device = False
        self.scanning = False
        self.connected_devices = {}
        self.disconnect_events = {}
        self.status_queue = queue.Queue()
        self.status_devices = {}
        self.event_loop = asyncio.new_event_loop()
        self.event_loop_thread = threading.Thread(
            target=self._asyncloop, daemon=True
        )
        self.event_loop_thread.start()

    def __del__(self):
        if self.scanning:
            self.stop_scan()
        self.event_loop_thread.join()

    def start_scan(self):
        # clear previously found devices
        self.found_devices = {}
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

    def has_found_device(self):
        ret_val = self.found_device
        self.found_device = False
        return ret_val

    def get_found_devices(self):
        devices = []
        for address, (
            device,
            advertisement_data,
        ) in self.found_devices.items():
            dev = {
                "name": advertisement_data.local_name,
                "address": address,
                "rssi": advertisement_data.rssi,
                "uuids": advertisement_data.service_uuids,
                "dev": device,
            }
            devices.append(dev)
        return devices

    def connect(self, dev):
        self.status_devices[dev.address] = ConnectionStatus.Connecting
        try:
            self.status_queue.put_nowait(
                (dev.address, ConnectionStatus.Connecting)
            )
        except queue.Full:
            # TODO better handling of this case
            pass
        self.disconnect_events[dev.address] = asyncio.Event()
        asyncio.run_coroutine_threadsafe(
            self.bluetooth_connect(dev, self.disconnect_events[dev.address]),
            self.event_loop,
        )

    def disconnect(self, dev_address):
        self.status_devices[dev_address] = ConnectionStatus.Disconnecting
        try:
            self.status_queue.put_nowait(
                (dev_address, ConnectionStatus.Disconnecting)
            )
        except queue.Full:
            # TODO better handling of this case
            pass
        self.event_loop.call_soon_threadsafe(
            self.disconnect_events[dev_address].set
        )

    def is_connected(self, dev_address):
        return dev_address in self.connected_devices

    def get_status(self, dev_address):
        if dev_address in self.status_devices:
            return self.status_devices[dev_address]
        else:
            return None

    def get_status_event(self):
        try:
            return self.status_queue.get_nowait()
        except queue.Empty:
            return None

    async def bluetooth_scan(self, stop_event):
        async with BleakScanner(
            detection_callback=self._detection_callback,
        ):
            await stop_event.wait()

    def _detection_callback(self, device, advertisement_data):
        if advertisement_data.local_name is not None:
            self.found_devices[device.address] = (
                device,
                advertisement_data,
            )
            self.found_device = True

    async def bluetooth_connect(self, device, disconnect_event):
        async with BleakClient(
            device,
            self._disconnect_callback,
        ) as client:
            self.connected_devices[device.address] = client
            self.status_devices[device.address] = ConnectionStatus.Connected
            try:
                self.status_queue.put_nowait(
                    (device.address, ConnectionStatus.Connected)
                )
            except queue.Full:
                # TODO better handling of this case
                pass
            await disconnect_event.wait()

    def _disconnect_callback(self, client):
        del self.connected_devices[client.address]
        del self.status_devices[client.address]
        try:
            self.status_queue.put_nowait(
                (client.address, ConnectionStatus.Disconnected)
            )
        except queue.Full:
            # TODO better handling of this case
            pass

    def _asyncloop(self):
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_forever()
