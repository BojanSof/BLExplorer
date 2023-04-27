import os
import sys

import PySimpleGUI as sg

from ble import Ble, BleStatus


MAX_NUM_DEVICES = 3  # maximum number of connected devices
MAX_NUM_SERVICES = 6  # maximum number of services per device
MAX_NUM_CHARACTERISTICS = 3  # maximum number of characteristics per service


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class BLExplorerGUI:
    def __init__(self):
        self.ble = Ble()
        sg.theme("DarkTeal12")
        self.layout = self._create_layout()
        self.running = False
        self.i_selected_dev = None
        # for updating connected devices layout
        self.dev_tabs_free = {i for i in range(1, MAX_NUM_DEVICES + 1)}
        self.dev_tabs = {}
        self.chars_maps = {}

    def run(self):
        self.window = sg.Window(
            "BLExplorer",
            self.layout,
            resizable=True,
            size=(1024, 700),
            font=("Helvetica", 12),
            icon=resource_path(os.path.join("resources", "blexplorer.ico")),
        )
        self.running = True
        while self.running:
            event, values = self.window.read(timeout=50)
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
                    if ble_selected_dev_status == BleStatus.Connecting:
                        self.window["-BLE_CONNECT-"].update(
                            text="Connect", disabled=True
                        )
                    elif ble_selected_dev_status == BleStatus.Disconnecting:
                        self.window["-BLE_CONNECT-"].update(
                            text="Disconnect", disabled=True
                        )
                    elif ble_selected_dev_status == BleStatus.Connected:
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
        elif (
            "READ" in event
            or "WRITE" in event
            or "NOTIFY" in event
            or "INDICATE" in event
        ):
            char_base_key = event.split("--")[0]
            tab_num = int(event.split("$")[1].split(",")[0])
            dev_addr = [
                addr for addr, tab in self.dev_tabs.items() if tab == tab_num
            ][0]
            char_uuid = [
                uuid
                for uuid, e_key in self.chars_maps[dev_addr].items()
                if char_base_key in e_key
            ][0]
            if "READ" in event:
                self.ble.read_characteristic(dev_addr, char_uuid)
            elif "WRITE" in event:
                data_str = sg.popup_get_text(
                    "Enter bytes to write, in hex", title="Write characteristic"
                )
                if data_str is not None:
                    data = bytearray.fromhex(data_str)
                    self.ble.write_characteristic(dev_addr, char_uuid, data)
            elif "NOTIFY" in event:
                if self.ble.are_notifications_enabled(dev_addr, char_uuid):
                    self.ble.stop_notifications_characteristic(
                        dev_addr, char_uuid
                    )
                else:
                    self.ble.start_notifications_characteristic(
                        dev_addr, char_uuid
                    )
        elif "DESCRIPTOR" in event:
            char_base_key = event.split("--")[0] + "-"
            tab_num = int(event.split("$")[1].split(",")[0])
            dev_addr = [
                addr for addr, tab in self.dev_tabs.items() if tab == tab_num
            ][0]
            char_uuid = [
                uuid
                for uuid, e_key in self.chars_maps[dev_addr].items()
                if char_base_key in e_key
            ][0]
            services = self.ble.get_services_and_characteristics(dev_addr)
            service = [
                serv
                for _, serv in services.items()
                if char_uuid in serv["characteristics"].keys()
            ][0]
            char = service["characteristics"][char_uuid]
            desc_uuids = list(char["descriptors"].keys())
            desc_names = [
                desc["name"] for _, desc in char["descriptors"].items()
            ]
            descriptor_name_key = char_base_key + "-DESCRIPTORS_NAMES-"
            descriptor_uuid_key = char_base_key + "-DESCRIPTORS_UUIDS-"
            if "NAMES" in event:
                i_desc = desc_names.index(values[event])
            else:
                i_desc = desc_uuids.index(values[event])
            self.window[descriptor_name_key].update(value=desc_names[i_desc])
            self.window[descriptor_uuid_key].update(value=desc_uuids[i_desc])

    def update(self):
        # update scan info
        self.update_scan()
        self.update_ble_status()
        self.update_data()

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
            if len(dev["manufacturer_data"]) > 0:
                mfr_id, mfr_data = list(dev["manufacturer_data"].items())[0]
                self.window["-ADV_MFR_ID-"].update(value=f"{mfr_id:04x}")
                self.window["-ADV_MFR_DATA-"].update(value=f"{mfr_data.hex()}")
            else:
                self.window["-ADV_MFR_ID-"].update(value="")
                self.window["-ADV_MFR_DATA-"].update(value="")
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

    def update_ble_status(self):
        status = self.ble.get_status_event()
        if status is not None:
            if (
                status[1] in [BleStatus.Disconnected, BleStatus.Connected]
                and self.i_selected_dev is not None
            ):
                status_address, connection_status = status
                ble_devices = self.ble.get_found_devices()
                ble_selected_dev = ble_devices[self.i_selected_dev]
                ble_selected_dev_addr = ble_selected_dev["address"]
                if status_address == ble_selected_dev_addr:
                    if connection_status == BleStatus.Connected:
                        if self.ble.is_connected(ble_selected_dev_addr):
                            self.window["-BLE_CONNECT-"].update(
                                text="Disconnect", disabled=False
                            )
                            # find free tab and assign it to the device
                            tab = min(self.dev_tabs_free)
                            self.dev_tabs[ble_selected_dev_addr] = tab
                            self.dev_tabs_free.remove(tab)
                            tab_key = f"-CONNECTED_DEVICE${tab}$-"
                            self.window[tab_key].update(
                                title=ble_selected_dev["name"]
                                if len(ble_selected_dev["name"]) > 0
                                else ble_selected_dev_addr,
                                visible=True,
                            )
                            self.set_tab_data(tab, ble_selected_dev_addr)
                            self.window[tab_key].select()
                            if len(self.dev_tabs_free) == MAX_NUM_DEVICES - 1:
                                self.window["-NO_CONN_DEVS_CONTAINER-"].update(
                                    visible=False
                                )
                                self.window["-CONN_DEVS_CONTAINER-"].update(
                                    visible=True
                                )
                    elif connection_status == BleStatus.Disconnected:
                        self.window["-BLE_CONNECT-"].update(
                            text="Connect", disabled=False
                        )
                        # release the device tab
                        tab = self.dev_tabs[ble_selected_dev_addr]
                        self.dev_tabs_free.add(tab)
                        del self.dev_tabs[ble_selected_dev_addr]
                        del self.chars_maps[ble_selected_dev_addr]
                        tab_key = f"-CONNECTED_DEVICE${tab}$-"
                        self.window[tab_key].update(visible=False)
                        if len(self.dev_tabs_free) == MAX_NUM_DEVICES:
                            self.window["-CONN_DEVS_CONTAINER-"].update(
                                visible=False
                            )
                            self.window["-NO_CONN_DEVS_CONTAINER-"].update(
                                visible=True
                            )
            elif status[1] in [
                BleStatus.NotificationsDisabled,
                BleStatus.NotificationsEnabled,
            ]:
                dev_addr, notification_status, char_uuid = status
                section = self.chars_maps[dev_addr][char_uuid]
                self.window[section + "-NOTIFY-"].update(
                    button_color=("white", "red")
                    if notification_status == BleStatus.NotificationsEnabled
                    else sg.theme_button_color()
                )
            elif status[1] in [BleStatus.WriteSuccessful]:
                pass

    def update_data(self):
        data = self.ble.get_data_event()
        if data is not None:
            dev_addr, char_uuid, read_data = data
            # find characteristic GUI key
            char_key = self.chars_maps[dev_addr][char_uuid]
            data_hex = read_data.hex()
            self.window[char_key + "-VALUE-"].update(value=data_hex)

    def set_tab_data(self, i_tab, dev_address):
        dev_attr = self.ble.get_services_and_characteristics(dev_address)
        if dev_attr is not None:
            self.chars_maps[dev_address] = {}
            for i_service, (service_uuid, service) in enumerate(
                dev_attr.items()
            ):
                service_key = f"-SERVICE${i_tab},{i_service + 1}$-"
                self.window[service_key + "-EXPAND_TITLE-"].update(
                    value=service["name"]
                )
                self.window[service_key + "-UUID-"].update(value=service_uuid)
                self.window[service_key + "-CONTAINER-"].update(visible=True)
                # by default, section is collapsed
                self.window[service_key].update(visible=False)
                self.window[service_key + "-EXPAND_BUTTON-"].update(
                    self.window[service_key].metadata[0]
                    if self.window[service_key].visible
                    else self.window[service_key].metadata[1]
                )
                # update characteristics data
                for i_char, (
                    char_uuid,
                    char,
                ) in enumerate(service["characteristics"].items()):
                    char_key = service_key + f"CHARACTERISTIC${i_char + 1}$-"
                    self.chars_maps[dev_address][char_uuid] = char_key
                    self.window[char_key + "-EXPAND_TITLE-"].update(
                        value=char["name"]
                    )
                    self.window[char_key + "-UUID-"].update(value=char_uuid)
                    self.window[char_key + "-PROPERTIES-"].update(
                        value=",".join(char["properties"])
                    )
                    desc_uuids = [uuid for uuid in char["descriptors"].keys()]
                    desc_names = [
                        desc["name"] for _, desc in char["descriptors"].items()
                    ]
                    if len(desc_uuids) > 0:
                        self.window[char_key + "-DESCRIPTORS_LABEL-"].update(
                            visible=True
                        )
                        self.window[char_key + "-DESCRIPTORS_NAMES-"].update(
                            value=desc_names[0], values=desc_names, visible=True
                        )
                        self.window[char_key + "-DESCRIPTORS_UUIDS-"].update(
                            value=desc_uuids[0], values=desc_uuids, visible=True
                        )
                    else:
                        self.window[char_key + "-DESCRIPTORS_LABEL-"].update(
                            visible=False
                        )
                        self.window[char_key + "-DESCRIPTORS_NAMES-"].update(
                            value="", values=[""], visible=False
                        )
                        self.window[char_key + "-DESCRIPTORS_UUIDS-"].update(
                            value="", values=[""], visible=False
                        )
                    self.window[char_key + "-READ-"].update(
                        visible="read" in char["properties"]
                    )
                    self.window[char_key + "-WRITE-"].update(
                        visible="write" in char["properties"]
                    )
                    self.window[char_key + "-INDICATE-"].update(
                        visible="indicate" in char["properties"]
                    )
                    self.window[char_key + "-NOTIFY-"].update(
                        visible="notify" in char["properties"]
                    )
                    if (
                        len(char["properties"]) == 1
                        and "write" in char["properties"][0]
                    ):
                        self.window[char_key + "-VALUE_LABEL-"].update(
                            visible=False
                        )
                        self.window[char_key + "-VALUE-"].update(visible=False)
                    else:
                        self.window[char_key + "-VALUE_LABEL-"].update(
                            visible=True
                        )
                        self.window[char_key + "-VALUE-"].update(visible=True)
                    self.window[char_key + "-CONTAINER-"].update(visible=True)
                    # by default, section is collapsed
                    self.window[char_key].update(visible=False)
                    self.window[char_key + "-EXPAND_BUTTON-"].update(
                        self.window[char_key].metadata[0]
                        if self.window[char_key].visible
                        else self.window[char_key].metadata[1]
                    )
                for i_char in range(
                    len(service["characteristics"]), MAX_NUM_CHARACTERISTICS
                ):
                    char_key = service_key + f"CHARACTERISTIC${i_char + 1}$-"
                    self.window[char_key + "-CONTAINER-"].update(visible=False)

            for i_service in range(len(dev_attr), MAX_NUM_SERVICES):
                service_key = f"-SERVICE${i_tab},{i_service + 1}$-"
                self.window[service_key + "-CONTAINER-"].update(visible=False)
            dev_tab_section = f"-DEV${i_tab}$_CONTAINER-"
            self.window.refresh()
            self.window[dev_tab_section].contents_changed()

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
                resource_path(os.path.join("resources", "blexplorer.png")),
                size=(100, 100),
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
                [sg.Text("Manufacturer Data", key="-ADV_MFR_ID_LABEL-")],
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
                        size=(6, 1),
                        key="-ADV_MFR_ID-",
                    ),
                    sg.Input(
                        "",
                        readonly=True,
                        size=(27, 1),
                        key="-ADV_MFR_DATA-",
                    ),
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
            sg.Column(
                [
                    [
                        sg.Column(
                            [[ble_dev_table]],
                            justification="left",
                            expand_x=True,
                        ),
                        sg.Column(
                            [[ble_adv_info_frame]], justification="right"
                        ),
                    ]
                ],
                expand_x=True,
                expand_y=True,
            )
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
                            key=f"-DEV${i}$_CONTAINER-",
                        )
                    ]
                ],
                expand_x=True,
                expand_y=True,
                visible=False,
                key=f"-CONNECTED_DEVICE${i}$-",
            )
            for i in range(1, MAX_NUM_DEVICES + 1)
        ]
        tab_group = sg.TabGroup(
            [tabs],
            size=(500, 500),
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
                            visible=False,
                            key="-CONN_DEVS_CONTAINER-",
                        ),
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
                            element_justification="center",
                            expand_x=True,
                            expand_y=True,
                            visible=True,
                            key="-NO_CONN_DEVS_CONTAINER-",
                        ),
                    ],
                ],
                size=(500, 500),
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
        service_labels = sg.Column(
            [
                [sg.Text("UUID", key=key + "-UUID_LABEL-")],
            ]
        )
        service_vals = sg.Column(
            [
                [
                    sg.Input(
                        "",
                        readonly=True,
                        size=(33,),
                        key=key + "-UUID-",
                    )
                ]
            ]
        )
        service_layout = [[service_labels, service_vals]] + [
            [
                sg.pin(
                    sg.Frame(
                        "",
                        [
                            [
                                self._create_characteristics_layout(
                                    key + f"CHARACTERISTIC${i}$-",
                                    section_arrows,
                                )
                            ]
                        ],
                        border_width=1,
                        expand_x=True,
                        expand_y=True,
                        key=key + f"CHARACTERISTIC${i}$-" + "-CONTAINER-",
                    )
                )
            ]
            for i in range(1, MAX_NUM_CHARACTERISTICS + 1)
        ]
        service_section = sg.pin(
            sg.Frame(
                "",
                [
                    [
                        sg.Column(
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
                                ]
                            ],
                            expand_x=True,
                        )
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
                key=key + "-CONTAINER-",
            )
        )
        return service_section

    def _create_characteristics_layout(
        self, key, section_arrows=(sg.SYMBOL_DOWN, sg.SYMBOL_UP)
    ):
        characteristic_labels = sg.Column(
            [
                [sg.Text("UUID", key=key + "-UUID_LABEL-")],
                [sg.Text("Properties", key=key + "-PROPERTIES_LABEL-")],
                [sg.pin(sg.Text("Value", key=key + "-VALUE_LABEL-"))],
                [
                    sg.pin(
                        sg.Text("Descriptors", key=key + "-DESCRIPTORS_LABEL-")
                    )
                ],
            ]
        )
        characteristic_vals = sg.Column(
            [
                [
                    sg.Input(
                        "",
                        readonly=True,
                        size=(33,),
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
                    sg.pin(
                        sg.Input(
                            "",
                            readonly=True,
                            size=(33,),
                            key=key + "-VALUE-",
                        )
                    )
                ],
                [
                    sg.pin(
                        sg.Combo(
                            [""],
                            default_value="",
                            readonly=True,
                            size=(33,),
                            enable_events=True,
                            key=key + "-DESCRIPTORS_NAMES-",
                        )
                    ),
                    sg.pin(
                        sg.Combo(
                            [""],
                            default_value="",
                            readonly=True,
                            size=(33,),
                            enable_events=True,
                            key=key + "-DESCRIPTORS_UUIDS-",
                        )
                    ),
                ],
            ]
        )
        characteristic_layout = [[characteristic_labels, characteristic_vals]]
        characteristic_buttons = sg.Column(
            [
                [
                    sg.pin(
                        sg.Button(
                            "↓",
                            enable_events=True,
                            font=14,
                            key=key + "-READ-",
                        )
                    ),
                    sg.pin(
                        sg.Button(
                            "↑",
                            enable_events=True,
                            font=14,
                            key=key + "-WRITE-",
                        )
                    ),
                    sg.pin(
                        sg.Button(
                            "↑↓",
                            enable_events=True,
                            font=14,
                            disabled=True,  # indications are not supported yet
                            key=key + "-INDICATE-",
                        )
                    ),
                    sg.pin(
                        sg.Button(
                            "↓↓",
                            enable_events=True,
                            font=14,
                            key=key + "-NOTIFY-",
                        )
                    ),
                ]
            ],
            element_justification="right",
        )
        characteristic_section = sg.Column(
            [
                [
                    sg.Column(
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
                                sg.Push(),
                                characteristic_buttons,
                            ]
                        ],
                        expand_x=True,
                    )
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
