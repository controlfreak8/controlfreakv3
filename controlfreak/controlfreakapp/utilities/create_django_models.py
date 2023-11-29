from typing import List, Dict, Any, Tuple
from datetime import datetime
from django.db.utils import IntegrityError
from django.utils import timezone
from .CONSTANTS import DATE_FORMAT
from .. models import Coordinates, HelmertResection, ReflectorType, InstrumentMeasureStyle, InstrumentSettings, ResectionPoint, OverPointStationSetup

def create_over_point_setup(data: dict) -> Any | None:
    try:
        coordinates, created = Coordinates.objects.get_or_create(
            easting=float(data['is_x']),
            northing=float(data['is_y']),
            elevation=float(data['is_z']),
            flavour='OP'
        )

        bs_coordinates, created = Coordinates.objects.get_or_create(
            easting=float(data['bs_x']),
            northing=float(data['bs_y']),
            elevation=float(data['bs_ht']),
            flavour='BS'
        )

        otp_ob, created = OverPointStationSetup.objects.get_or_create(
            ops_id=data['is_id'],
            setup_type=data['setup_type'],
            coordinates=coordinates,
            origin_elevation=float(data['is_z_orig']),
            instrument_height=float(data['is_hi']),
            bearing_swing=float(data['is_bearing_swing']),
            utc_time=timezone.make_aware(datetime.strptime(data['is_utc_time_text'], DATE_FORMAT)),
            bs_id=data['bs_id'],
            bs_coordinates=bs_coordinates,
            bs_calc_elevation=float(data['bs_z']),
            bs_elevation_delta=float(data['bs_diff_hd']),
            bs_easting_delta=float(data['bs_diff_x']),
            bs_northing_delta=float(data['bs_diff_y']),
            bs_diff_z=float(data['bs_diff_z'])
        )

        if created:
            print(f"Created Over the point setup: {otp_ob}")
        else:
            print(f"Found Over-the-point: {otp_ob}")

        return otp_ob

    except IntegrityError:
        return None


def create_helmert_setup(data: dict, points: list, source_file_obj) -> Any | None:

    coordinates, created = Coordinates.objects.get_or_create(
        easting=float(data['is_x']),
        northing=float(data['is_y']),
        elevation=float(data['is_z']),
        flavour='HM'
    )

    try:
        resection, created = HelmertResection.objects.get_or_create(
            helmert_id=data['is_id'],
            setup_type=data['setup_type'],
            source_file=source_file_obj,
            coordinates=coordinates,
            origin_elevation=float(data['is_z_orig']),
            instrument_height=float(data['is_hi']),
            bearing_swing=float(data['is_bearing_swing']),
            utc_time=datetime.strptime(data['is_utc_time_text'], DATE_FORMAT),
            pos_error=float(data['is_helm_pos_error']),
            scale_factor=float(data['is_helm_scale_factor']),
            level_diff=float(data['is_helm_level_diff'])
        )

        if created:
            print(f"Created Helmert Resection: {resection}")
        else:
            print(f"Found Helmert Resection: {resection}")

        for point in points:
            use_pos = True if point['helm_use_xy'] == '1' else False
            use_ht = True if point['helm_use_z'] == '1' else False
            try:
                pos_error = point['helm_pos_error']

            except KeyError:
                pos_error = None

            coordinates, created = Coordinates.objects.get_or_create(
                easting=point['helm_x'],
                northing=point['helm_y'],
                elevation=point['helm_z'],
                flavour='Adjusted'
            )

            reflector_obj, created = ReflectorType.objects.get_or_create(
                reflector_type_id=point['reflector_id'],
                reflector_type_name=point['reflector_type'],
                reflector_constant=point['reflector_constant']
            )

            measure_style, created = InstrumentMeasureStyle.objects.get_or_create(
                instrument_measure_style_id=point['ms_id'],
                instrument_measure_style_name=point['ms_name']
            )

            instrument_settings, created = InstrumentSettings.objects.get_or_create(
                instrument_settings_id=point['set_id'],
                instrument_settings_name=point['set_name']
            )

            try:
                ResectionPoint.objects.get_or_create(
                    resection=resection,
                    helm_id=point['helm_id'],
                    model_name=point['helm_model_name'],
                    target_type=point['helm_string_name'],
                    coordinates=coordinates,
                    use_pos=use_pos,
                    use_ht=use_ht,
                    pos_error=pos_error,
                    tps_reflector_type=reflector_obj,
                    tps_measure_style=measure_style,
                    tps_settings=instrument_settings
                )
            except IntegrityError:
                print('resection point integrity error')
                pass
        resection.save()
        return resection

    except IntegrityError:
        print("Helmert resection integrity error")
        pass