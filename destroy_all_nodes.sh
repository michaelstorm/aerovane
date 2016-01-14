#!/bin/bash
echo "[pc._destroy_all_nodes() for pc in ProviderConfiguration.objects.all()]" | python manage.py shell_plus
