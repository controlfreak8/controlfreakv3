from typing import List, Dict, Any, Tuple
from .CONSTANTS import Helmert, OverPoint, ResectionPoint, ControlPoint, RESECTION_KEYS, OVER_POINT_KEYS, HELMERT_PT_KEYS
from .text_from_12d import remove_parenthesis
from .create_django_models import create_helmert_setup, create_over_point_setup
import re


def split_number_at_end(string):
    match = re.search(r'(-?\d+(\.\d+)?)$', string)
    if match:
        number = match.group()
        string_without_number = string[:match.start()].strip()
        return string_without_number, float(number)
    else:
        return string, None

class StationSetupParser:

    def __init__(self, data: List[str], index: int, obj):
        self.setup_object = None
        self.data = data
        self.sliced_data = None
        self.index = index
        self.line_tracking = 0
        self.is_helmert_resection = False
        self.is_resection()
        self.obj = obj
        self.extract_setup_data()

    def return_setup_object(self) -> dict[str, Helmert] | dict[str, OverPoint]:
        """
        Returns the setup object.
        :return:
        """
        return self.setup_object

    def is_resection(self):
        """
        Checks if the setup is a resection or an over the point setup.
        :return:
        """

        iterator = 1

        while True:
            iterator += 1
            if 'group {' in self.data[self.index + iterator]:
                break

        # 29 is the number of lines in an otp setup

        self.is_helmert_resection = iterator <= 20

        self.line_tracking = self.index + iterator
        self.sliced_data = self.data[self.index + 2:self.index + iterator]

    def extract_setup_data(self):

        if self.is_helmert_resection:
            keys = RESECTION_KEYS
        else:
            keys = OVER_POINT_KEYS

        setup_dict = {}

        for key in keys:
            for line in self.sliced_data:
                if key in line:
                    key = remove_parenthesis(line.split()[1]).strip()
                    value = remove_parenthesis(line.split(key)[1]).strip()
                    setup_dict[key] = value

        if self.is_helmert_resection:
            iterator = 1
            pt_dict = {}
            resection_points = []

            while True:
                iterator += 1
                line = self.data[self.line_tracking + iterator]
                if "Check Shot" in line:
                #print(setup_dict, resection_points)
                    self.setup_object = create_helmert_setup(setup_dict, resection_points, self.obj)
                    break
                else:
                    for key in HELMERT_PT_KEYS:

                        if key in line:
                            if 'helm_tps_reflector_type_as_text_' in line:
                                reflector_type_key = remove_parenthesis(line.split()[1]).strip()
                                reflector = remove_parenthesis(line.split(reflector_type_key)[1]).strip()
                                reflector_id_key = self.data[self.line_tracking + iterator - 1].split()[1].strip()
                                pt_dict['reflector_id'] = remove_parenthesis(
                                    self.data[self.line_tracking + iterator - 1].split(reflector_id_key)[1]).strip()
                                reflector_type, reflector_constant = split_number_at_end(reflector)
                                pt_dict['reflector_type'] = reflector_type
                                pt_dict['reflector_constant'] = reflector_constant

                            elif 'helm_inst_meas_style_text_' in line:
                                instrument_measure_style_key = remove_parenthesis(line.split()[1]).strip()
                                pt_dict['ms_name'] = remove_parenthesis(
                                    line.split(instrument_measure_style_key)[1]).strip()
                                instrument_measure_style_name_key = \
                                self.data[self.line_tracking + iterator - 1].split()[1].strip()
                                pt_dict['ms_id'] = remove_parenthesis(
                                    self.data[self.line_tracking + iterator - 1].split(
                                        instrument_measure_style_name_key)[1]).strip()

                            elif 'helm_tps_settings_text_' in line:
                                instrument_setting_key = remove_parenthesis(line.split()[1]).strip()
                                pt_dict['set_name'] = remove_parenthesis(
                                    line.split(instrument_setting_key)[1]).strip()
                                instrument_setting_name_key = self.data[self.line_tracking + iterator - 1].split()[
                                    1].strip()
                                pt_dict['set_id'] = remove_parenthesis(
                                    self.data[self.line_tracking + iterator - 1].split(instrument_setting_name_key)[
                                        1]).strip()

                            zkey = remove_parenthesis(line.split()[1]).strip()
                            value = remove_parenthesis(line.split(zkey)[1]).strip()
                            zkey = key[:-1]
                            pt_dict.update({zkey: value})

                            if zkey == 'helm_tps_settings_text':
                                resection_points.append(pt_dict)
                                pt_dict = {}

        else:
            self.setup_object = create_over_point_setup(setup_dict)

