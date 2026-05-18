import json
from celery import shared_task
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from finance.services import LoanRepaymentEngineService

@shared_task(name="finance.tasks.run_automated_loan_repayments")
def run_automated_loan_repayments():
    """
    Periodic worker task executor target endpoint.
    Invokes the automated atomic wallet collection engine.
    """
    result = LoanRepaymentEngineService.execute_bulk_auto_repayments()
    return json.dumps(result)


def sync_scheduler_to_celery_beat(config_instance):
    """
    Synchronizes the database settings record directly to the Celery Beat 
    engine core tables, completely abstracting crontab adjustments.
    """
    task_name = "Automated System Loan Repayment Loop Execution"
    
    # 1. Clean up tracking task components if configurations are deactivated
    if not config_instance.is_enabled:
        PeriodicTask.objects.filter(name=task_name).delete()
        return

    # 2. Extract base minute configuration parameters from the model's time object
    minute = config_instance.execution_time.minute

    # 3. Parse cron structural expressions based on selected administrative settings
    if config_instance.frequency == 'hourly':
        hour = '*'          # Execute every single hour at the set minute mark
        day_of_week = '*'
        day_of_month = '*'
    elif config_instance.frequency == 'daily':
        hour = str(config_instance.execution_time.hour)
        day_of_week = '*'
        day_of_month = '*'
    elif config_instance.frequency == 'weekly':
        hour = str(config_instance.execution_time.hour)
        day_of_week = '1'   # Execute on Mondays explicitly
        day_of_month = '*'
    else:  # Monthly
        hour = str(config_instance.execution_time.hour)
        day_of_week = '*'
        day_of_month = '1'  # Execute on the 1st day of every calendar month

    # 4. Atomically look up or record the target Crontab schedule row
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=str(minute),
        hour=hour,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        month_of_year='*'
    )

    # 5. Bind schedule to task execution block entrypoint safely
    PeriodicTask.objects.update_or_create(
        name=task_name,
        defaults={
            'crontab': schedule,
            'task': 'finance.tasks.run_automated_loan_repayments',
            'args': '[]',
            'enabled': True
        }
    )


