from django import forms

class FileUploadForm(forms.Form):
    horizontal_tolerance = forms.FloatField(label='Hz Tolerance required (mm)')
    vertical_tolerance = forms.FloatField(label='Vz Tolerance required (mm)')
    report_name = forms.CharField(label='Output report name')
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))
