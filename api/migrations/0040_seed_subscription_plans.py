from django.db import migrations

def seed_plans(apps, schema_editor):
    SubscriptionPlans = apps.get_model('api', 'SubscriptionPlans')
    
    plans = [
        {
            'plan_name': 'Starter (Free)',
            'description': 'The simple plan you need to get started',
            'inventory': True,
            'collection_accounts': '2',
            'ai_manager': False,
            'ai_calls': False,
            'cashiers': 1,
            'payroll': '2',
            'support': True,
            'is_popular': False,
            'one_amount': '0',
            'three_months': '0',
            'six_months': '0',
            'twelve_months': '0',
        },
        {
            'plan_name': 'Professional (Basic)',
            'description': 'More power for growing businesses',
            'inventory': True,
            'collection_accounts': '10',
            'ai_manager': True,
            'ai_calls': False,
            'cashiers': 5,
            'payroll': '10',
            'support': True,
            'is_popular': True,
            'one_amount': '100',
            'three_months': '270',
            'six_months': '500',
            'twelve_months': '900',
        },
        {
            'plan_name': 'Enterprise PRO',
            'description': 'Ultimate control for large teams',
            'inventory': True,
            'collection_accounts': '50',
            'ai_manager': True,
            'ai_calls': True,
            'cashiers': 20,
            'payroll': '50',
            'support': True,
            'is_popular': False,
            'one_amount': '25000',
            'three_months': '70000',
            'six_months': '130000',
            'twelve_months': '250000',
        }
    ]
    
    for plan_data in plans:
        SubscriptionPlans.objects.update_or_create(
            plan_name=plan_data['plan_name'],
            defaults=plan_data
        )

def remove_plans(apps, schema_editor):
    SubscriptionPlans = apps.get_model('api', 'SubscriptionPlans')
    SubscriptionPlans.objects.filter(plan_name__in=['Starter (Free)', 'Professional (Basic)', 'Enterprise PRO']).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('api', '0039_userpayroll__allowances_userpayroll__deductions_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_plans, remove_plans),
    ]
