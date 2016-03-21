#!/bin/bash
celery -A multicloud beat # concurrency defaults to number of available cores
