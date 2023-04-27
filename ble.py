import asyncio
import enum
import threading
import queue

from bleak import BleakScanner, BleakClient


class BleStatus(enum.Enum):
    Disconnected = enum.auto()
    Connecting = enum.auto()
    Connected = enum.auto()
    Disconnecting = enum.auto()
    WriteSuccessful = enum.auto()
    NotificationsEnabled = enum.auto()
    NotificationsDisabled = enum.auto()


class Ble:
    def __init__(self):
        self.found_devices = {}
        self.found_device = False
        self.scanning = False
        self.connected_devices = {}
        self.disconnect_events = {}
        self.notification_devices = {}
        self.stop_notify_events = {}
        self.status_queue = queue.Queue()
        self.data_queue = queue.Queue()
        self.status_devices = {}
        self.event_loop = asyncio.new_event_loop()
        self.event_loop_thread = threading.Thread(
            target=self._asyncloop, daemon=True
        )
        self.event_loop_thread.start()

    def __del__(self):
        # stop scanning
        if self.scanning:
            self.stop_scan()
        # stop notifications
        for dev_addr, dev_events in self.stop_notify_events.items():
            for char_uuid in dev_events.keys():
                self.stop_notifications_characteristic(dev_addr, char_uuid)
        # disconnect from connected devices
        for dev_addr in self.connected_devices.keys():
            self.disconnect(dev_addr)
        self.event_loop.call_soon_threadsafe(self.event_loop.stop)
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
                "manufacturer_data": advertisement_data.manufacturer_data,
                "dev": device,
            }
            devices.append(dev)
        return devices

    def connect(self, dev):
        self.status_devices[dev.address] = BleStatus.Connecting
        try:
            self.status_queue.put_nowait((dev.address, BleStatus.Connecting))
        except queue.Full:
            # TODO better handling of this case
            pass
        self.disconnect_events[dev.address] = asyncio.Event()
        asyncio.run_coroutine_threadsafe(
            self.bluetooth_connect(dev, self.disconnect_events[dev.address]),
            self.event_loop,
        )

    def disconnect(self, dev_address):
        self.status_devices[dev_address] = BleStatus.Disconnecting
        try:
            self.status_queue.put_nowait((dev_address, BleStatus.Disconnecting))
        except queue.Full:
            # TODO better handling of this case
            pass
        # stop notifications if any
        for dev_addr, dev_events in self.stop_notify_events.items():
            for char_uuid in dev_events.keys():
                self.stop_notifications_characteristic(dev_addr, char_uuid)
        self.event_loop.call_soon_threadsafe(
            self.disconnect_events[dev_address].set
        )

    def is_connected(self, dev_address):
        return dev_address in self.connected_devices

    def get_connected_devices(self):
        return list(self.connected_devices.keys())

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

    def get_data_event(self):
        try:
            return self.data_queue.get_nowait()
        except queue.Empty:
            return None

    def get_services_and_characteristics(self, dev_address):
        if not self.is_connected(dev_address):
            services_collection = None
        else:
            services_collection = {}
            dev = self.connected_devices[dev_address]
            for _, service in dev.services.services.items():
                services_collection[service.uuid] = {
                    "name": service.description,
                    "service": service,
                }
                service_characteristics = {}
                for characteristic in service.characteristics:
                    service_characteristics[characteristic.uuid] = {
                        "name": characteristic.description,
                        "properties": characteristic.properties,
                        "characteristic": characteristic,
                    }
                    characteristic_descriptors = {}
                    for descriptor in characteristic.descriptors:
                        characteristic_descriptors[descriptor.uuid] = {
                            "name": descriptor.description,
                            "descriptor": descriptor,
                        }
                    service_characteristics[characteristic.uuid][
                        "descriptors"
                    ] = characteristic_descriptors
                services_collection[service.uuid][
                    "characteristics"
                ] = service_characteristics
        return services_collection

    def read_characteristic(self, dev_addr, char_uuid):
        if self.is_connected(dev_addr):
            client = self.connected_devices[dev_addr]
            chars = list(client.services.characteristics.values())
            chars_uuids = [char.uuid for char in chars]
            chars_properties = [char.properties for char in chars]
            if char_uuid in chars_uuids:
                i_char = chars_uuids.index(char_uuid)
                if "read" in chars_properties[i_char]:
                    asyncio.run_coroutine_threadsafe(
                        self.bluetooth_read(client, char_uuid), self.event_loop
                    )

    def write_characteristic(self, dev_addr, char_uuid, data):
        if self.is_connected(dev_addr):
            client = self.connected_devices[dev_addr]
            chars = list(client.services.characteristics.values())
            chars_uuids = [char.uuid for char in chars]
            chars_properties = [char.properties for char in chars]
            if char_uuid in chars_uuids:
                i_char = chars_uuids.index(char_uuid)
                if "write" in chars_properties[i_char]:
                    asyncio.run_coroutine_threadsafe(
                        self.bluetooth_write(client, char_uuid, data),
                        self.event_loop,
                    )

    def start_notifications_characteristic(self, dev_addr, char_uuid):
        if self.is_connected(dev_addr):
            client = self.connected_devices[dev_addr]
            chars = list(client.services.characteristics.values())
            chars_uuids = [char.uuid for char in chars]
            chars_properties = [char.properties for char in chars]
            if char_uuid in chars_uuids:
                i_char = chars_uuids.index(char_uuid)
                if "notify" in chars_properties[i_char]:
                    if dev_addr not in self.stop_notify_events:
                        self.stop_notify_events[dev_addr] = {}
                    self.stop_notify_events[dev_addr][
                        char_uuid
                    ] = asyncio.Event()
                    if dev_addr not in self.notification_devices:
                        self.notification_devices[dev_addr] = {}
                    asyncio.run_coroutine_threadsafe(
                        self.bluetooth_notify(
                            client,
                            char_uuid,
                            self.stop_notify_events[dev_addr][char_uuid],
                        ),
                        self.event_loop,
                    )

    def stop_notifications_characteristic(self, dev_addr, char_uuid):
        if (
            dev_addr in self.stop_notify_events.keys()
            and char_uuid in self.stop_notify_events[dev_addr].keys()
        ):
            self.event_loop.call_soon_threadsafe(
                self.stop_notify_events[dev_addr][char_uuid].set
            )

    def are_notifications_enabled(self, dev_addr, char_uuid):
        return (
            dev_addr in self.notification_devices.keys()
            and char_uuid in self.notification_devices[dev_addr].keys()
        )

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
            self.status_devices[device.address] = BleStatus.Connected
            try:
                self.status_queue.put_nowait(
                    (device.address, BleStatus.Connected)
                )
            except queue.Full:
                # TODO better handling of this case
                pass
            await disconnect_event.wait()

    def _disconnect_callback(self, client):
        del self.connected_devices[client.address]
        del self.status_devices[client.address]
        if client.address in self.notification_devices.keys():
            del self.notification_devices[client.address]
        try:
            self.status_queue.put_nowait(
                (client.address, BleStatus.Disconnected)
            )
        except queue.Full:
            # TODO better handling of this case
            pass

    async def bluetooth_read(self, client, uuid):
        data = await client.read_gatt_char(uuid)
        try:
            self.data_queue.put_nowait((client.address, uuid, data))
        except queue.Full:
            # TODO better handling of this case
            pass

    async def bluetooth_write(self, client, uuid, data):
        await client.write_gatt_char(uuid, data)
        try:
            self.status_queue.put_nowait(
                (client.address, BleStatus.WriteSuccessful, uuid)
            )
        except queue.Full:
            # TODO better handling of this case
            pass

    async def bluetooth_notify(self, client, uuid, stop_event):
        await client.start_notify(
            uuid,
            lambda uuid, data: self.bluetooth_notify_callback(
                client, uuid, data
            ),
        )
        self.notification_devices[client.address][uuid] = True
        try:
            self.status_queue.put_nowait(
                (client.address, BleStatus.NotificationsEnabled, uuid)
            )
        except queue.Full:
            # TODO better handling of this case
            pass
        await stop_event.wait()
        await client.stop_notify(uuid)
        del self.notification_devices[client.address]
        try:
            self.status_queue.put_nowait(
                (client.address, BleStatus.NotificationsDisabled, uuid)
            )
        except queue.Full:
            # TODO better handling of this case
            pass

    def bluetooth_notify_callback(self, client, char, data):
        try:
            self.data_queue.put_nowait((client.address, char.uuid, data))
        except queue.Full:
            # TODO better handling of this case
            pass

    def _asyncloop(self):
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_forever()
