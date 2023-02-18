from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.html import escape


def index(request):
    return render(request, 'main/index.html')

def funky(request):
    return HttpResponseRedirect('https://www.dj4e.com/simple.htm')
