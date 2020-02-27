from __future__ import unicode_literals
# -*- coding: utf-8 -*-

from django.forms import ModelForm, TextInput
from .models import List

class ListForm(ModelForm):
    class Meta:
        fields = '__all__'
        model = List
        widgets = {
            'password': TextInput(attrs={'style':'font-family:monospace'}),
        }
