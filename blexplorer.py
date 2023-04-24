import os

import PySimpleGUI as sg

from ble import Ble, ConnectionStatus


MAX_NUM_DEVICES = 2  # maximum number of connected devices
MAX_NUM_SERVICES = 3  # maximum number of services per device
MAX_NUM_CHARACTERISTICS = 3  # maximum number of characteristics per service


class BLExplorerGUI:
    def __init__(self):
        self.ble = Ble()
        sg.theme("DarkTeal12")
        self.layout = self._create_layout()
        self.running = False
        self.i_selected_dev = None

    def run(self):
        self.window = sg.Window(
            "BLExplorer",
            self.layout,
            resizable=True,
            size=(1024, 700),
            font=("Helvetica", 12),
            icon=os.path.join("resources", "blexplorer.ico"),
        )
        self.running = True
        while self.running:
            event, values = self.window.read(timeout=100)
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
                self.clear_scan_data()
                self.ble.start_scan()
                self.window["-BLE_SCAN-"].update(text="Stop Scanning")
        elif event == "-BLE_TABLE_DEVICES-":
            if len(values[event]) > 0:
                self.i_selected_dev = values[event][0]
                self.update_advertisement_info()
                ble_devices = self.ble.get_found_devices()
                ble_selected_dev_status = self.ble.get_status(
                    ble_devices[self.i_selected_dev]["address"]
                )
                if ble_selected_dev_status is not None:
                    if ble_selected_dev_status == ConnectionStatus.Connecting:
                        self.window["-BLE_CONNECT-"].update(
                            text="Connect", disabled=True
                        )
                    elif (
                        ble_selected_dev_status
                        == ConnectionStatus.Disconnecting
                    ):
                        self.window["-BLE_CONNECT-"].update(
                            text="Disconnect", disabled=True
                        )
                    elif ble_selected_dev_status == ConnectionStatus.Connected:
                        self.window["-BLE_CONNECT-"].update(
                            text="Disconnect", disabled=False
                        )
                else:
                    self.window["-BLE_CONNECT-"].update(
                        text="Connect", disabled=False
                    )
        elif event == "-BLE_CONNECT-":
            if self.i_selected_dev is not None:
                ble_devices = self.ble.get_found_devices()
                ble_selected_dev = ble_devices[self.i_selected_dev]
                if self.ble.is_connected(ble_selected_dev["address"]):
                    self.ble.disconnect(ble_selected_dev["address"])
                else:
                    self.ble.connect(ble_selected_dev["dev"])
                self.window["-BLE_CONNECT-"].update(disabled=True)
        elif "EXPAND" in event:
            section_key = event.split("--")[0] + "-"
            section_expand_key = event.split("--")[0] + "--EXPAND_BUTTON-"
            self.window[section_key].update(
                visible=not self.window[section_key].visible
            )
            self.window[section_expand_key].update(
                self.window[section_key].metadata[0]
                if self.window[section_key].visible
                else self.window[section_key].metadata[1]
            )
            # update scrollable section
            dev_num = section_key.split("$")[1].split(",")[0]
            dev_tab_section = f"-DEV${dev_num}$_CONTAINER-"
            self.window.refresh()
            self.window[dev_tab_section].contents_changed()


    def update(self):
        # update scan info
        self.update_scan()
        self.update_connections()

    def update_scan(self):
        if self.ble.has_found_device():
            ble_devices = self.ble.get_found_devices()
            ble_dev_data = self.create_ble_table_data(ble_devices)
            # workaround not to fire event when updating table
            # taken from: https://github.com/PySimpleGUI/PySimpleGUI/issues/5129
            # ############## Workaround ######################
            table = self.window["-BLE_TABLE_DEVICES-"]
            table_widget = table.Widget
            table_widget.unbind("<<TreeviewSelect>>")
            # ############# End of Workaround ################
            select_rows = None
            if self.i_selected_dev is not None:
                select_rows = [self.i_selected_dev]
            self.window["-BLE_TABLE_DEVICES-"].update(
                values=ble_dev_data, select_rows=select_rows
            )
            # ############## Workaround ######################
            selections = table_widget.selection()
            table.SelectedRows = [int(x) - 1 for x in selections]
            self.window.refresh()
            table_widget.bind("<<TreeviewSelect>>", table._treeview_selected)
            # ############# End of Workaround ################
            self.update_advertisement_info()

    def update_advertisement_info(self):
        if self.i_selected_dev is not None:
            dev = self.ble.get_found_devices()[self.i_selected_dev]
            self.window["-ADV_NAME-"].update(value=dev["name"])
            self.window["-ADV_RSSI-"].update(value=f"{dev['rssi']}")
            if len(dev["uuids"]) > 0:
                old_uuid_val = self.window["-ADV_UUIDS-"].get()
                new_uuid_val = dev["uuids"][0]
                if old_uuid_val in dev["uuids"]:
                    new_uuid_val = old_uuid_val
                self.window["-ADV_UUIDS-"].update(
                    values=dev["uuids"], value=new_uuid_val
                )
            else:
                self.window["-ADV_UUIDS-"].update(values=[])

    def update_connections(self):
        status = self.ble.get_status_event()
        if status is not None and self.i_selected_dev is not None:
            status_address, connection_status = status
            ble_devices = self.ble.get_found_devices()
            ble_selected_dev_addr = ble_devices[self.i_selected_dev]["address"]
            if status_address == ble_selected_dev_addr:
                if connection_status == ConnectionStatus.Connected:
                    if self.ble.is_connected(ble_selected_dev_addr):
                        self.window["-BLE_CONNECT-"].update(
                            text="Disconnect", disabled=False
                        )
                elif connection_status == ConnectionStatus.Disconnected:
                    self.window["-BLE_CONNECT-"].update(
                        text="Connect", disabled=False
                    )

    def clear_scan_data(self):
        self.i_selected_dev = None
        self.window["-BLE_TABLE_DEVICES-"].update(values=[])
        self.window["-ADV_NAME-"].update(value="")
        self.window["-ADV_RSSI-"].update(value="")
        self.window["-ADV_UUIDS-"].update(values=[""], value="")
        self.window["-ADV_MFR_ID-"].update(value="")

    def create_ble_table_data(self, ble_devices):
        data = [
            [dev["name"], dev["address"], dev["rssi"]] for dev in ble_devices
        ]
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
            row_height=25,
            max_col_width=35,
            col_widths=[15, 15, 9],
            auto_size_columns=False,
            background_color="SteelBlue4",
            enable_events=True,
            key="-BLE_TABLE_DEVICES-",
        )
        ble_adv_info_labels = sg.Column(
            [
                [sg.Text("Local name ", key="-ADV_NAME_LABEL-")],
                [sg.Text("RSSI (dBm)", key="-ADV_RSSI_LABEL-")],
                [sg.Text("Manufacturer ID", key="-ADV_MFR_ID_LABEL-")],
                [sg.Text("Service UUIDs", key="-ADV_UUIDS_LABEL-")],
            ]
        )
        ble_adv_info_vals = sg.Column(
            [
                [
                    sg.Input(
                        "",
                        readonly=True,
                        size=(15,),
                        key="-ADV_NAME-",
                    )
                ],
                [
                    sg.Input(
                        "",
                        readonly=True,
                        size=(15,),
                        key="-ADV_RSSI-",
                    )
                ],
                [
                    sg.Input(
                        "",
                        readonly=True,
                        size=(15, 1),
                        key="-ADV_MFR_ID-",
                    )
                ],
                [
                    sg.Combo(
                        [""],
                        default_value="",
                        readonly=True,
                        size=(33,),
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
                [
                    [
                        sg.Column(
                            [
                                [
                                    self._create_service_layout(
                                        f"-SERVICE${i},{j}$-"
                                    )
                                ]
                                for j in range(1, MAX_NUM_SERVICES + 1)
                            ],
                            scrollable=True,
                            vertical_scroll_only=True,
                            expand_x=True,
                            expand_y=True,
                            key=f"-DEV${i}$_CONTAINER-"
                        )
                    ]
                ],
                expand_x=True,
                expand_y=True,
                visible=True,
                key=f"-CONNECTED_DEVICE_{i}-",
            )
            for i in range(1, MAX_NUM_DEVICES + 1)
        ]
        tab_group = sg.TabGroup(
            [tabs],
            expand_x=True,
            expand_y=True,
            key="-CONN_DEVS_TABS-",
        )
        layout_connections = [
            sg.Frame(
                "Connected devices",
                [
                    [
                        sg.Column(
                            [[tab_group]],
                            expand_x=True,
                            expand_y=True,
                            visible=True,
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
                            visible=False,
                            key="-NO_CONN_DEVS_CONTAINER-",
                        )
                    ],
                ],
                expand_x=True,
                expand_y=True,
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

    def _create_service_layout(
        self, key, section_arrows=(sg.SYMBOL_DOWN, sg.SYMBOL_UP)
    ):
        service_layout = [
            [
                sg.Frame(
                    "",
                    [
                        [
                            self._create_characteristics_layout(
                                key + f"CHARACTERISTIC{i}-", section_arrows
                            )
                        ]
                    ],
                    border_width=1,
                    expand_x=True,
                    expand_y=True,
                )
            ]
            for i in range(1, MAX_NUM_CHARACTERISTICS + 1)
        ]
        service_section = sg.Frame(
            "",
            [
                [
                    sg.Text(
                        (section_arrows[1]),
                        enable_events=True,
                        k=key + "-EXPAND_BUTTON-",
                    ),
                    sg.Text(
                        "Service",
                        enable_events=True,
                        key=key + "-EXPAND_TITLE-",
                    ),
                ],
                [
                    sg.pin(
                        sg.Column(
                            service_layout,
                            metadata=section_arrows,
                            expand_x=True,
                            expand_y=True,
                            visible=False,
                            key=key,
                        )
                    )
                ],
            ],
            border_width=2,
            expand_x=True,
            expand_y=True,
        )
        return service_section

    def _create_characteristics_layout(
        self, key, section_arrows=(sg.SYMBOL_DOWN, sg.SYMBOL_UP)
    ):
        characteristic_labels = sg.Column(
            [
                [sg.Text("UUID", key=key + "-UUID_LABEL-")],
                [sg.Text("Properties", key=key + "-PROPERTIES_LABEL-")],
                [sg.Text("Value", key=key + "-VALUE_LABEL-")],
                [sg.Text("Descriptors", key=key + "-DESCRIPTORS_LABEL-")],
            ]
        )
        characteristic_vals = sg.Column(
            [
                [
                    sg.Input(
                        "",
                        readonly=True,
                        size=(15,),
                        key=key + "-UUID-",
                    )
                ],
                [
                    sg.Input(
                        "",
                        readonly=True,
                        size=(15,),
                        key=key + "-PROPERTIES-",
                    )
                ],
                [
                    sg.Input(
                        "",
                        readonly=True,
                        size=(15,),
                        key=key + "-VALUE-",
                    )
                ],
                [
                    sg.Combo(
                        [""],
                        default_value="",
                        readonly=True,
                        size=(15,),
                        key=key + "-DESCRIPTORS-",
                    )
                ],
            ]
        )
        characteristic_layout = [[characteristic_labels, characteristic_vals]]
        characteristic_buttons = sg.Column(
            [
                [
                    sg.Button("↓", key=key + "-READ-"),
                    sg.Button("↑", key=key + "-WRITE-"),
                    sg.Button("↑↓", key=key + "-INDICATE-"),
                    sg.Button("↓↓", key=key + "-NOTIFY-"),
                ]
            ],
            element_justification="right",
            pad=((50, 0), (0, 0)),
        )
        characteristic_section = sg.Column(
            [
                [
                    sg.Text(
                        (section_arrows[1]),
                        enable_events=True,
                        k=key + "-EXPAND_BUTTON-",
                    ),
                    sg.Text(
                        "Characteristic",
                        enable_events=True,
                        key=key + "-EXPAND_TITLE-",
                    ),
                    characteristic_buttons,
                ],
                [
                    sg.pin(
                        sg.Column(
                            characteristic_layout,
                            metadata=section_arrows,
                            expand_x=True,
                            expand_y=True,
                            visible=False,
                            key=key,
                        )
                    )
                ],
            ],
            expand_x=True,
            expand_y=True,
        )
        return characteristic_section


if __name__ == "__main__":
    blexplorer = BLExplorerGUI()
    blexplorer.run()
