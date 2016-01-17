#!/bin/bash
celery -A multicloud worker --concurrency 4 -l info -B -E
