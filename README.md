# Cutout service

## Overview

This repo contains the source code and a Docker Compose deployment configuration for an application that generates cutouts of astronomical data images. The core application component is the Django-based API server and web frontend, which acts as model, view, and controller in the MVC architectural pattern. Asynchronous tasks are executed by a scalable workflow management system based on Celery.

## Developers

See `docs/developer.md` to learn how to run locally and develop the application.
