from django.http import HttpResponseRedirect # HttpResponse
# from django.utils.html import escape
from django.shortcuts import render
from .forms import UploadFileForm
import os

from .analyze import Analyzer
from .local_vars import image_dir_prefix


def index(request):
    context = {'form': UploadFileForm(), 'not_gamelog': request.session.get('not_gamelog', False)}
    request.session['not_gamelog'] = False
    return render(request, 'analyzer/index.html', context)


def upload(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            data = str(request.FILES['file'].read())
            if 'Gamelog' in data:
                request.session['data'] = data[2:-1]
                return HttpResponseRedirect('/analyzer/output')
            else:
                request.session['not_gamelog'] = True
                return HttpResponseRedirect('/analyzer')
    else:
        form = UploadFileForm()
    return render(request, 'analyzer/index.html', {'form': form})


def output(request):
    if 'data' not in request.session.keys():
        return HttpResponseRedirect('/analyzer')
    with os.scandir(image_dir_prefix + 'main/static/main/images') as it:
        for entry in it:
            if 'chart' in entry.name:
                os.remove(entry)
    analyzer = Analyzer(request.session['data'])
    context = analyzer.context
    context['form'] = UploadFileForm()
    return render(request, 'analyzer/output.html', context)


def example(request):
    with open(image_dir_prefix + 'analyzer/resources/example-log.txt', 'r') as f:
        request.session['data'] = f.read()
        return HttpResponseRedirect('/analyzer/output')
