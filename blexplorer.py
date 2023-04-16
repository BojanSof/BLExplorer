import asyncio

import PySimpleGUI as sg

from ble import Ble


class BLExplorerGUI:
    def __init__(self):
        self.ble = Ble()
        self._create_layout()
        self.running = False

    def run(self):
        sg.theme("DarkTeal12")
        self.window = sg.Window(
            "BLExplorer", self.layout, resizable=True, size=(800, 600)
        )
        self.running = True
        while self.running:
            event, values = self.window.read(timeout=20)
            # process event
            self.process_event(event, values)
            # update
            self.update()
        self.window.close()

    def process_event(self, event, values):
        if event == sg.WIN_CLOSED:
            self.running = False
        elif event == "-BLE_SCAN-":
            if self.ble.is_scanning():
                self.ble.stop_scan()
                self.window["-BLE_SCAN-"].update(text="Scan")
            else:
                self.ble.start_scan()
                self.window["-BLE_SCAN-"].update(text="Stop Scanning")

    def update(self):
        if self.ble.has_found_new_device():
            ble_dev_data, _ = self.ble.get_found_devices()
            self.window["-BLE_TABLE_SCAN-"].update(values=ble_dev_data)

    def _create_layout(self):
        font = "MesloLGS NF"
        self.layout_heading = [sg.Text("BLExplorer", font=(font, 48))]
        ble_dev_data, ble_dev_data_cols = self.ble.get_found_devices()
        self.layout_table = [
            sg.Table(
                values=ble_dev_data,
                headings=ble_dev_data_cols,
                justification="center",
                num_rows=5,
                font=(font, 16),
                expand_x=True,
                key="-BLE_TABLE_SCAN-",
            )
        ]
        self.layout_buttons = [sg.Button("Scan", key="-BLE_SCAN-")]
        self.layout = [
            self.layout_heading,
            self.layout_buttons,
            self.layout_table,
        ]


if __name__ == "__main__":
    blexplorer = BLExplorerGUI()
    blexplorer.run()
