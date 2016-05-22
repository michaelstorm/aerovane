from django.db import transaction
from django.utils import timezone

import libcloud.common.types

from ..models import ProviderCredentialSet, ProviderImage, ProviderSize, DiskImage

import json
import traceback
import uuid


class ProviderConfigurationDataLoader(object):
    _ecus_by_id = {
        'aws': {
            'c1.medium': 5,
            'c1.xlarge': 20,
            'c3.2xlarge': 28,
            'c3.4xlarge': 55,
            'c3.8xlarge': 108,
            'c3.large': 7,
            'c3.xlarge': 14,
            'c4.2xlarge': 31,
            'c4.4xlarge': 62,
            'c4.8xlarge': 132,
            'c4.large': 8,
            'c4.xlarge': 16,
            'cc2.8xlarge': 88,
            'cg1.4xlarge': 33.5,
            'cr1.8xlarge': 88,
            'd2.2xlarge': 28,
            'd2.4xlarge': 56,
            'd2.8xlarge': 116,
            'd2.xlarge': 14,
            'g2.2xlarge': 26,
            'g2.8xlarge': 104,
            'hi1.4xlarge': 35,
            'hs1.8xlarge': 35,
            'i2.2xlarge': 27,
            'i2.4xlarge': 53,
            'i2.8xlarge': 104,
            'i2.xlarge': 14,
            'm1.large': 4,
            'm1.medium': 2,
            'm1.small': 1,
            'm1.xlarge': 8,
            'm2.2xlarge': 13,
            'm2.4xlarge': 26,
            'm2.xlarge': 6.5,
            'm3.2xlarge': 26,
            'm3.large': 6.5,
            'm3.medium': 3,
            'm3.xlarge': 13,
            'm4.10xlarge': 124.5,
            'm4.2xlarge': 26,
            'm4.4xlarge': 53.5,
            'm4.large': 6.5,
            'm4.xlarge': 13,
            'r3.2xlarge': 26,
            'r3.4xlarge': 52,
            'r3.8xlarge': 104,
            'r3.large': 6.5,
            'r3.xlarge': 13,
            't1.micro': 0,
            't2.large': 0,
            't2.medium': 0,
            't2.micro': 0,
            't2.nano': 0,
            't2.small': 0
        }
    }

    def load_data(self, include_public):
        self._load_available_sizes()
        self._load_available_images(include_public)

    def _load_available_sizes(self):
        driver_sizes = self.driver.list_sizes()
        provider_size_ids = set(self.provider_sizes.values_list('id', flat=True))

        for driver_size in driver_sizes:
            if driver_size.id.startswith('t'):
                # TODO this Amazon-specific
                # t* instance types can only be used in VPCs
                continue

            provider_size = ProviderSize.objects.filter(external_id=driver_size.id, provider_configuration=self).first()
            if provider_size is None:
                provider_size = ProviderSize(external_id=driver_size.id, provider_configuration=self)
            else:
                provider_size_ids.remove(provider_size.pk)

            provider_size.name = driver_size.name
            provider_size.price = driver_size.price
            provider_size.ram = driver_size.ram
            provider_size.disk = driver_size.disk
            provider_size.cpu = self._ecus_by_id['aws'][driver_size.id] # TODO this is Amazon-specific
            provider_size.bandwidth = driver_size.bandwidth
            provider_size.extra = json.loads(json.dumps(driver_size.extra))

            provider_size.save()

        # remaining elements of provider_size_ids are those elements deleted remotely
        ProviderSize.objects.filter(pk__in=provider_size_ids).delete()

    def _get_driver_images(self, include_public):
        return self.driver.list_images()

    # TODO locally delete images deleted remotely
    def _load_available_images(self, include_public, driver_images_limit=None, row_retrieval_chunk_size=100):
        def driver_image_name(driver_image):
            return driver_image.name

        def get_provider_images_by_external_id(driver_images):
            driver_image_ids = [driver_image.id for driver_image in driver_images]
            provider_images = ProviderImage.objects.filter(provider=self.provider,
                                                           external_id__in=driver_image_ids)
            return {provider_image.external_id: provider_image for provider_image in provider_images}

        import itertools
        def grouper(n, iterable):
            it = iter(iterable)
            while True:
               chunk = tuple(itertools.islice(it, n))
               if not chunk:
                   return
               yield chunk

        def handle_load_error(error_type):
            print('Caught exception while loading provider images for %s:\n%s' % (self.pk, traceback.format_exc()))
            with transaction.atomic():
                self.data_state = self.ERROR
                self.save()

                self.provider_credential_set.error_type = error_type
                self.provider_credential_set.save()

        try:
            print('Querying images for provider %s' % self.provider.name)
            start = timezone.now()

            try:
                driver_images = self._get_driver_images(include_public)

            except Exception as e:
                if isinstance(e, libcloud.common.types.InvalidCredsError):
                    error_type = ProviderCredentialSet.INVALID_CREDENTIALS
                elif isinstance(e, libcloud.common.exceptions.BaseHTTPError) and e.message.startswith('UnauthorizedOperation'):
                    error_type = ProviderCredentialSet.UNAUTHORIZED_CREDENTIALS
                else:
                    error_type = ProviderCredentialSet.UNAUTHORIZED_CREDENTIALS

                handle_load_error(error_type)
                return

            end = timezone.now()
            print('Retrieved %d images in %s' % (len(driver_images), (end - start)))

            filtered_driver_images = list(driver_images)
            if driver_images_limit is not None:
                filtered_driver_images = filtered_driver_images[:driver_images_limit]

            print('Scanning driver and updating provider images...')
            start = timezone.now()

            modified, scanned = 0, 0
            new_driver_images_by_provider_id = {}
            for driver_images_chunk in grouper(row_retrieval_chunk_size, filtered_driver_images):
                provider_images_by_external_id = get_provider_images_by_external_id(driver_images_chunk)

                for driver_image in driver_images_chunk:
                    provider_image = provider_images_by_external_id.get(driver_image.id)
                    if provider_image is None:
                        new_provider_id = uuid.uuid4()
                        new_driver_images_by_provider_id[new_provider_id] = driver_image
                    else:
                        provider_image.extra = json.loads(json.dumps(driver_image.extra))

                        if provider_image.has_changed:
                            modified += 1
                            provider_image.save()

                scanned += len(driver_images_chunk)

            end = timezone.now()
            print('Scanned %d driver images and modified %d ProviderImages in %s' %
                  (len(filtered_driver_images), modified, end - start))

            with transaction.atomic():
                new_driver_image_names = {driver_image: driver_image.name
                                          for driver_image in new_driver_images_by_provider_id.values()}

                print('Creating DiskImages...')
                start = timezone.now()

                new_disk_images_by_provider_id = {new_provider_id: DiskImage(name=new_driver_image_names[driver_image])
                                                  for new_provider_id, driver_image in new_driver_images_by_provider_id.items()}
                DiskImage.objects.bulk_create(new_disk_images_by_provider_id.values())

                end = timezone.now()
                print('Created %d DiskImages in %s' % (len(new_disk_images_by_provider_id), end - start))

                print('Creating ProviderImages...')
                start = timezone.now()

                new_provider_images = [ProviderImage(id=new_provider_id,
                                                     provider=self.provider,
                                                     external_id=driver_image.id,
                                                     name=new_driver_image_names[driver_image],
                                                     extra=json.loads(json.dumps(driver_image.extra)),
                                                     disk_image=new_disk_images_by_provider_id[new_provider_id])
                                       for new_provider_id, driver_image in new_driver_images_by_provider_id.items()]
                ProviderImage.objects.bulk_create(new_provider_images)

                end = timezone.now()
                print('Created %d ProviderImages in %s' % (len(new_provider_images), end - start))

                print('Linking ProviderImages to DiskImages...')
                start = timezone.now()

                scanned, linked, unlinked = 0, 0, 0
                new_driver_images = new_driver_images_by_provider_id.values()
                for driver_images_chunk in grouper(row_retrieval_chunk_size, filtered_driver_images):
                    provider_images_by_external_id = get_provider_images_by_external_id(driver_images_chunk)

                    for driver_image in driver_images_chunk:
                        provider_image = provider_images_by_external_id[driver_image.id]

                        # TODO this is Amazon-specific
                        if provider_image.extra.get('is_public'):
                            unlinked += 1
                            provider_image.provider_configurations.remove(self)
                        else:
                            linked += 1
                            provider_image.provider_configurations.add(self)

                    scanned += len(driver_images_chunk)

                end = timezone.now()
                print('Scanned %d ProviderImages, linked %d, unlinked %d to DiskImages in %s' %
                      (scanned, linked, unlinked, end - start))

        except:
            handle_load_error(None)
        else:
            self.data_state = self.LOADED
            self.save()
