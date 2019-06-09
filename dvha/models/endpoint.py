#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import wx
from models.datatable import DataTable
from dialogs.main import AddEndpointDialog, DelEndpointDialog
from dialogs.export import save_string_to_file
from copy import deepcopy


ENDPOINT_DEF_COLUMNS = ['label', 'output_type', 'input_type', 'input_value', 'units_in', 'units_out']


class EndpointFrame:
    def __init__(self, parent, dvh, times_series, regression, control_chart):

        self.parent = parent
        self.dvh = dvh
        self.time_series = times_series
        self.regression = regression
        self.control_chart = control_chart
        self.initial_columns = ['MRN', 'Tx Site', 'ROI Name', 'Volume (cc)']
        self.widths = [150, 150, 250, 100]

        self.button = {'add': wx.Button(self.parent, wx.ID_ANY, "Add Endpoint"),
                       'del': wx.Button(self.parent, wx.ID_ANY, "Delete Endpoint"),
                       'exp': wx.Button(self.parent, wx.ID_ANY, 'Export')}

        self.table = wx.ListCtrl(self.parent, wx.ID_ANY,
                                 style=wx.BORDER_SUNKEN | wx.LC_HRULES | wx.LC_REPORT | wx.LC_VRULES)
        self.table.SetMinSize((1046, 800))
        self.data_table = DataTable(self.table)

        self.endpoint_defs = DataTable(None, columns=ENDPOINT_DEF_COLUMNS)

        if dvh:
            self.dvh.endpoints['data'] = self.data_table.data
            self.dvh.endpoints['defs'] = self.endpoint_defs.data

        self.__do_bind()
        self.__set_properties()
        self.__do_layout()

        self.disable_buttons()

    def __do_bind(self):
        self.parent.Bind(wx.EVT_BUTTON, self.add_ep_button_click, id=self.button['add'].GetId())
        self.parent.Bind(wx.EVT_BUTTON, self.del_ep_button_click, id=self.button['del'].GetId())
        self.parent.Bind(wx.EVT_BUTTON, self.on_export_csv, id=self.button['exp'].GetId())

    def __set_properties(self):
        for i, column in enumerate(self.initial_columns):
            self.table.AppendColumn(column, format=wx.LIST_FORMAT_LEFT, width=self.widths[i])

    def __do_layout(self):
        sizer_wrapper = wx.BoxSizer(wx.VERTICAL)
        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        for key in list(self.button):
            hbox.Add(self.button[key], 0, wx.ALL, 5)
        vbox.Add(hbox, 0, wx.ALL | wx.EXPAND, 5)
        vbox.Add(self.table, 1, wx.EXPAND, 0)
        sizer_wrapper.Add(vbox, 1, wx.ALL | wx.EXPAND, 20)
        self.layout = sizer_wrapper

    @property
    def ep_count(self):
        return len(self.endpoint_defs['label'])

    def calculate_endpoints(self):

        columns = [c for c in self.initial_columns]
        if self.data_table.data:
            current_labels = [key for key in list(self.data_table.data) if key not in columns]
        else:
            current_labels = []

        ep = {'MRN': self.dvh.mrn,
              'Tx Site': self.dvh.get_plan_values('tx_site'),
              'ROI Name': self.dvh.roi_name,
              'Volume (cc)': self.dvh.volume}

        ep_defs = self.endpoint_defs.data
        if ep_defs:
            for i, ep_name in enumerate(ep_defs['label']):

                if ep_name not in columns:
                    columns.append(ep_name)

                    if ep_name in current_labels:
                        ep[ep_name] = deepcopy(self.data_table.data[ep_name])

                    else:
                        endpoint_input = ep_defs['input_type'][i]
                        endpoint_output = ep_defs['output_type'][i]

                        x = float(ep_defs['input_value'][i])
                        if endpoint_input == 'relative':
                            x /= 100.

                        if 'V' in ep_name:
                            ep[ep_name] = self.dvh.get_volume_of_dose(x, volume_scale=endpoint_output,
                                                                      dose_scale=endpoint_input)

                        else:
                            ep[ep_name] = self.dvh.get_dose_to_volume(x, dose_scale=endpoint_output,
                                                                      volume_scale=endpoint_input)

        self.data_table.set_data(ep, columns)
        self.data_table.set_column_width(0, 150)
        self.data_table.set_column_width(1, 150)
        self.data_table.set_column_width(2, 200)

    def add_ep_button_click(self, evt):
        dlg = AddEndpointDialog(title='Add Endpoint')
        res = dlg.ShowModal()
        if res == wx.ID_OK and dlg.is_endpoint_valid:
            self.endpoint_defs.append_row(dlg.endpoint_row)
            self.calculate_endpoints()
            self.enable_buttons()
            self.update_endpoints_in_dvh()
            self.time_series.update_y_axis_options()
        dlg.Destroy()
        self.regression.stats_data.update_endpoints_and_radbio()
        self.regression.update_combo_box_choices()
        self.control_chart.update_combo_box_choices()

    def del_ep_button_click(self, evt):
        dlg = DelEndpointDialog(self.data_table.columns, title='Delete Endpoint')
        res = dlg.ShowModal()
        if res == wx.ID_OK:
            for value in dlg.selected_values:
                self.data_table.delete_column(value)
                endpoint_def_row = self.endpoint_defs.data['label'].index(value)
                self.update_endpoints_in_dvh()
                self.endpoint_defs.delete_row(endpoint_def_row)
            self.time_series.update_y_axis_options()
        dlg.Destroy()

        self.regression.stats_data.update_endpoints_and_radbio()
        self.regression.update_combo_box_choices()
        self.control_chart.update_combo_box_choices()

        if self.data_table.column_count == 3:
            self.button['del'].Disable()
            self.button['exp'].Disable()

    def update_dvh(self, dvh):
        self.dvh = dvh
        self.update_endpoints_in_dvh()

    def update_endpoints_in_dvh(self):
        if self.dvh:
            self.dvh.endpoints['data'] = self.data_table.data
            self.dvh.endpoints['defs'] = self.endpoint_defs.data

    def clear_data(self):
        self.data_table.delete_all_rows()
        self.endpoint_defs.delete_all_rows(force_delete_data=True)  # no attached layout, force delete

        if self.data_table.data:
            for column in list(self.data_table.data):
                if column not in self.initial_columns:
                    self.data_table.delete_column(column)

    def enable_buttons(self):
        for key in list(self.button):
            self.button[key].Enable()

    def disable_buttons(self):
        for key in list(self.button):
            self.button[key].Disable()

    def enable_initial_buttons(self):
        self.button['add'].Enable()

    def get_csv(self, selection=None):
        uid = {1: {'title': 'Study Instance UID',
                   'data': self.dvh.uid}}
        return self.data_table.get_csv(extra_column_data=uid)

    def on_export_csv(self, evt):
        save_string_to_file(self.parent, "Export Endpoints to CSV", self.get_csv)

    def get_save_data(self):
        return deepcopy({'data_table': self.data_table.get_save_data(),
                         'endpoint_defs': self.endpoint_defs.get_save_data()})

    def load_save_data(self, save_data):
        self.data_table.load_save_data(save_data['data_table'], ignore_layout=True)
        self.endpoint_defs.load_save_data(save_data['endpoint_defs'], ignore_layout=True)
        self.calculate_endpoints()

    @property
    def has_data(self):
        if self.endpoint_defs.data and self.endpoint_defs.data['label']:
            return True
        return False