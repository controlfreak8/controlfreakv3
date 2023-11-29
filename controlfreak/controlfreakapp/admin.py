from django.contrib import admin
from django.db.models import Count, CharField
from .models import HelmertResection, ResectionPoint, TertiaryControlFile, UnAdjustedTertiaryControlPoint, Coordinates, AveragedTertiaryControlPoint
from . utilities import geometry_manipulation as gm
from . utilities.CONSTANTS import ControlPoint
from statistics import mean
import math
import csv
from io import BytesIO, StringIO
import zipfile
from django.http import HttpResponse

class ResectionPointInline(admin.TabularInline):
    model = ResectionPoint
    extra = 0

# Register your models here.
@admin.register(HelmertResection)
class HelmertResectionAdmin(admin.ModelAdmin):
    inlines = [ResectionPointInline, ]
    list_display = (
        'helmert_id',
        'pos_error',
        'scale_factor',
        'resection_point_count',
        'source_file',
        #'observation_date',
    )

    def observation_date(self, obj):
        return obj.source_file.observation_date

    observation_date.short_description = 'Observation Date'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _resection_point_count=Count('resectionpoint')
        )
        return queryset

    def resection_point_count(self, obj):
        return obj._resection_point_count

@admin.register(TertiaryControlFile)
class TertiaryControlFileAdmin(admin.ModelAdmin):
    model = TertiaryControlFile
    list_display = (
        'file',
        'uploaded_at',
        'observation_date',
        'file_hash'
    )

class HelmertResectionInline(admin.TabularInline):
    model = HelmertResection
    extra = 0

def write_to_report_csvss(rows):
    # fieldnames = ['Proposed Name', 'Target Type', 'Easting', 'Northing', 'Elevation',
    #               'Point A Name', 'Point A Source', 'Point A Resection',
    #                'Pos Error', 'Scale Factor', 'Hz delta',
    #               'Point B Name', 'Point B Source', 'Point B Resection',
    #                'Pos Error', 'Scale Factor', 'Hz delta']

    with open('data.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # writer.writerow(fieldnames) # write the header
        for row in rows:
            writer.writerow(row)

def write_to_report_csv(rows):

    output = StringIO()
    writer = csv.writer(output)
    # writer.writerow(fieldnames) # write the header
    for row in rows:
        writer.writerow(row)

    return output.getvalue()

def adjust_tertiary_control_points(queryset) -> None:
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

    clustered = gm.cluster_data(tertiary_control, euclidean_dist=0.0029)
    one_shot, to_process = gm.remove_incorporated_shots_testing(clustered)

    noise, shots_to_investigate = gm.cluster_data_split_noise(to_process, euclidean_dist=0.0029)

    for cp_list in noise.values():
        for cp_dict in cp_list:
            one_shot.update(cp_dict)
    print(f'There are {len(one_shot)} one shot wonders to process.')
    print(one_shot)

    print(f'There are {len(shots_to_investigate)} shots to investigate.')
    rows = []
    for i, (label, shots) in enumerate(shots_to_investigate.items()):
        print(i)
        res = gm.cluster_processing(shots, pos_thresh=0.0029, ht_thresh=0.0029)
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
            print(best_code, best_name, averages, a.id, a.file_source, b.id, b.file_source)

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
                    print(f'Created {proposed_control}')
                else:
                    print(f'Already exists {proposed_control}')

                print(a_seed, a_seed.source, a_seed.resection, a_seed.otp_setup)
                print(b_seed, b_seed.source, b_seed.resection, b_seed.otp_setup)

                if a_seed.resection is None:
                    a_setup_id = a_seed.otp_setup.ops_id
                    a_pos_error = 'TBC'
                    a_scale_factor = 'TBC'
                    a_level_diff = a_seed.otp_setup.bs_elevation_delta
                else:
                    a_resection_coords = [(rp.helm_id, rp.target_type, rp.model_name) for rp in a_seed.resection.resectionpoint_set.all()]
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
                    b_resection_coords =  [(rp.helm_id, rp.target_type, rp.model_name) for rp in b_seed.resection.resectionpoint_set.all()]
                    b_setup_id = b_seed.resection.helmert_id
                    b_pos_error = b_seed.resection.pos_error
                    b_scale_factor = b_seed.resection.scale_factor
                    b_level_diff = b_seed.resection.level_diff

                proposed_cp_row = (pc.control_id, pc.coordinates.easting, pc.coordinates.northing, pc.coordinates.elevation, pc.target_type)
                # Resection / OTP setup for control point shot.
                a_seed_row = [a_seed.control_id, a.easting, a.northing, a.elevation, a_seed.target_type]
                b_seed_row = [b_seed.control_id, b.easting, b.northing, b.elevation, b_seed.target_type]

                a_setup_row = [a_setup_id, a_pos_error, a_scale_factor, a_level_diff, a_seed.source]
                b_setup_row = [b_setup_id, b_pos_error, b_scale_factor, b_level_diff, b_seed.source]

                a_b_deltas_row = ['','', math.sqrt((a.easting - b.easting)**2 + (a.northing - b.northing)**2), a.elevation - b.elevation]

                rows.append(['Proposed Name', 'Easting', 'Northing', 'Elevation', 'Target Type'])
                rows.append(proposed_cp_row)
                rows.append([" "])

                rows.append(['', 'A-B Deltas:', 'Hz Euclidian', 'Vz Delta'])
                rows.append(a_b_deltas_row)
                rows.append([" "])

                rows.append(['Seed A Name', 'Easting', 'Northing', 'Elevation','Target Type'])
                rows.append(a_seed_row)
                rows.append([''])
                rows.append(['', 'Resection', 'Pos Error', 'Scale Factor', 'Level Delta', 'Source'])

                rows.append([''] + a_setup_row)
                rows.append([''])
                rows.append(['', ''] +['Resection Points'])
                rows.append(['', '']+ ['Name', 'Quality','', 'Source'])
                for (name, quality, source) in a_resection_coords:
                    rows.append(['', '']+ [name, quality, '', source])

                rows.append([" "])
                rows.append(['Seed B Name', 'Easting', 'Northing', 'Elevation','Target Type'])
                rows.append(b_seed_row)
                rows.append([''])
                rows.append(['', 'Resection', 'Pos Error', 'Scale Factor', 'Level Delta', 'Source'])
                rows.append([''] + b_setup_row)
                rows.append([''])
                rows.append(['', ''] + ['Resection Points'])
                rows.append(['', ''] + ['Name', 'Quality','', 'Source'])

                for (name, quality, source) in b_resection_coords:
                    rows.append(['', ''] + [name, quality, '', source])

                rows.append([" "])
                rows.append([" "])

            except UnAdjustedTertiaryControlPoint.DoesNotExist:
                pass

    return write_to_report_csv(rows)

def create_internet_zip(data_str):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zip_file:
        zip_file.writestr('data.csv', data_str)

    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=my_zip.zip'

    # Important: close the buffer
    buffer.close()

    return response

from django.contrib.admin import SimpleListFilter

class MultipleSourceFileFilter(SimpleListFilter):
    title = 'source file'  # or use _('source file') for i18n
    parameter_name = 'source_file'

    def lookups(self, request, model_admin):
        # Assuming `source_file` is a field in `resection` model.
        # Adjust the query as needed for your models.
        source_files = set([c.source_file for c in HelmertResection.objects.all()])
        print(source_files)
        return [(sf.id, sf.file.name) for sf in source_files]

    def queryset(self, request, queryset):
        if self.value():
            print(queryset)
            return queryset.filter(resection__source_file__in=self.value().split(','))
        return queryset

class ResectionOrOtpSetupFilter(SimpleListFilter):
    title = 'Source File'
    parameter_name = 'source_file'

    def lookups(self, request, model_admin):
        # Define lookups here - you might need to combine values from both resection and otp_setup
        pass

    def queryset(self, request, queryset):
        if self.value():
            # Apply filtering logic for both resection and otp_setup
            pass
        return queryset

from django_admin_multi_select_filter.filters import MultiSelectFieldListFilter

@admin.register(UnAdjustedTertiaryControlPoint)
class UnAdjustedTertiaryControlPointAdmin(admin.ModelAdmin):
    list_display = (
        'control_id',
        'target_type',
        'show_resection',
        'resection_points'
    )

    list_select_related = ('resection',)

    #list_filter = ('resection__source_file__id',)
    list_filter = ('resection__source_file',)
    #list_filter = (('resection', MultiSelectFieldListFilter,))


    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('resection')
        return queryset

    def show_resection(self, obj):
        try:
            try:
                return obj.resection.helmert_id
            except AttributeError:
                return "No Resection"

        except AttributeError:
            try:
                return obj.otp_setup.ops_id
            except AttributeError:
                return "No OTP Setup"

    def resection_points(self, obj):
        try:
            return ", ".join([f'{rp.helm_id} {rp.target_type}' for rp in obj.resection.resectionpoint_set.all()])

            #return obj.resection.resectionpoint_set.all()
        except AttributeError:
            try:
                return obj.otp_setup.bs_id
            except AttributeError:
                return "What is happening here?"

    actions = ['adjust_selected']

    def adjust_selected(self, request, queryset):
        return create_internet_zip(adjust_tertiary_control_points(queryset))

admin.site.register(AveragedTertiaryControlPoint)
