import os
import dataclasses
from datetime import datetime

DATE_FORMAT = "%Y/%m/%d %H:%M:%S"

HELMERT_SETUP_KEYS = [
    'is_helm_pos_error', 'is_helm_scale_factor', 'is_helm_level_diff'
]

STATION_SETUP_KEYS = [
    'bs_id', 'bs_ht', 'bs_x', 'bs_y', 'bs_z', 'bs_diff_hd',
    'bs_diff_x', 'bs_diff_y', 'bs_diff_z', 'bs_model_ref'
]

COMMON_SETUP_KEYS = [
    'is_id', 'is_x', 'is_y', 'is_z', 'is_z_orig', 'is_hi', 'setup_type',
    'is_bearing_swing', 'setup_type', 'is_utc_time_text',
]

RESECTION_KEYS = HELMERT_SETUP_KEYS + COMMON_SETUP_KEYS

OVER_POINT_KEYS = STATION_SETUP_KEYS + COMMON_SETUP_KEYS

HELMERT_COORD_KEYS = [
    'helm_id_',
    'helm_model_name_',
    'helm_string_name_',
    'helm_x_', 'helm_y_', 'helm_z_', 'helm_use_xy_', 'helm_use_z_', 'helm_pos_error_',
]

HELMERT_META_KEYS = [
    'helm_tps_reflector_type_',
    'helm_tps_reflector_type_as_text',
    'helm_inst_meas_style_',
    'helm_inst_meas_style_text_',
    'helm_tps_settings_',
    'helm_tps_settings_text_'
]

HELMERT_PT_KEYS = HELMERT_COORD_KEYS + HELMERT_META_KEYS


@dataclasses.dataclass
class ControlPoint:
    id: str
    #setup_hash_key: str # foreign key to HelmertStationSetup
    easting: float
    northing: float
    elevation: float
    target_type: str
    horizontal_quality: int
    vertical_quality: int
    file_source: str
    adjusted: bool


@dataclasses.dataclass
class ControlPoint:
    id: str
    #setup_hash_key: str # foreign key to HelmertStationSetup
    easting: float
    northing: float
    elevation: float
    target_type: str
    horizontal_quality: int
    vertical_quality: int
    file_source: str
    adjusted: bool



@dataclasses.dataclass
class Helmert:
    helmert_id: str
    setup_type: str
    easting: float
    northing: float
    elevation: float
    origin_elevation: float
    instrument_height: float
    bearing_swing: float
    utc_time: datetime
    pos_error: float
    scale_factor: float
    level_diff: float
    hash_key: str

@dataclasses.dataclass
class OverPoint:
    ops_id: str
    setup_type: str
    easting: float
    northing: float
    elevation: float
    origin_elevation: float
    instrument_height: float
    bearing_swing: float
    utc_time: datetime
    bs_id: str
    bs_elevation: float
    bs_easting: float
    bs_northing: float
    bs_calc_elevation: float
    bs_elevation_delta: float
    bs_easting_delta: float
    bs_northing_delta: float
    bs_diff_z: float
    hash_key: str


@dataclasses.dataclass
class ResectionPoint:
    id: str
    setup_hash_key: str # foreign key to HelmertStationSetup
    source: str
    target_type: str
    easting: float
    northing: float
    elevation: float
    horizontal_angle: float # helm_hb_dms_x
    vertical_angle: float # helm_va_dms_x
    slope_distance: float # helm_sd_ after correction
    raw_slope_distance: float # helm_orig_sd_x
    used_position: bool # helm_use_xy_x
    used_elevation: bool # helm_use_z_x
    pos_error: float # helm_pos_error_x
    utc_time: str
    reflector_type: str # helm_tps_reflector_type_as_text_x
    measurement_style: str # helm_inst_meas_style_text_x
    measurement_settingS: str # helm_tps_settings_text_x