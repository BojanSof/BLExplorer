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
            size=(1024, 600),
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
                self.window["-BLE_TABLE_DEVICES-"].update(values=[])
                self.ble.start_scan()
                self.window["-BLE_SCAN-"].update(text="Stop Scanning")

    def update(self):
        # update scan info
        self.update_scan()

    def update_scan(self):
        if self.ble.has_found_device():
            ble_devices = self.ble.get_found_devices()
            ble_dev_data = self.create_ble_table_data(ble_devices)
            self.window["-BLE_TABLE_DEVICES-"].update(values=ble_dev_data)

    def create_ble_table_data(self, ble_devices):
        data = [[dev["name"], dev["address"], dev["rssi"]] for dev in ble_devices]
        return data

    def _create_layout(self):
        font = "Helvetica"
        layout_heading = [
            sg.Image(
                os.path.join("resources", "blexplorer.png"), size=(100, 100)
            ),
            sg.Text("BLExplorer", font=(font, 48)),
        ]
        ble_cntl_buttons = [
            sg.Button("Scan", key="-BLE_SCAN-"),
            sg.Button("Connect", disabled=True, key="-BLE_CONNECT-"),
        ]
        layout_buttons = [
            sg.Frame(
                "Controls",
                [ble_cntl_buttons],
                font=(font, 14),
                expand_x=True,
            )
        ]
        ble_dev_data_cols = ["Name", "Address", "RSSI (dBm)"]
        ble_dev_table = sg.Table(
            values=[],
            headings=ble_dev_data_cols,
            justification="center",
            font=(font, 12),
            num_rows=5,
            expand_x=True,
            row_height=30,
            max_col_width=35,
            col_widths=[15, 15, 9],
            auto_size_columns=False,
            background_color="SteelBlue4",
            alternating_row_color="SteelBlue3",
            key="-BLE_TABLE_DEVICES-",
        )
        ble_adv_info_labels = sg.Column(
            [
                [sg.Text("Local name ", key="-ADV_NAME_LABEL-")],
                [sg.Text("RSSI (dBm)", key="-ADV_RSSI_LABEL-")],
                [sg.Text("Interval (ms)", key="-ADV_INT_LABEL-")],
                [sg.Text("Manufacturer ID", key="-ADV_MFR_ID_LABEL-")],
                [sg.Text("Service UUIDs", key="-ADV_UUIDS_LABEL-")],
            ]
        )
        ble_adv_info_vals = sg.Column(
            [
                [
                    sg.Input(
                        "NAME",
                        readonly=True,
                        size=(15,),
                        key="-ADV_NAME-",
                    )
                ],
                [
                    sg.Input(
                        "RSSI",
                        readonly=True,
                        size=(15,),
                        key="-ADV_RSSI-",
                    )
                ],
                [
                    sg.Input(
                        "ADV INT",
                        readonly=True,
                        size=(15,),
                        key="-ADV_INT-",
                    )
                ],
                [
                    sg.Input(
                        "0xDEAD",
                        readonly=True,
                        size=(15, 1),
                        key="-ADV_MFR_ID-",
                    )
                ],
                [
                    sg.Combo(
                        [""],
                        default_value="",
                        size=(15,),
                        key="-ADV_UUIDS-",
                    )
                ],
            ]
        )
        ble_adv_info_layout = [
            [
                ble_adv_info_labels,
                ble_adv_info_vals,
            ]
        ]
        ble_adv_info_frame = sg.Frame(
            "Advertisement info", ble_adv_info_layout, font=(font, 14)
        )
        layout_advertisement = [
            [
                sg.Column(
                    [[ble_dev_table]], justification="left", expand_x=True
                ),
                sg.Column([[ble_adv_info_frame]], justification="right"),
            ]
        ]
        tabs = [
            sg.Tab(
                f"Dev{i}",
                [[sg.Text(f"Connection {i}")]],
                visible=False,
                key=f"-CONNECTED_DEVICE_{i}-",
            )
            for i in range(1, 6)
        ]
        tab_group = sg.TabGroup(
            [tabs],
            expand_x=True,
            key="-CONN_DEVS_TABS-",
        )
        layout_connections = [
            sg.Frame(
                "Connected devices",
                [
                    [
                        sg.Column(
                            [[tab_group]],
                            visible=False,
                            key="-CONN_DEVS_CONTAINER-",
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
                            key="-NO_CONN_DEVS_CONTAINER-",
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
