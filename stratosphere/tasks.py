from multicloud.celery import app

from .models import *

@app.task()
def load_available_images(provider_configuration_id):
    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    provider_configuration.load_available_images()
