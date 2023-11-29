import os
import re
import zipfile
import logging
import math
from io import BytesIO, StringIO
import csv
from django.http import HttpResponse
from typing import Optional
from typing import List, Dict, Any, Tuple

from .CONSTANTS import Helmert, OverPoint, ResectionPoint, ControlPoint, RESECTION_KEYS, OVER_POINT_KEYS
from statistics import mean
from .station_setup_parser import StationSetupParser
from .text_from_12d import TextFrom12dConverter, split_string, remove_parenthesis
from ..models import TertiaryControlFile, Coordinates, UnAdjustedTertiaryControlPoint, OverPointStationSetup, AveragedTertiaryControlPoint
from ..utilities import geometry_manipulation as gm


def write_to_report_csv(rows):

    output = StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow(row)

    return output.getvalue()

def adjust_tertiary_control_points(queryset, hz_tolerance, vz_tolerance) -> None:
    hz_tolerance = float(hz_tolerance/1000)
    vz_tolerance = float(vz_tolerance/1000)

    tertiary_control = []

    for cp in queryset:
        tertiary_control_point = {
            cp.control_id:
                ControlPoint(
                    id=cp.control_id,
                    easting=cp.coordinates.easting,
                    northing=cp.coordinates.northing,
                    elevation=cp.coordinates.elevation,
                    target_type=cp.target_type,
                    horizontal_quality=4,
                    vertical_quality=4,
                    file_source=str(cp.source),
                    adjusted=False,
                ),
        }
        tertiary_control.append(tertiary_control_point)

    clustered = gm.cluster_data(tertiary_control, euclidean_dist=hz_tolerance*3)
    one_shot, to_process = gm.remove_incorporated_shots_testing(clustered)

    noise, shots_to_investigate = gm.cluster_data_split_noise(to_process, euclidean_dist=hz_tolerance*3)

    for cp_list in noise.values():
        for cp_dict in cp_list:
            one_shot.update(cp_dict)

    print(f'There are {len(one_shot)} points that will need additional observations.')
    print(f'Compared the euclidian distance and Hz delta of {len(shots_to_investigate)} shots.')

    rows = []
    proposed_rows = []
    one_shot_rows = []
    one_shot_rows.append(['Name', 'Easting', 'Northing', 'Elevation', 'Target Type','Original Source'])
    for k,v in one_shot.items():

        one_shot_rows.append((v.id, v.easting, v.northing, v.elevation, v.target_type, v.file_source))

    for i, (label, shots) in enumerate(shots_to_investigate.items()):
        res = gm.cluster_processing(shots, pos_thresh=hz_tolerance+.0009, ht_thresh=vz_tolerance+.0009)
        if res is not None:
            tab, shots_to_average, pos_val, ht_val, file_a, file_b = res
            a, b = shots_to_average

            shot_col = [
                [cp.id,
                 cp.easting,
                 cp.northing,
                 cp.elevation,
                 cp.target_type,
                 cp.file_source] for cp in shots_to_average]

            averages = [round(mean([item[i] for item in shot_col]), 3) for i in range(1, 4)]
            codes = [item[0] for item in shot_col]
            names = [item[4] for item in shot_col]
            best_code = gm.get_best_code(codes)
            best_name = gm.get_best_name(names)

            try:
                a_coords, created = Coordinates.objects.get_or_create(
                    easting=a.easting,
                    northing=a.northing,
                    elevation=a.elevation,
                    flavour='RW'
                )

            except Coordinates.MultipleObjectsReturned:
                a_coords = Coordinates.objects.filter(
                    easting=a.easting,
                    northing=a.northing,
                    elevation=a.elevation,
                    flavour='RW').first()
            try:
                b_coords, created = Coordinates.objects.get_or_create(
                    easting=b.easting,
                    northing=b.northing,
                    elevation=b.elevation,
                    flavour='RW'
                )

            except Coordinates.MultipleObjectsReturned:
                b_coords = Coordinates.objects.filter(
                    easting=b.easting,
                    northing=b.northing,
                    elevation=b.elevation,
                    flavour='RW'
                ).first()

            try:
                try:
                    a_seed = UnAdjustedTertiaryControlPoint.objects.get(
                        control_id=a.id,
                        target_type=a.target_type,
                        coordinates=a_coords
                    )
                except UnAdjustedTertiaryControlPoint.MultipleObjectsReturned:
                    a_seed = UnAdjustedTertiaryControlPoint.objects.filter(
                        control_id=a.id,
                        target_type=a.target_type,
                        coordinates=a_coords
                    ).first()

                try:
                    b_seed = UnAdjustedTertiaryControlPoint.objects.get(
                        control_id=b.id,
                        target_type=b.target_type,
                        coordinates=b_coords)

                except UnAdjustedTertiaryControlPoint.MultipleObjectsReturned:
                    b_seed = UnAdjustedTertiaryControlPoint.objects.filter(
                        control_id=b.id,
                        target_type=b.target_type,
                        coordinates=b_coords
                    ).first()

                averaged_coords, created = Coordinates.objects.get_or_create(
                    easting=averages[0],
                    northing=averages[1],
                    elevation=averages[2],
                    flavour='ME'
                )

                pc, created = AveragedTertiaryControlPoint.objects.get_or_create(
                    control_id=best_code,
                    target_type=best_name,
                    horizontal_quality=4,
                    vertical_quality=4,
                    a_seed=a_seed,
                    b_seed=b_seed,
                    coordinates=averaged_coords,
                )
                if created:
                    print(f'Created {pc}')
                else:
                    print(f'Already exists {pc}')

                if a_seed.resection is None:
                    a_setup_id = a_seed.otp_setup.ops_id
                    a_pos_error = 'TBC'
                    a_scale_factor = 'TBC'
                    a_level_diff = a_seed.otp_setup.bs_elevation_delta
                else:
                    a_resection_coords = [
                        (
                            rp.helm_id,
                            rp.target_type,
                            "Yes" if rp.use_pos else "No",
                            "Yes" if rp.use_ht else "No",
                            rp.pos_error,
                            rp.tps_reflector_type,
                            rp.tps_measure_style,
                            rp.tps_settings,
                            rp.model_name
                        ) for rp in a_seed.resection.resectionpoint_set.all()]

                    a_setup_id = a_seed.resection.helmert_id
                    a_pos_error = a_seed.resection.pos_error
                    a_scale_factor = a_seed.resection.scale_factor
                    a_level_diff = a_seed.resection.level_diff

                if b_seed.resection is None:
                    b_setup_id = b_seed.otp_setup.ops_id
                    b_pos_error = 'TBC'
                    b_scale_factor = 'TBC'
                    b_level_diff = b_seed.otp_setup.bs_elevation_delta
                else:
                    b_resection_coords =  [
                        (
                            rp.helm_id,
                            rp.target_type,
                            "Yes" if rp.use_pos else "No",
                            "Yes" if rp.use_ht else "No",
                            rp.pos_error,
                            rp.tps_reflector_type,
                            rp.tps_measure_style,
                            rp.tps_settings,
                            rp.model_name
                        ) for rp in b_seed.resection.resectionpoint_set.all()]

                    b_setup_id = b_seed.resection.helmert_id
                    b_pos_error = b_seed.resection.pos_error
                    b_scale_factor = b_seed.resection.scale_factor
                    b_level_diff = b_seed.resection.level_diff

                proposed_cp_row = (pc.control_id, pc.coordinates.easting, pc.coordinates.northing, pc.coordinates.elevation, pc.target_type)
                # Resection / OTP setup for control point shot.
                a_seed_row = [a_seed.control_id, a.easting, a.northing, a.elevation, a_seed.target_type,'','','','', a_seed.source]
                b_seed_row = [b_seed.control_id, b.easting, b.northing, b.elevation, b_seed.target_type,'','','','',  b_seed.source]

                a_setup_row = [a_setup_id, a_pos_error, a_scale_factor, a_level_diff]
                b_setup_row = [b_setup_id, b_pos_error, b_scale_factor, b_level_diff]

                a_b_deltas_row = ['','', math.sqrt((a.easting - b.easting)**2 + (a.northing - b.northing)**2), a.elevation - b.elevation]

                rows.append(['Proposed Name', 'Easting', 'Northing', 'Elevation', 'Target Type'])
                proposed_rows.append(proposed_cp_row)
                rows.append(proposed_cp_row)
                rows.append([" "])

                rows.append(['', 'A-B Deltas:', 'Hz Euclidian', 'Vz Delta'])
                rows.append(a_b_deltas_row)
                rows.append([" "])

                rows.append(['Seed A Name', 'Easting', 'Northing', 'Elevation','Target Type', '','','','', 'Source'])
                rows.append(a_seed_row)
                rows.append([''])
                rows.append(['', 'Resection', 'Pos Error', 'Scale Factor', 'Level Delta',])

                rows.append([''] + a_setup_row)
                rows.append([''])
                rows.append([''] +['Resection Points'])
                                # (rp.helm_id, rp.target_type, rp.use_pos, rp.use_ht, rp.pos_error, rp.tps_reflector_type, rp.tps_measure_style, rp.tps_settings, rp.model_name)
                rows.append(['']+ ['Name','Type & Quality','Pos Held','Ht Held',  'Pos Error', 'Reflector Type','Measure Style','TPS setting','Source'])
                for row in a_resection_coords:
                    rows.append([''] + list(row))


                rows.append([" "])
                rows.append(['Seed B Name', 'Easting', 'Northing', 'Elevation','Target Type','','','','', 'Source'])
                rows.append(b_seed_row)
                rows.append([''])
                rows.append(['', 'Resection', 'Pos Error', 'Scale Factor', 'Level Delta'])
                rows.append([''] + b_setup_row)
                rows.append([''])
                rows.append([''] + ['Resection Points'])
                rows.append([''] + ['Name', 'Type & Quality', 'Pos Held', 'Ht Held', 'Pos Error', 'Reflector Type',
                                    'Measure Style', 'TPS setting', 'Source'])
                for row in b_resection_coords:
                    rows.append([''] + list(row))

                rows.append([" "])
                rows.append([" "])

            except UnAdjustedTertiaryControlPoint.DoesNotExist:
                pass


    return rows, one_shot_rows, proposed_rows

def create_internet_zip(report_data, one_shot_data, proposed_data, report_name) -> HttpResponse:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zip_file:
        if report_data:
            zip_file.writestr(f'{report_name}_averaging_report.csv', report_data)
        if one_shot_data:
            zip_file.writestr(f'{report_name}_additional_obs_required.csv', one_shot_data)
        if proposed_data:
            zip_file.writestr(f'{report_name}_proposed_new_control.csv', proposed_data)

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename=f{report_name}.zip'

    # Important: close the buffer
    buffer.close()

    return response

def create_control_point_objects(obj) -> list[dict[Any, Any] | dict[Any, ControlPoint]]:
    print(f'Processing {obj}...')
    path = obj.file.path
    raw_12da = TextFrom12dConverter(path).get_12da_text()

    lines = raw_12da.splitlines()
    tertiary_control_point = {}
    coordinates_collector = []
    point_data_collector = []
    final_collector = []
    query_set_collector = []
    has_setup_data = False
    target_type = 'Not specified'

    for i in range(len(lines)):

        if 'super ' in lines[i]:
            # if lines[i].startswith('super '):
            # Check if the next line starts with 'name'
            if i + 1 < len(lines) and 'name ' in lines[i + 1]:
                # try:
                target_type = remove_parenthesis(lines[i + 1].split()[1].strip())
                if target_type == '':
                    target_type = 'Not specified'

        # Collect the coordinates
        if 'data_3d' in lines[i]:
            has_setup_data = False
            # if lines[i].startswith('data_3d'):
            # will have as many lines as there are points
            coordinates_iterator = 1

            while True:
                line = lines[i + coordinates_iterator]

                try:
                    coordinates = [float(item) for item in line.split()]
                    coordinates_collector.append(coordinates + [target_type])
                    coordinates_iterator += 1

                except ValueError:
                    # Could not convert to float, so it must be the end of the coordinates
                    # if lines[i + coordinates_iterator + 1] == '}':
                    if '}' in lines[i + coordinates_iterator + 1]:
                        coordinates_collector.pop(-1)

                    point_data_iterator = coordinates_iterator + 2
                    break

            while True:
                # Got to the end of the set of coordinates or to the end of a file
                try:
                    if '}' in lines[i + point_data_iterator]:
                        # if lines[i + point_data_iterator] == '}':
                        break

                except IndexError:
                    break

                point_data = lines[i + point_data_iterator]  # get the next line
                point_data = split_string(point_data)  # split the line into a list of strings
                point_data_collector.extend(point_data)
                point_data_iterator += 1

        if "Inst Stat Setup" in lines[i]:
            # Get the setup data
            if not has_setup_data:

                setup_data = StationSetupParser(lines, i, obj).return_setup_object()

                has_setup_data = setup_data is not None

                if setup_data is not None:

                    merged = zip(point_data_collector, coordinates_collector)

                    collector = []

                    for point_data, coordinate in merged:
                        # As long as the coordinate is not already in the collector, add it and the point id
                        if coordinate not in collector:
                            # Create the control point using the class
                            collector.append([point_data] + coordinate)  # + [setup_hash_key])

                    for j, item in enumerate(collector):
                        pt_id = item[0]
                        #hash_key = create_hash(item[1:4])
                        if pt_id not in tertiary_control_point:
                            tertiary_control_point = {
                                pt_id:
                                    ControlPoint(
                                        id=item[0],
                                        easting=item[1],
                                        northing=item[2],
                                        elevation=item[3],
                                        target_type=item[4],
                                        horizontal_quality=4,
                                        vertical_quality=4,
                                        file_source=obj,
                                        adjusted=False,
                                    ),
                            }

                            final_collector.append(tertiary_control_point)

                    print(f'{len(final_collector)} control points for each setup')

                    for item in final_collector:

                        for key, tcp in item.items():
                            coordinates, created = Coordinates.objects.get_or_create(
                                easting=tcp.easting,
                                northing=tcp.northing,
                                elevation=tcp.elevation,
                                flavour='RW'
                            )

                            tertiary_cp_for_db, created = UnAdjustedTertiaryControlPoint.objects.get_or_create(
                                control_id=key,
                                coordinates=coordinates,
                                target_type=tcp.target_type,
                                horizontal_quality=4,
                                vertical_quality=4,
                                source=obj,
                                adjusted=False,
                            )

                            if created:
                                if setup_data.setup_type == 'Helmert':
                                    tertiary_cp_for_db.resection = setup_data
                                    tertiary_cp_for_db.save()
                                else:
                                    tertiary_cp_for_db.otp_setup = setup_data
                                    tertiary_cp_for_db.save()

                                print(f'Created {tertiary_cp_for_db}')
                            else:
                                print(setup_data.setup_type)
                                print(f'Already exists {tertiary_cp_for_db}')
                            query_set_collector.append(tertiary_cp_for_db)
    return query_set_collector
    #return final_collector