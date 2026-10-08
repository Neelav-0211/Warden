"""Spec 04 import compatibility; implementation lives in backends.celery."""

from common.queue.backends.celery import CeleryQueueConsumer, CeleryQueueProducer

__all__ = ["CeleryQueueConsumer", "CeleryQueueProducer"]
