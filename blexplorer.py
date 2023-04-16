import asyncio
import os

import PySimpleGUI as sg

from ble import Ble


class BLExplorerGUI:
    def __init__(self):
        self.ble = Ble()
        sg.theme("DarkTeal12")
        self.layout = self._create_layout()
        self.running = False

    def run(self):
        self.window = sg.Window(
            "BLExplorer",
            self.layout,
            resizable=True,
            size=(800, 600),
            font=("Helvetica", 12),
            icon=os.path.join("resources", "blexplorer.ico")
        )
        self.running = True
        while self.running:
            event, values = self.window.read(timeout=20)
            # process event
            self.process_event(event, values)
            if not self.running:
                break
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
        font = "Helvetica"
        layout_heading = [
            sg.Image(os.path.join("resources", "blexplorer.png"), size=(100,100)),
            sg.Text("BLExplorer", font=(font, 48))
        ]
        ble_dev_data, ble_dev_data_cols = self.ble.get_found_devices()
        layout_table = [
            sg.Table(
                values=ble_dev_data,
                headings=ble_dev_data_cols,
                justification="center",
                num_rows=5,
                font=(font, 16),
                expand_x=True,
                background_color="SteelBlue4",
                alternating_row_color="SteelBlue3",
                key="-BLE_TABLE_SCAN-",
            )
        ]
        layout_buttons = [
            sg.Frame(
                "Controls",
                [[sg.Button("Scan", key="-BLE_SCAN-")]],
                expand_x=True,
            )
        ]
        layout_tabs = [
            sg.TabGroup(
                [
                    [
                        sg.Tab("Advertisement Info", [[sg.Text("Advertisement")]]),
                        sg.Tab("Connection info", [[sg.Text("Connection")]]),
                    ]
                ],
                expand_x=True
            )
        ]
        layout = [
            layout_heading,
            layout_buttons,
            layout_table,
            layout_tabs,
        ]
        return layout


if __name__ == "__main__":
    blexplorer = BLExplorerGUI()
    blexplorer.run()
