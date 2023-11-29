from django.shortcuts import render
from .forms import FileUploadForm
from .models import TertiaryControlFile
from .utilities.process_files import create_control_point_objects, adjust_tertiary_control_points, create_internet_zip, write_to_report_csv
import time

def file_upload_view(request):
    collector = []
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist('files')
            hz_tol = form.cleaned_data['horizontal_tolerance']

            vt_tol = form.cleaned_data['vertical_tolerance']
            report_name = form.cleaned_data['report_name']
            for file in files:
                uploaded_file = TertiaryControlFile(file=file)
                file_hash = uploaded_file.save()
                time.sleep(1)
                if file_hash is not None:
                    uploaded_file = TertiaryControlFile.objects.get(file_hash=file_hash)

                print(uploaded_file.file.path)

                collector.extend(create_control_point_objects(uploaded_file)) # Replace with your processing function
            # Redirect or respond after processing
            #return render(request, 'upload.html', {'form': form, 'collector': collector})
            #for item in collector:
            #    print(item)
            report, one_shot, proposed_rows = adjust_tertiary_control_points(collector, hz_tol, vt_tol)
            report_csv = write_to_report_csv(report)
            one_shot_csv = write_to_report_csv(one_shot)
            proposed_csv = write_to_report_csv(proposed_rows)
            return(create_internet_zip(report_csv, one_shot_csv, proposed_csv, report_name))
    else:
        form = FileUploadForm()
    return render(request, 'upload.html', {'form': form})
