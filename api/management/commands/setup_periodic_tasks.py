from django.core.management.base import BaseCommand
from django.conf import settings
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
from celery.schedules import crontab
from datetime import timedelta

class Command(BaseCommand):
    help = 'Sync settings.CELERY_BEAT_SCHEDULE to django-celery-beat database models'

    def handle(self, *args, **options):
        self.stdout.write('Syncing Celery Beat Schedule to database...')
        
        beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        
        for name, entry in beat_schedule.items():
            task_name = entry['task']
            schedule = entry['schedule']
            
            interval = None
            crontab_sched = None
            
            if isinstance(schedule, timedelta):
                seconds = int(schedule.total_seconds())
                interval, _ = IntervalSchedule.objects.get_or_create(
                    every=seconds,
                    period=IntervalSchedule.SECONDS
                )
            elif isinstance(schedule, crontab):
                # Helper to convert crontab elements to string representation
                def clean_element(element):
                    if isinstance(element, set):
                        return ','.join(map(str, element))
                    return str(element)
                
                crontab_sched, _ = CrontabSchedule.objects.get_or_create(
                    minute=clean_element(schedule.minute),
                    hour=clean_element(schedule.hour),
                    day_of_week=clean_element(schedule.day_of_week),
                    day_of_month=clean_element(schedule.day_of_month),
                    month_of_year=clean_element(schedule.month_of_year)
                )
            else:
                self.stdout.write(self.style.WARNING(f'Skipping {name}: Unknown schedule type'))
                continue
                
            task, created = PeriodicTask.objects.update_or_create(
                name=name,
                defaults={
                    'task': task_name,
                    'interval': interval,
                    'crontab': crontab_sched,
                    'enabled': True
                }
            )
            
            status = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'✓ {status} periodic task: {name}'))
            
        # Clean up any duplicate tasks targeting our managed celery tasks
        managed_tasks = [entry['task'] for entry in beat_schedule.values()]
        duplicate_tasks = PeriodicTask.objects.filter(
            task__in=managed_tasks
        ).exclude(
            name__in=beat_schedule.keys()
        )
        
        count = duplicate_tasks.count()
        if count > 0:
            names = list(duplicate_tasks.values_list('name', flat=True))
            duplicate_tasks.delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Cleaned up {count} duplicate periodic tasks from database: {names}'))
            
        self.stdout.write(self.style.SUCCESS('Celery Beat schedule synced successfully!'))
