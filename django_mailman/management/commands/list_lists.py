# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Rodolphe Quiédeville <rodolphe@quiedeville.org>
#
"""
List all lists
"""
from django.core.management.base import BaseCommand
from django_mailman.models import List


class Command(BaseCommand):
    help = 'List all lists with their url on stdout'

    def handle(self, *args, **options):
        for olist in List.objects.all():
            self.stdout.write("%s - %s\n" % (olist.name,
                                             olist.main_url))
