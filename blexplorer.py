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
            icon=os.path.join("resources", "blexplorer.ico"),
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
            self.window["-BLE_TABLE_DEVICES-"].update(values=ble_dev_data)

    def _create_layout(self):
        font = "Helvetica"
        layout_heading = [
            sg.Image(
                os.path.join("resources", "blexplorer.png"), size=(100, 100)
            ),
            sg.Text("BLExplorer", font=(font, 48)),
        ]
        layout_buttons = [
            sg.Frame(
                "Controls",
                [
                    [
                        sg.Button("Scan", key="-BLE_SCAN-"),
                        sg.Button(
                            "Connect", disabled=True, key="-BLE_CONNECT-"
                        ),
                    ],
                ],
                font=(font, 14),
                expand_x=True,
            )
        ]
        ble_dev_data, ble_dev_data_cols = self.ble.get_found_devices()
        ble_dev_table = sg.Table(
            values=ble_dev_data,
            headings=ble_dev_data_cols,
            justification="center",
            font=(font, 12),
            num_rows=5,
            expand_x=True,
            row_height=20,
            max_col_width=25,
            background_color="SteelBlue4",
            alternating_row_color="SteelBlue3",
            key="-BLE_TABLE_DEVICES-",
        )
        ble_adv_info = [
            [sg.Text("ADV INFO 1                                 ")],
            [sg.Text("ADV INFO 2                                 ")],
            [sg.Text("ADV INFO 3                                 ")],
        ]
        ble_adv_info_layout = sg.Frame(
            "Advertisement info", ble_adv_info, font=(font, 14)
        )
        layout_advertisement = [
            [
                sg.Column(
                    [[ble_dev_table]], justification="left", expand_x=True
                ),
                sg.Column([[ble_adv_info_layout]], justification="right"),
            ]
        ]
        layout_connections = [
            sg.Frame(
                "Connected devices",
                [
                    [
                        sg.Column(
                            [
                                [
                                    sg.TabGroup(
                                        [
                                            [
                                                sg.Tab(
                                                    "Dev1",
                                                    [[sg.Text("Connection 1")]],
                                                    visible=False,
                                                    key="-CONNECTED_DEVICE_1-",
                                                ),
                                                sg.Tab(
                                                    "Dev2",
                                                    [[sg.Text("Connection 2")]],
                                                    visible=False,
                                                    key="-CONNECTED_DEVICE_2-",
                                                ),
                                                sg.Tab(
                                                    "Dev3",
                                                    [[sg.Text("Connection 3")]],
                                                    visible=False,
                                                    key="-CONNECTED_DEVICE_3-",
                                                ),
                                                sg.Tab(
                                                    "Dev4",
                                                    [[sg.Text("Connection 4")]],
                                                    visible=False,
                                                    key="-CONNECTED_DEVICE_4-",
                                                ),
                                                sg.Tab(
                                                    "Dev5",
                                                    [[sg.Text("Connection 5")]],
                                                    visible=False,
                                                    key="-CONNECTED_DEVICE_5-",
                                                ),
                                            ]
                                        ],
                                        expand_x=True,
                                        key="-CONNECTED_DEVICES_TABS-",
                                    )
                                ]
                            ],
                            visible=False,
                            key="-CONNECTED_DEVICES_CONTAINER-",
                        )
                    ],
                    [
                        sg.Column(
                            [
                                [
                                    sg.Text(
                                        "\n\nNo connected devices\n\n",
                                        text_color="gray70",
                                    )
                                ]
                            ],
                            justification="center",
                            key="-NO_CONNECTED_DEVICES-",
                        )
                    ],
                ],
                expand_x=True,
                font=(font, 14),
            )
        ]
        layout = [
            layout_heading,
            layout_buttons,
            layout_advertisement,
            layout_connections,
        ]
        return layout


if __name__ == "__main__":
    blexplorer = BLExplorerGUI()
    blexplorer.run()
