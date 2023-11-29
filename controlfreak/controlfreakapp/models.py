import os
import hashlib
import base64
import datetime
import re
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from datetime import datetime
# Create your models here.

from django.db import models
from django.core.files import File
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from django.db.models import UniqueConstraint
BASE_DIR = settings.BASE_DIR

def extract_and_convert_to_date(file_name):
    pattern = r"\b\d{6}\b"  # Regular expression pattern for six consecutive digits
    match = re.search(pattern, file_name)
    if match:
        date_string = match.group(0)
        try:
            date = datetime.strptime(date_string, "%y%m%d").date()
            return date

        except ValueError:
            print("Invalid date format: Should be YYMMDD."
                  " C'mon. You're better than this")

            return None
    else:
        return None


def unique_filename(path):
    """
    Enforce unique upload file names.
    Usage:
    class MyModel(models.Model):
        file = ImageField(upload_to=unique_filename("path/to/upload/dir"))
    """

    def _func(instance, filename):
        name, ext = os.path.splitext(filename)
        name = base64.urlsafe_b64encode(name.encode("utf-8") + str(datetime.datetime.now()))
        return os.path.join(path, name + ext)

    return _func


# TODO refactor - this function is duplicated in views
def calculate_file_hash(file):
    hasher = hashlib.md5()
    # Read the file in chunks to conserve memory

    for chunk in file.chunks():
        hasher.update(chunk)
    return hasher.hexdigest()


def calculate_file_hash_io(file, algorithm='md5'):
    hash_obj = hashlib.new(algorithm)
    for chunk in iter(lambda: file.read(4096), b""):
        hash_obj.update(chunk)
    file.seek(0)  # Reset file pointer to beginning
    return hash_obj.hexdigest()


# TODO refactor - this function is duplicated in views
def get_revision(filename):
    pattern = r"\b\d{3}\b"  # Regular expression pattern for three consecutive digits
    match = re.search(pattern, filename)
    if match:
        return match.group(0)
    else:
        return "000"


def get_tertiary_upload_path(instance, file_path):
    return os.path.join(
        "tertiary_control",
        os.path.basename(file_path)
    )

class TertiaryControlFile(models.Model):
    file = models.FileField()
    revision = models.IntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_hash = models.CharField(max_length=32, unique=True, null=True, blank=True)
    observation_date = models.DateField(null=True, blank=True)

    @staticmethod
    def delete_original_control(sender, instance, **kwargs):
        instance.file.delete(save=False)


    @staticmethod
    def pre_save_control(sender, instance, **kwargs):
        try:
            old_file = sender.objects.get(pk=instance.pk).file.path
            new_file = instance.file.path if instance.file else None
            if old_file != new_file and os.path.exists(old_file):
                os.remove(old_file)

        except ObjectDoesNotExist:
            pass

    def save(self, *args, **kwargs):
        # with open(self.file.path, 'rb') as f:
        file_hash = calculate_file_hash_io(self.file)
        # The files that have the same name but different contents
        duplicate_files = self.__class__.objects.filter(file_hash=file_hash)

        # If there is an identical file, skip it.
        if duplicate_files.exists():
            print("Duplicate file detected.")
            return file_hash
        else:
            self.file_hash = file_hash
            self.observation_date = extract_and_convert_to_date(self.file.name)
            super().save(*args, **kwargs)

    def __str__(self):
        try:
            return f'{os.path.basename(self.file.name)} {f"- {self.revision}" if self.revision else " "}'
        except TypeError:
            return 'WTF'


post_delete.connect(TertiaryControlFile.delete_original_control, sender=TertiaryControlFile)

class ReflectorType(models.Model):
    reflector_type_id = models.IntegerField(null=True, blank=True)
    reflector_type_name = models.CharField(max_length=50, null=True, blank=True)
    reflector_constant = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.reflector_type_name


class InstrumentMeasureStyle(models.Model):
    instrument_measure_style_id = models.IntegerField(null=True, blank=True)
    instrument_measure_style_name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.instrument_measure_style_name


class InstrumentSettings(models.Model):
    instrument_settings_id = models.IntegerField(null=True, blank=True)
    instrument_settings_name = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.instrument_settings_name


COORD_FLAVOURS = (
    ('AD', 'Adjusted'),
    ('ME', 'Averaged'),
    ('RW', 'Raw'),
    ('HM', 'Helmert'),
    ('OP', 'Over Point'),
    ('BS', 'Backsite')
)


class Coordinates(models.Model):
    easting = models.DecimalField(max_digits=20, decimal_places=8)
    northing = models.DecimalField(max_digits=20, decimal_places=8)
    elevation = models.DecimalField(max_digits=20, decimal_places=8)
    flavour = models.CharField(max_length=2, choices=COORD_FLAVOURS, null=True, blank=True)

    def __str__(self):
        return f"{self.easting} {self.northing} {self.elevation}, {self.flavour}"


class HelmertResection(models.Model):
    # TODO: establish accurate max_digits
    helmert_id = models.CharField(max_length=15)
    source_file = models.ForeignKey(TertiaryControlFile,
                                    on_delete=models.CASCADE,
                                    related_name='helmert_resections',
                                    null=True,
                                    blank=True)
    setup_type = models.CharField(max_length=50, null=True, blank=True)

    coordinates = models.ForeignKey(
        Coordinates,
        on_delete=models.CASCADE,
        related_name='helmert_resections',
        null=True,
        blank=True
    )

    origin_elevation = models.DecimalField(max_digits=20, decimal_places=3)
    instrument_height = models.DecimalField(max_digits=20, decimal_places=3)
    bearing_swing = models.DecimalField(max_digits=20, decimal_places=3)
    utc_time = models.DateTimeField()
    pos_error = models.DecimalField(max_digits=20, decimal_places=3)
    scale_factor = models.DecimalField(max_digits=6, decimal_places=5)
    level_diff = models.DecimalField(max_digits=20, decimal_places=3)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['helmert_id', 'coordinates'], name='helmert_id_coordinates')
        ]

    @classmethod
    def count_unique_coordinates(cls):
        return cls.objects.values('coordinates').distinct().count()

    def __str__(self):
        return self.helmert_id


class OverPointStationSetup(models.Model):
    ops_id = models.CharField(max_length=15)
    setup_type = models.CharField(max_length=50, null=True, blank=True)

    coordinates = models.ForeignKey(
        Coordinates,
        on_delete=models.CASCADE,
        related_name='otp_station_setups',
        null=True,
        blank=True
    )

    origin_elevation = models.DecimalField(max_digits=20, decimal_places=3)
    instrument_height = models.DecimalField(max_digits=20, decimal_places=3)
    bearing_swing = models.DecimalField(max_digits=20, decimal_places=3)
    utc_time = models.DateTimeField()
    bs_id = models.CharField(max_length=15)

    bs_coordinates = models.ForeignKey(
        Coordinates,
        on_delete=models.CASCADE,
        related_name='otp_station_setups_bs',
        null=True,
        blank=True
    )

    bs_calc_elevation = models.DecimalField(max_digits=20, decimal_places=3)
    bs_elevation_delta = models.DecimalField(max_digits=20, decimal_places=3)
    bs_easting_delta = models.DecimalField(max_digits=20, decimal_places=3)
    bs_northing_delta = models.DecimalField(max_digits=20, decimal_places=3)
    bs_diff_z = models.DecimalField(max_digits=20, decimal_places=3)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['ops_id', 'coordinates', 'bs_coordinates'], name='ops_id_coordinates')
        ]

    def __str__(self):
        return self.ops_id


class ResectionPoint(models.Model):
    resection = models.ForeignKey(HelmertResection, on_delete=models.CASCADE)
    helm_id = models.CharField(max_length=15)
    model_name = models.CharField(max_length=50, null=True, blank=True)
    target_type = models.CharField(max_length=50, null=True, blank=True)

    coordinates = models.ForeignKey(
        Coordinates,
        on_delete=models.CASCADE,
        related_name='resection_points',
        null=True,
        blank=True
    )

    use_pos = models.BooleanField()
    use_ht = models.BooleanField()
    pos_error = models.DecimalField(max_digits=20, decimal_places=3, null=True, blank=True)

    tps_reflector_type = models.ForeignKey(
        ReflectorType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    tps_measure_style = models.ForeignKey(
        InstrumentMeasureStyle,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    tps_settings = models.ForeignKey(
        InstrumentSettings,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    def __str__(self):
        return f'{self.helm_id} used in resection {self.resection.helmert_id}'


class ControlPointModel(models.Model):
    class Meta:
        abstract = True

    control_id = models.CharField(max_length=15, null=True, blank=True)
    target_type = models.CharField(max_length=15, null=True, blank=True)
    horizontal_quality = models.IntegerField()
    vertical_quality = models.IntegerField()
    adjusted = models.BooleanField()

    def __str__(self):
        return self.control_id


class UnAdjustedTertiaryControlPoint(ControlPointModel):
    source = models.ForeignKey(TertiaryControlFile, on_delete=models.CASCADE)
    resection = models.ForeignKey(HelmertResection, on_delete=models.CASCADE, null=True, blank=True)
    otp_setup = models.ForeignKey(OverPointStationSetup, on_delete=models.CASCADE, null=True, blank=True)

    coordinates = models.ForeignKey(
        Coordinates,
        on_delete=models.CASCADE,
        related_name='un_adjusted_control_points',
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=['resection', 'coordinates','source'], name='resection_coordinates')
        ]

    def __str__(self):
        return self.control_id

#
# class AdjustedControlPoint(ControlPointModel):
#     source = models.ForeignKey(AdjustedControlFile, on_delete=models.CASCADE)
#     coordinates = models.ForeignKey(
#         Coordinates,
#         on_delete=models.CASCADE,
#         related_name='adjusted_control_points',
#         null=True,
#         blank=True
#     )
#
#     def __str__(self):
#         try:
#             return str(self.source)
#         except TypeError:
#             return 'Adjusted Control Point'
#
#
class AveragedTertiaryControlPoint(models.Model):
    control_id = models.CharField(max_length=15, null=True, blank=True)
    target_type = models.CharField(max_length=15, null=True, blank=True)
    horizontal_quality = models.IntegerField()
    vertical_quality = models.IntegerField()

    a_seed = models.ForeignKey(
        UnAdjustedTertiaryControlPoint,
        on_delete=models.CASCADE,
        related_name='a_seed',
        null=True,
        blank=True
    )

    b_seed = models.ForeignKey(
        UnAdjustedTertiaryControlPoint,
        on_delete=models.CASCADE,
        related_name='b_seed',
        null=True,
        blank=True
    )

    coordinates = models.ForeignKey(
        Coordinates,
        on_delete=models.CASCADE,
        related_name='averaged_control_points',
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=['a_seed', 'b_seed', 'coordinates'], name='a_seed_b_seed_coordinates')
        ]

    def __str__(self):
        return self.control_id

