from celery.task.schedules import crontab
from celery.decorators import periodic_task

from datetime import timedelta

from multicloud.celery import app

from .models import *

@app.task()
def load_available_images(provider_configuration_id):
    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    provider_configuration.load_available_images()


@periodic_task(run_every=timedelta(seconds=30))
def update_instance_statuses():
    for provider_configuration in ProviderConfiguration.objects.all():
        provider_configuration.update_instance_statuses()
