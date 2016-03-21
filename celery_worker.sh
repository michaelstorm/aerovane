#!/bin/bash
celery -A multicloud worker --concurrency 4 -l info -B -E
#celery -A multicloud worker --concurrency 1 -l info -E # concurrency defaults to number of available cores
