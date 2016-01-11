#!/bin/bash
celery -A multicloud worker -l info -B
