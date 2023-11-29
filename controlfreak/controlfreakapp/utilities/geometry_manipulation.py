import numpy as np
from sklearn.cluster import DBSCAN
import statistics

from .string_parsing import create_hash

from fuzzywuzzy import fuzz
import itertools
import math

import os
import re

pattern = r"(?<![a-zA-Z])\d+(?![a-zA-Z])"
from fuzzywuzzy import process


def format_for_split(clust_data):
    to_process_further = []

    for item in clust_data.items():

        no_shots_in_group = len(item[1])

        # There is a dict with 100's of items

        col = []
        for pts_dict in item[1]:

            for k, v in pts_dict.items():
                no_shots_in_group -= 1

                col.append((k, v))

                if no_shots_in_group == 0:
                    # ... add them in to the list that will be processed later
                    # There might be no shots left in the group,
                    # but none of the shots were added to the collector, so...

                    if len(col) > 0:
                        to_process_further.append(col)
                        col = []

    return to_process_further


def cluster_flat_data(input_array, euclidean_dist):
    mod_input_array = []

    for item in input_array:
        key = item[0]
        value = item[1][:4]
        mod_input_array.append({key: value})

    pt_dict = {}
    for pt_data in mod_input_array:
        keys = pt_data.keys()
        for key in keys:
            if key in pt_dict:
                mod_key = f'{key}_tert'
                pt_dict[mod_key] = pt_data[key][:4]
            pt_dict[key] = pt_data[key][:4]

    x_y_z = [value[:3] for value in pt_dict.values()]
    print(x_y_z)
    point_array = np.array(x_y_z)

    # define the DBSCAN model
    dbscan = DBSCAN(eps=euclidean_dist, min_samples=50, metric='euclidean')

    # fit the model to the data
    dbscan.fit(point_array)

    # get the labels assigned to each point
    labels = dbscan.labels_

    # create a dictionary to store the clustered points
    clusters = {}

    for i, label in enumerate(labels):
        key = list(mod_input_array[i].keys())[0]

        if label not in clusters:
            clusters[label] = [{key: mod_input_array[i][key]}]
        else:
            clusters[label].append({key: mod_input_array[i][key]})

    return clusters


def cluster_data(input_array, euclidean_dist):
    """
    This function clusters a given set of geographical data points based on their Euclidean distance using the DBSCAN (Density-Based Spatial Clustering of Applications with Noise) algorithm. The function takes in two parameters: input_array and euclidean_dist.

    Parameters:
    input_array (list of dict): The input data to be clustered. Each dictionary in the list represents a data point with the structure {key: value}, where key is a unique identifier and value is an object with properties: easting, northing, and elevation, representing the coordinates of the point.
    euclidean_dist (float): The maximum distance between two samples for them to be considered as in the same neighborhood. This parameter is passed as the 'eps' argument in the DBSCAN model.

    The function constructs a NumPy array from the coordinates in the input data, applies the DBSCAN algorithm to cluster the data based on the given Euclidean distance, and returns a dictionary of the resulting clusters. In the result, each key is a cluster label assigned by the DBSCAN model and the value is a list of data points in the cluster.

    Returns:
    clusters (dict): A dictionary where each key is a cluster label and each value is a list of data points that belong to the cluster. Each data point is represented as a dictionary similar to the input format.
    """

    coords = []
    keys = []

    for item in input_array:
        key = list(item.keys())[0]
        keys.append(key)
        v = item[key]
        easting = v.easting
        northing = v.northing
        elevation = v.elevation
        coords.append([easting, northing, elevation])

    point_array = np.array(coords)

    # define the DBSCAN model
    dbscan = DBSCAN(eps=euclidean_dist, min_samples=2, metric='euclidean')

    # fit the model to the data
    dbscan.fit(point_array)

    # get the labels assigned to each point
    labels = dbscan.labels_

    # create a dictionary to store the clustered points
    clusters = {}

    for i, label in enumerate(labels):

        key = keys[i]

        if label not in clusters:
            clusters[label] = [{key: input_array[i][key]}]
        else:
            clusters[label].append({key: input_array[i][key]})

    return clusters


def cluster_data_split_noise(input_dict, euclidean_dist):
    """
    This function clusters a given set of geographical data points based on their Euclidean distance using the DBSCAN (Density-Based Spatial Clustering of Applications with Noise) algorithm. The function takes in two parameters: input_array and euclidean_dist.

    Parameters:
    input_array (list of dict): The input data to be clustered. Each dictionary in the list represents a data point with the structure {key: value}, where key is a unique identifier and value is an object with properties: easting, northing, and elevation, representing the coordinates of the point.
    euclidean_dist (float): The maximum distance between two samples for them to be considered as in the same neighborhood. This parameter is passed as the 'eps' argument in the DBSCAN model.

    The function constructs a NumPy array from the coordinates in the input data, applies the DBSCAN algorithm to cluster the data based on the given Euclidean distance, and returns a dictionary of the resulting clusters. In the result, each key is a cluster label assigned by the DBSCAN model and the value is a list of data points in the cluster.

    Returns:
    clusters (dict): A dictionary where each key is a cluster label and each value is a list of data points that belong to the cluster. Each data point is represented as a dictionary similar to the input format.
    """

    coords = []
    keys = []

    for key, cp in input_dict.items():
        keys.append(key)
        coords.append([cp.easting, cp.northing, cp.elevation])

    point_array = np.array(coords)

    # define the DBSCAN model
    dbscan = DBSCAN(eps=euclidean_dist, min_samples=2, metric='euclidean')

    # fit the model to the data
    dbscan.fit(point_array)

    # get the labels assigned to each point
    labels = dbscan.labels_

    # create a dictionary to store the clustered points
    clusters = {}
    noise_cluster = {-1: []}

    for i, label in enumerate(labels):

        key = keys[i]
        if label == -1:
            noise_cluster[label].append({key: input_dict[key]})
        else:
            if label not in clusters:
                clusters[label] = [{key: input_dict[key]}]
            else:
                clusters[label].append({key: input_dict[key]})

    return noise_cluster, clusters


def avg_similarity(string, string_list):
    scores = [fuzz.token_sort_ratio(string, s) for s in string_list]
    return sum(scores) / len(scores)


def get_best_code(codes):
    best_code = 'UNCODED'
    codes = [item.replace(" ", "") for item in codes if "CHK" not in item]
    try:
        # TODO S07 vs 008C
        # if len(codes) == 2:
        #    print(codes)
        best_code = max(codes, key=lambda s: avg_similarity(s, codes))

        try:
            last_char = best_code[-1]
            if last_char.isalpha() and last_char.upper() in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                best_code = best_code[:-1]

        except IndexError:
            print('A point with no code')
            best_code = 'UNCODED'

    except ValueError:
        print("Point with no name")

    return best_code


def get_best_name(names):
    best_name = 'UNNAMED'

    names_to_filter = ['CHK', 'PTS', 'PSHT', 'TEST', 'PIN']
    # Remove any names in the name list that are 'PTS', PSHT, 'CHK'
    filtered_names = [item for item in names if not any(x in item for x in names_to_filter)]

    try:
        best_name = max(filtered_names, key=lambda s: avg_similarity(s, names))
    except ValueError:
        # Filtered names is empty:
        return best_name

    return best_name


def _render_mm(value):
    try:
        if 0.001 <= value <= 0.005:
            return f'{str(value)[4]} mm'
        elif value >= 0.005:
            if str(value)[6] == 0:
                return f'{str(value)[4]}.{str(value)[5]}{str(value)[6]} mm'
            else:
                return f'{str(value)[4]}.{str(value)[5]} mm'
        else:
            value_1 = str(value)[5]
            if value_1 == 0:
                value = str(value)[6]
                return f'{value} hundredths of a mm'

            as_int = int(value_1)
            if as_int == 1:
                return f'{value_1} tenth of a mm'
            else:
                return f'{value_1} tenths of a mm'
    except IndexError:
        # Same value saved twice
        return None


def remove_spaces(s):
    # replace 'ME ' or 'VT ' followed by 'B' or 'L' and a number with
    # 'ME' or 'VT' immediately followed by 'B' or 'L' and the number
    return re.sub(r"(ME|VT) ([BL]\d+)", r"\1\2", s)


def get_most_probable_string(ref_string, string_list):
    # Use the extractOne method from fuzzywuzzy.process which compares ref_string with all the strings in string_list
    # and returns the best match along with its score.
    best_match = process.extractOne(ref_string, string_list)

    return best_match


def min_from_dict(lst_of_dicts):
    # Flatten the list of dictionaries into one dictionary
    flat_dict = {k: v for d in lst_of_dicts for k, v in d.items()}

    # Find the key of the minimum value
    min_key = min(flat_dict, key=flat_dict.get)
    min_value = flat_dict[min_key]

    return min_key, min_value


def two_min_from_dict(lst_of_dicts):
    # Flatten the list of dictionaries into one dictionary
    flat_dict = {k: v for d in lst_of_dicts for k, v in d.items()}

    # Find the key of the minimum value
    min_key = min(flat_dict, key=flat_dict.get)
    min_value = flat_dict[min_key]

    # Remove the minimum value from the dictionary
    flat_dict.pop(min_key)

    # Find the key of the second minimum value
    second_min_key = min(flat_dict, key=flat_dict.get)
    second_min_value = flat_dict[second_min_key]

    return min_key, min_value, second_min_key, second_min_value


def file_name_to_csv(file_name, me_keys, vt_keys, key_collector, match_thresh=65):
    raw_file_name = os.path.splitext(file_name)[0]
    sans_date = re.sub(pattern, '', raw_file_name)
    file_name = remove_spaces(sans_date)

    if 'ME' in file_name:
        key, match = get_most_probable_string(file_name, me_keys)
        if match > match_thresh:
            key_collector.add(key)

    elif 'VT' in file_name:
        key, match = get_most_probable_string(file_name, vt_keys)
        if match > match_thresh:
            key_collector.add(key)
    return key_collector


def one_shot_file_name_to_csv(file_name, me_keys, vt_keys, match_thresh=65):
    raw_file_name = os.path.splitext(file_name)[0]
    sans_date = re.sub(pattern, '', raw_file_name)
    file_name = remove_spaces(sans_date)

    if 'ME' in file_name:
        key, match = get_most_probable_string(file_name, me_keys)
        if match > match_thresh:
            return key

    elif 'VT' in file_name:
        key, match = get_most_probable_string(file_name, vt_keys)
        if match > match_thresh:
            return key

    return 'misc'


def one_shot_ref_processing_org(item, me_keys, vt_keys):
    key = list(item.keys())[0]
    hash_key = item[key].hash_key
    file_name = item[key].file_source
    file_name = one_shot_file_name_to_csv(file_name, me_keys, vt_keys)
    code = key
    x = item[key].easting
    y = item[key].northing
    z = item[key].elevation
    name = item[key].target_type
    file_source = item[key].file_source

    row = [code] + [x, y, z] + [name] + [file_source] + [hash_key]

    return file_name, row


def one_shot_ref_processing(item, me_keys, vt_keys):
    pt_id = item.id
    file_name = item.file_source
    file_name = one_shot_file_name_to_csv(file_name, me_keys, vt_keys)

    x = item.easting
    y = item.northing
    z = item.elevation
    name = item.target_type
    file_source = item.file_source

    row = [pt_id] + [x, y, z] + [name] + [file_source]

    return file_name, row


def gather_additional_one_shot_wonders(shot_group):
    """
    One shot wonders that are disguised as points with multiple shots
    because they are duplicates of other points.

    """

    pt_collector = {}
    """
        for i, item in enumerate(shot_group):

        key = list(item.keys())[0]

        new_key = f'{key}_{i}'
        shot_group[i][new_key] = shot_group[i][key]
        del shot_group[i][key]
    """

    shot_combinations = list(itertools.combinations(shot_group, 2))

    for p1, p2 in shot_combinations:

        p1_key, p1_values = list(p1.items())[0]
        p2_key, p2_values = list(p2.items())[0]

        pos_dist = math.sqrt((p1_values.easting - p2_values.easting) ** 2
                             + (p2_values.northing - p2_values.northing) ** 2)
        ht_dist = abs(p1_values.elevation - p2_values.elevation)

        # TODO: What is this for?
        if pos_dist == 0.0 or ht_dist == 0.0:
            pt_collector.update({p1_key: p1_values})

    return pt_collector


def ref_processing(shot_group, me_keys, vt_keys, flag='Engineering'):
    if flag == 'Civil':
        pos_thresh = 0.005
        ht_thresh = 0.002
    else:
        pos_thresh = ht_thresh = 0.002

    shot_combinations = list(itertools.combinations(shot_group, 2))

    pair_wise_ht_collector = []
    pair_wise_pos_collector = []

    # Calculate the distance between each pair of shots
    for p1, p2 in shot_combinations:
        p1_key, p1_values = list(p1.items())[0]
        p2_key, p2_values = list(p2.items())[0]

        pos_dist = math.sqrt((p1_values.easting - p2_values.easting) ** 2
                             + (p2_values.northing - p2_values.northing) ** 2)

        ht_dist = abs(p1_values.elevation - p2_values.elevation)

        pos_deltas = {
            f'{p1_key}|{p2_key}':
                pos_dist}

        pair_wise_pos_collector.append(pos_deltas)

        ht_deltas = {f'{p1_key}|{p2_key}': ht_dist}
        pair_wise_ht_collector.append(ht_deltas)

    pos_key, pos_val = min_from_dict(pair_wise_pos_collector)
    ht_key, ht_val = min_from_dict(pair_wise_ht_collector)

    collector = []
    key_collector = set()

    if pos_val <= pos_thresh:
        pos_good = True
    else:
        pos_good = False
    if ht_val <= ht_thresh:
        ht_good = True
    else:
        ht_good = False

    if pos_good and ht_good:
        print("POS and HT are good")

        for i, item in enumerate(shot_group):
            key = list(item.keys())[0]
            file_name = item[key].file_source
            key_collector = file_name_to_csv(file_name, me_keys, vt_keys, key_collector)
            if key in pos_key.split('|'):
                collector.append(item)
        try:
            file_name_key = f'{list(key_collector)[0]}'
        except IndexError:
            file_name_key = 'misc'

    elif pos_good and not ht_good:

        print("POS is good, HT is bad")
        for i, item in enumerate(shot_group):
            key = list(item.keys())[0]
            file_name = item[key].file_source
            key_collector = file_name_to_csv(file_name, me_keys, vt_keys, key_collector)
            if key in pos_key.split('|'):
                collector.append(item)
        try:
            file_name_key = f'{list(key_collector)[0]}_hit_list'
        except IndexError:
            file_name_key = 'misc'

    elif not pos_good and ht_good:
        print("POS is bad, HT is good")
        for i, item in enumerate(shot_group):
            key = list(item.keys())[0]
            file_name = item[key].file_source
            key_collector = file_name_to_csv(file_name, me_keys, vt_keys, key_collector)
            if key in pos_key.split('|'):
                collector.append(item)
        try:
            file_name_key = f'{list(key_collector)[0]}_hit_list'
        except IndexError:
            file_name_key = 'misc'

    else:
        print("POS and HT are bad")
        for i, item in enumerate(shot_group):
            key = list(item.keys())[0]
            file_name = item[key].file_source
            key_collector = file_name_to_csv(file_name, me_keys, vt_keys, key_collector)
            if key in pos_key.split('|'):
                collector.append(item)
        try:
            file_name_key = f'{list(key_collector)[0]}_hit_list'
        except IndexError:
            file_name_key = 'misc'

    return file_name_key, collector

    # else:
    #    print('Pairwise comparison on different shots')
    #    return None


def cluster_processing(shot_group, pos_thresh=0.0029, ht_thresh=0.0029):
    consolidation_dict = {}
    for shot in shot_group:
        consolidation_dict.update(shot.items())

    shot_combinations = list(itertools.combinations(shot_group, 2))
    no_of_shot_combinations = len(shot_combinations)

    pair_wise_ht_collector = []
    pair_wise_pos_collector = []

    # Calculate the distance between each pair of shots
    for p1, p2 in shot_combinations:
        p1_key, p1_values = list(p1.items())[0]
        p2_key, p2_values = list(p2.items())[0]

        pos_dist = math.sqrt((p1_values.easting - p2_values.easting) ** 2
                             + (p2_values.northing - p2_values.northing) ** 2)

        ht_dist = abs(p1_values.elevation - p2_values.elevation)

        pos_deltas = {
            f'{p1_key}|{p2_key}':
                pos_dist}

        pair_wise_pos_collector.append(pos_deltas)

        ht_deltas = {f'{p1_key}|{p2_key}': ht_dist}
        pair_wise_ht_collector.append(ht_deltas)

    ordered_pos_deltas = sorted(pair_wise_pos_collector, key=lambda x: list(x.values())[0])
    ordered_ht_deltas = sorted(pair_wise_ht_collector, key=lambda x: list(x.values())[0])

    (pos_key, pos_value) = list(ordered_pos_deltas[0].items())[0]
    (ht_key, ht_value) = list(ordered_ht_deltas[0].items())[0]

    # if pos_key != ht_key:
    #    print("The minimum position delta is not the same as the minimum HT delta")

    # else:
    a, b = pos_key.split('|')

    a = consolidation_dict[a]
    b = consolidation_dict[b]

    key_collector = set()

    if pos_value <= pos_thresh:
        pos_good = True
    else:
        pos_good = False
    if ht_value <= ht_thresh:
        ht_good = True
    else:
        ht_good = False

    if pos_good:
        if ht_good:
            print("POS and HT are good")

            a_file_name = a.file_source
            b_file_name = b.file_source

            try:
                file_name_key = f'{list(key_collector)[0]}'
            except IndexError:
                file_name_key = 'misc'

            return file_name_key, (a, b), pos_value, ht_value, a_file_name, b_file_name

        else:
            print("POS is good, HT is bad")
    else:
        if ht_good:
            print("POS is bad, HT is good")
        else:
            print("POS and HT are bad")


def gsheets_ref_processing(shot_group, me_keys, vt_keys, flag='Engineering'):
    consolidation_dict = {}
    for shot in shot_group:
        consolidation_dict.update(shot.items())

    if flag == 'Civil':
        pos_thresh = 0.0059
        ht_thresh = 0.0029
    else:
        pos_thresh = ht_thresh = 0.0035

    shot_combinations = list(itertools.combinations(shot_group, 2))
    no_of_shot_combinations = len(shot_combinations)

    pair_wise_ht_collector = []
    pair_wise_pos_collector = []

    # Calculate the distance between each pair of shots
    for p1, p2 in shot_combinations:
        p1_key, p1_values = list(p1.items())[0]
        p2_key, p2_values = list(p2.items())[0]

        pos_dist = math.sqrt((p1_values.easting - p2_values.easting) ** 2
                             + (p2_values.northing - p2_values.northing) ** 2)

        ht_dist = abs(p1_values.elevation - p2_values.elevation)

        pos_deltas = {
            f'{p1_key}|{p2_key}':
                pos_dist}

        pair_wise_pos_collector.append(pos_deltas)

        ht_deltas = {f'{p1_key}|{p2_key}': ht_dist}
        pair_wise_ht_collector.append(ht_deltas)

    ordered_pos_deltas = sorted(pair_wise_pos_collector, key=lambda x: list(x.values())[0])
    ordered_ht_deltas = sorted(pair_wise_ht_collector, key=lambda x: list(x.values())[0])

    (pos_key, pos_value) = list(ordered_pos_deltas[0].items())[0]
    (ht_key, ht_value) = list(ordered_ht_deltas[0].items())[0]

    if pos_key != ht_key:
        print("The minimum position delta is not the same as the minimum HT delta")

    else:
        a, b = pos_key.split('|')

        a = consolidation_dict[a]
        b = consolidation_dict[b]

        key_collector = set()

        if pos_value <= pos_thresh:
            pos_good = True
        else:
            pos_good = False
        if ht_value <= ht_thresh:
            ht_good = True
        else:
            ht_good = False

        if pos_good:
            if ht_good:
                print("POS and HT are good")

                a_file_name = a.file_source
                b_file_name = b.file_source

                key_collector = file_name_to_csv(a_file_name, me_keys, vt_keys, key_collector)
                key_collector = file_name_to_csv(b_file_name, me_keys, vt_keys, key_collector)

                try:
                    file_name_key = f'{list(key_collector)[0]}'
                except IndexError:
                    file_name_key = 'misc'

                return file_name_key, (a, b), pos_value, ht_value

            else:
                print("POS is good, HT is bad")
        else:
            if ht_good:
                print("POS is bad, HT is good")
            else:
                print("POS and HT are bad")


def remove_incorporated_shots(clust_data):
    no_of_clustered_items = sum([len(item) for item in clust_data.values()])

    one_shot = []
    to_process = []
    """
    A dict
    key of -1 is all the shots that are not grouped with any other shots
    The items in this list that have a numerical quality value are the master shots
    ... and so shouldn't be included.
    """

    # Make a list of dicts to be fed to cluster data
    # Remove the control contaminating the point cloud
    noise_control_counter = 0
    neighbour_control_counter = 0
    already_processed_counter = 0

    # Remove the tertiary control already incorporated into the control
    for k, pts_dict_list in clust_data.items():
        for pts_dict in pts_dict_list:
            # If it's in the noise cluster, and is adjusted,
            # Ignore it, it's already been incorporated
            # If it's in the noise cluster, and is not adjusted,
            # Add it to the one_shot list
            # If it's in a cluster, and has an adjusted point with it, it's been processed
            # If it's in a cluster, and has no adjusted point with it, it's not been processed
            if k == -1:
                for one_shot_control_point in pts_dict.values():
                    if not one_shot_control_point.adjusted:
                        one_shot.append(pts_dict)
                    else:
                        noise_control_counter += 1
            else:
                # for multiple_shot_control_point in pts_dict.values():
                if not any([multiple_shot_control_point.adjusted
                            for multiple_shot_control_point in pts_dict.values()]):
                    to_process.append(pts_dict)
                    neighbour_control_counter += 1
                else:
                    # There is an adjusted point in the cluster, so it's been processed
                    already_processed_counter += 1

    print(f'In the "noise" sub cluster there are {noise_control_counter} control points that\n'
          f'do not have tertiary control within 10mms, meaning they are either\nprimary or secondary control,'
          f' or tertiary control that has already been incorporated into the master control file')

    print('-' * 50)

    print(f'In the "neighbour" sub clusters there were {neighbour_control_counter} clusters that'
          f' did not have adjusted control within 10mms, totalling {len(to_process)} points to be re-clustered\n')

    print(f'In the "neighbour" sub clusters there were {already_processed_counter} tertiary points that'
          f' had adjusted control within 10mms,\nsuggesting they have already been transformed into'
          f' a master control point, and would otherwise be\nredundantly re-processed if not removed,'
          f' along with the adjusted control in the cluster.')

    # assert len(one_shot) + len(to_process) == no_of_clustered_items - noise_control_counter - neighbour_control_counter
    print(f'There are {len(one_shot)} shots that will go straight into a "hit list" file')
    print(f'There are {len(to_process)} shots that will be re-clustered and processed')
    # for item in to_process:
    #    print(item)

    return one_shot, to_process


def remove_incorporated_shots_testing(clust_data):
    to_process = {}
    one_shot = {}

    for k, v in clust_data.items():  # k is the cluster number, v is the list of dicts

        for i, item in enumerate(v):  # i is the index of the dict in the list, item is the dict
            pt_id, pt = list(item.items())[0]
            if k == -1:
                if not pt.adjusted:
                    hash_key = create_hash(pt.easting, pt.northing, pt.elevation)
                    one_shot.update({hash_key: pt})
            else:
                if not any([clustered_shot.adjusted for clustered_shot in item.values()]):
                    hash_key = create_hash(pt.easting, pt.northing, pt.elevation)
                    to_process.update({hash_key: pt})

    return one_shot, to_process





