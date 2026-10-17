from django.db import transaction
from rest_framework.decorators import api_view
import asyncio
import os
import traceback
import decimal
import uuid
from datetime import datetime, date
from urllib.parse import parse_qs
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.core.mail import EmailMessage
from django.conf import settings
from asgiref.sync import sync_to_async
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.cache import never_cache
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser, User
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q, Count, Value, CharField
from django.core.paginator import Paginator
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from calendar import monthrange
from api.functions import misc
from django.shortcuts import get_object_or_404, redirect, render
from .serializer import UserSecureSerializer, FundingInstrumentsSerializer, SupportSerializer, \
    FaqSerializer, CryptoAssetsSerializer, UserTransactionsSerializer, \
    UserItemsSerializer, UserInvoicesSerializer, UserBusinessDetailsSerializer, UserManagersSerializer, \
    SubscriptionSerializer, UserPayrollSerializer, StaffSecureSerializer, DepartmentsSerializer, \
    BankDepositDetailsSerializer
from api import models
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from django.core.files.storage import default_storage
from datetime import datetime, timedelta
from django.utils.timezone import now, make_aware
from dotenv import load_dotenv
import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from datetime import timedelta
from decimal import Decimal
from collections import defaultdict
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate, Coalesce
from django.db.models import Count
from ..functions.subscription_validation import SubscriptionManager
from ..models import UserSecure, UserItems, UserInvoices, UserInvoiceItems, BusinessDetails
import urllib.request
import urllib.error
import re as _re
import json as _json

load_dotenv()
today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
today_end = today_start + timedelta(days=1)


class UnsafeSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return None

def get_items_expiring_soon(user):
    today = now().date()
    two_weeks_from_now = today + timedelta(days=14)

    expiring_items = []

    for item in UserItems.objects.filter(user=user, is_promo=False):
        try:
            expiry_date = datetime.strptime(item.item_expiry, "%d/%m/%Y").date()
            if today <= expiry_date <= two_weeks_from_now and item.item_quantity > 0:
                expiring_items.append(item)
        except (ValueError, TypeError):
            continue

    promo_percent = 5
    return [
        {
            "item_id": item.id,
            "promotional_percent": promo_percent,
            "promotional_amount": round(float(item.item_amount) * (1 - promo_percent / 100), 2),
            "item_name": item.item_name,
            "item_amount": item.item_amount,
            "item_description": item.item_description,
            "item_serial_number": item.item_serial_number,
            "item_quantity": item.item_quantity,
            "item_expiry": item.item_expiry,
        }
        for item in expiring_items
    ]

def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    return obj

def is_older_than_two_weeks(item: models.UserItems):
    if not item.last_adjusted_date:
        return True  # Allow items never adjusted
    return item.last_adjusted_date < now() - timedelta(days=14)


def get_item_id(user, item_name):
    item = models.UserItems.objects.filter(
        user=user,
        item_name__iexact=item_name
    ).first()
    if item:
        image_url = item.images.first().image.url if item.images.exists() else None
        return [str(item.item_id), str(item.item_amount), image_url]
    return None

def visitor_analytics_summary(user):
    from api.models import StoreVisitor, BusinessDetails
    
    business = BusinessDetails.objects.filter(user=user, store_setup=True).first() or BusinessDetails.objects.filter(user=user).first()
    if not business:
        return {'countries': [], 'states': []}
    visitors = StoreVisitor.objects.filter(store=business, is_preview=False)
        
    country_data = list(visitors.values('country_code').annotate(count=Count('id')).order_by('-count'))
    state_data = list(visitors.values('state').annotate(count=Count('id')).order_by('-count'))
    
    return {
        'countries': country_data,
        'states': state_data
    }

def invoice_analytics_summary(user, limit=100, reference_date=None):
    if reference_date in [None, "0000-00-00 00:00:00.000000"]:
        today = now()
    else:
        today = reference_date

    current_day = today.day
    start_of_month = today.replace(day=1)
    start_of_next_day = make_aware(datetime.combine(today + timedelta(days=1), datetime.min.time()))
    last_day_of_prev_month = start_of_month - timedelta(days=1)
    start_of_last_month = last_day_of_prev_month.replace(day=1)
    end_of_last_month = make_aware(datetime.combine(last_day_of_prev_month, datetime.max.time()))
    start_of_last_month = make_aware(datetime.combine(start_of_last_month, datetime.min.time()))


    try:
        end_of_last_month_period = start_of_last_month.replace(day=current_day)
    except ValueError:
        end_of_last_month_period = last_day_of_prev_month

    user_invoices = models.UserInvoices.objects.filter(user_id=user, invoice_status='completed')

    last_month_total_full = Decimal("0.0")
    last_month_total_partial = Decimal("0.0")
    this_month_total = Decimal("0.0")
    last_7_days_total = Decimal("0.0")

    daily_totals = defaultdict(lambda: Decimal("0.0"))
    item_sales_this_month = defaultdict(lambda: {"total": Decimal("0.0"), "unit_amount": Decimal("0.0")})
    item_sales_last_7_days = defaultdict(lambda: {"total": Decimal("0.0"), "unit_amount": Decimal("0.0")})

    this_week_sales = Decimal("0.0")
    last_week_sales = Decimal("0.0")

    weekday_index = today.weekday()
    start_of_this_week = today - timedelta(days=weekday_index)
    start_of_last_week = start_of_this_week - timedelta(days=7)
    seven_days_ago = today - timedelta(days=6)

    for invoice in user_invoices:
        invoice_id = invoice.invoice_id

        last_month_total_full += models.UserInvoiceItems.objects.filter(
            item_invoice_id=invoice_id,
            timestamp__range=[start_of_last_month, end_of_last_month]
        ).aggregate(total=Sum(
            ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField()))
        )['total'] or Decimal("0.0")

        last_month_total_partial += models.UserInvoiceItems.objects.filter(
            item_invoice_id=invoice_id,
            timestamp__range=[start_of_last_month, end_of_last_month_period]
        ).aggregate(total=Sum(
            ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField()))
        )['total'] or Decimal("0.0")

        items_by_day = models.UserInvoiceItems.objects.filter(
            item_invoice_id=invoice_id,
            timestamp__range=[start_of_month, today]
        ).annotate(day=TruncDate('timestamp')).values('day').annotate(
            daily_total=Sum(
                ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField()))
        )

        for item in items_by_day:
            daily_totals[item['day']] += item['daily_total'] or Decimal("0.0")
            this_month_total += item['daily_total'] or Decimal("0.0")

        last_7_days_total += models.UserInvoiceItems.objects.filter(
            item_invoice_id=invoice_id,
            timestamp__range=[seven_days_ago, today]
        ).aggregate(total=Sum(
            ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField()))
        )['total'] or Decimal("0.0")

        this_week_sales += models.UserInvoiceItems.objects.filter(
            item_invoice_id=invoice_id,
            timestamp__range=[start_of_this_week, today]
        ).aggregate(total=Sum(
            ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField()))
        )['total'] or Decimal("0.0")

        end_of_last_week_period = start_of_last_week + timedelta(days=weekday_index)
        last_week_sales += models.UserInvoiceItems.objects.filter(
            item_invoice_id=invoice_id,
            timestamp__range=[start_of_last_week, end_of_last_week_period]
        ).aggregate(total=Sum(
            ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField()))
        )['total'] or Decimal("0.0")

        items_week = models.UserInvoiceItems.objects.filter(
            item_invoice_id=invoice_id,
            timestamp__range=[seven_days_ago, today]
        ).values('item_name', 'item_amount').annotate(
            total_sales=Sum(ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField()))
        )
        for item in items_week:
            name = item['item_name']
            total = item['total_sales'] or Decimal("0.0")
            item_sales_last_7_days[name]["total"] += total
            item_sales_last_7_days[name]["unit_amount"] = item['item_amount']

        items_month = models.UserInvoiceItems.objects.filter(
            item_invoice_id=invoice_id,
            timestamp__range=[start_of_month, today]
        ).values('item_name', 'item_amount').annotate(
            total_sales=Sum(ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField()))
        )
        for item in items_month:
            name = item['item_name']
            total = item['total_sales'] or Decimal("0.0")
            item_sales_this_month[name]["total"] += total
            item_sales_this_month[name]["unit_amount"] = item['item_amount']

    # Calculate monthly sales for the current year
    monthly_sales = {m: Decimal("0.0") for m in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']}
    start_of_year = today.replace(month=1, day=1)
    invoice_items_year = models.UserInvoiceItems.objects.filter(
        user__user_id=user,
        user__invoice_status='completed',
        timestamp__range=[start_of_year, today]
    )
    for item in invoice_items_year:
        month_name = item.timestamp.strftime('%b')
        if month_name in monthly_sales:
            monthly_sales[month_name] += (item.item_quantity * item.item_amount)

    # Calculate inventory health (quantity by category)
    inventory_health = models.UserItems.objects.filter(user=user).values('item_category').annotate(total_qty=Sum('item_quantity'))
    inventory_by_category = {item['item_category'] or 'General': item['total_qty'] or 0 for item in inventory_health}

    # Calculate actual department sales
    department_sales = defaultdict(Decimal)
    user_items_dept_map = {str(item.id): item.item_department or 'General' for item in models.UserItems.objects.filter(user=user)}
    
    all_invoice_items = models.UserInvoiceItems.objects.filter(
        user__user_id=user,
        user__invoice_status='completed'
    )
    for item in all_invoice_items:
        dept = user_items_dept_map.get(str(item.item_id), 'General')
        department_sales[dept] += Decimal(item.item_quantity) * Decimal(item.item_amount)
    
    department_sales_dict = {k: float(v) for k, v in department_sales.items()}

    next_month = today.replace(day=28) + timedelta(days=4)
    last_day_of_this_month = next_month - timedelta(days=next_month.day)
    days_remaining = last_day_of_this_month.day - current_day

    avg_month = this_month_total / Decimal(current_day) if current_day else Decimal("0.0")
    avg_last_7_days = last_7_days_total / Decimal(7)
    weighted_avg = (avg_last_7_days * Decimal("0.7")) + (avg_month * Decimal("0.3"))
    forecasted_total = this_month_total + (weighted_avg * days_remaining)

    change_percentage = ((
                                 this_month_total - last_month_total_partial) / last_month_total_partial) * 100 if last_month_total_partial > 0 else (
        100 if this_month_total > 0 else 0)
    forecast_vs_last_month_change_percentage = ((
                                                        forecasted_total - last_month_total_full) / last_month_total_full) * 100 if last_month_total_full > 0 else (
        100 if forecasted_total > 0 else 0)
    weekly_change_percentage = ((
                                        this_week_sales - last_week_sales) / last_week_sales) * 100 if last_week_sales > 0 else (
        100 if this_week_sales > 0 else 0)

    best_week = sorted(item_sales_last_7_days.items(), key=lambda x: x[1]["total"], reverse=True)[:limit]
    best_names_week = {name for name, _ in best_week}
    worst_week = sorted([(k, v) for k, v in item_sales_last_7_days.items() if k not in best_names_week],
                        key=lambda x: x[1]["total"])[:limit]

    best_month = sorted(item_sales_this_month.items(), key=lambda x: x[1]["total"], reverse=True)[:limit]
    best_names_month = {name for name, _ in best_month}
    worst_month = sorted([(k, v) for k, v in item_sales_this_month.items() if k not in best_names_month],
                         key=lambda x: x[1]["total"])[:limit]

    # Expression to calculate margin
    margin_expr = ExpressionWrapper(
        (F('item_amount') - F('item_buy_amount')) * F('item_quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    # Filter & aggregate for current month
    if user_invoices.exists():
        user_invoice_ids = user_invoices.values_list('id', flat=True)

        current_margin_data = UserInvoiceItems.objects.filter(
            user_id__in=user_invoice_ids,
            timestamp__gte=make_aware(datetime.combine(start_of_month, datetime.min.time())),
            timestamp__lt=start_of_next_day
        ).aggregate(total_margin=Sum(margin_expr))

        prev_margin_data = UserInvoiceItems.objects.filter(
            user_id__in=user_invoice_ids,
            timestamp__gte=start_of_last_month,
            timestamp__lte=end_of_last_month
        ).aggregate(total_margin=Sum(margin_expr))

        current_margin = current_margin_data.get("total_margin") or 0
        prev_margin = prev_margin_data.get("total_margin") or 0
    else:
        current_margin = 0
        prev_margin = 0

    percent_diff = None if prev_margin == 0 else ((current_margin - prev_margin) / prev_margin) * 100

    negative_items = list(
        UserItems.objects.filter(
            user=user,
            item_amount__lt=F("item_buy_amount")
        ).values_list("item_name", flat=True)
    )

    # --- Average Order Value (AOV) ---
    completed_invoices = UserInvoices.objects.filter(user_id=user, invoice_status='completed')
    completed_count_total = completed_invoices.count()
    total_revenue_all = float(UserInvoiceItems.objects.filter(
        user__user_id=user, user__invoice_status='completed'
    ).aggregate(total=Sum(ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField())))['total'] or 0)
    average_order_value = round(total_revenue_all / completed_count_total, 2) if completed_count_total > 0 else 0.0

    # Previous month AOV
    prev_month_completed = completed_invoices.filter(
        timestamp__gte=start_of_last_month, timestamp__lte=end_of_last_month
    ).count()
    prev_month_revenue = float(UserInvoiceItems.objects.filter(
        user__user_id=user, user__invoice_status='completed',
        timestamp__gte=start_of_last_month, timestamp__lte=end_of_last_month
    ).aggregate(total=Sum(ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField())))['total'] or 0)
    prev_aov = round(prev_month_revenue / prev_month_completed, 2) if prev_month_completed > 0 else 0.0
    aov_change = round(((average_order_value - prev_aov) / prev_aov) * 100, 2) if prev_aov > 0 else (100.0 if average_order_value > 0 else 0.0)

    # --- Profit Margin ---
    total_cogs = float(UserInvoiceItems.objects.filter(
        user__user_id=user, user__invoice_status='completed'
    ).aggregate(total=Sum(ExpressionWrapper(F('item_quantity') * F('item_buy_amount'), output_field=DecimalField())))['total'] or 0)
    total_profit_all = total_revenue_all - total_cogs
    profit_margin = round((total_profit_all / total_revenue_all) * 100, 2) if total_revenue_all > 0 else 0.0

    # Previous month profit margin
    prev_cogs = float(UserInvoiceItems.objects.filter(
        user__user_id=user, user__invoice_status='completed',
        timestamp__gte=start_of_last_month, timestamp__lte=end_of_last_month
    ).aggregate(total=Sum(ExpressionWrapper(F('item_quantity') * F('item_buy_amount'), output_field=DecimalField())))['total'] or 0)
    prev_profit = prev_month_revenue - prev_cogs
    prev_profit_margin = round((prev_profit / prev_month_revenue) * 100, 2) if prev_month_revenue > 0 else 0.0
    margin_change = round(profit_margin - prev_profit_margin, 2)  # percentage point difference

    # --- Inventory Turnover (COGS / Average Inventory Cost) ---
    inventory_items = UserItems.objects.filter(user=user)
    avg_inventory_cost = float(
        inventory_items.aggregate(
            total=Sum(ExpressionWrapper(F('item_buy_amount') * F('item_quantity'), output_field=DecimalField()))
        )['total'] or 0
    )
    # Annualised: multiply monthly COGS by 12 to get yearly estimate
    current_month_cogs = float(UserInvoiceItems.objects.filter(
        user__user_id=user, user__invoice_status='completed',
        timestamp__gte=make_aware(datetime.combine(start_of_month, datetime.min.time())),
        timestamp__lt=start_of_next_day
    ).aggregate(total=Sum(ExpressionWrapper(F('item_quantity') * F('item_buy_amount'), output_field=DecimalField())))['total'] or 0)
    annualised_cogs = current_month_cogs * 12
    inventory_turnover = round(annualised_cogs / avg_inventory_cost, 2) if avg_inventory_cost > 0 else 0.0

    prev_month_cogs_turnover = float(UserInvoiceItems.objects.filter(
        user__user_id=user, user__invoice_status='completed',
        timestamp__gte=start_of_last_month, timestamp__lte=end_of_last_month
    ).aggregate(total=Sum(ExpressionWrapper(F('item_quantity') * F('item_buy_amount'), output_field=DecimalField())))['total'] or 0)
    prev_annualised_cogs = prev_month_cogs_turnover * 12
    prev_inventory_turnover = round(prev_annualised_cogs / avg_inventory_cost, 2) if avg_inventory_cost > 0 else 0.0
    turnover_change = round(inventory_turnover - prev_inventory_turnover, 2)

    # --- Customer Retention (Repeat Purchase Rate) ---
    # Customers who made >= 2 completed purchases
    customer_email_counts = (
        UserInvoices.objects.filter(user_id=user, invoice_status='completed')
        .exclude(customer_email=None).exclude(customer_email='')
        .values('customer_email')
        .annotate(invoice_count=Count('id'))
    )
    total_unique_customers = customer_email_counts.count()
    repeat_customers = customer_email_counts.filter(invoice_count__gte=2).count()
    customer_retention = round((repeat_customers / total_unique_customers) * 100, 2) if total_unique_customers > 0 else 0.0

    # Previous period retention (customers who had >= 1 purchase before last month)
    prev_period_emails = set(
        UserInvoices.objects.filter(
            user_id=user, invoice_status='completed',
            timestamp__lt=start_of_last_month
        ).exclude(customer_email=None).exclude(customer_email='')
        .values_list('customer_email', flat=True)
    )
    returning_last_month = (
        UserInvoices.objects.filter(
            user_id=user, invoice_status='completed',
            timestamp__gte=start_of_last_month, timestamp__lte=end_of_last_month,
            customer_email__in=prev_period_emails
        ).exclude(customer_email=None).exclude(customer_email='')
        .values('customer_email').distinct().count()
    )
    last_month_new_customers = (
        UserInvoices.objects.filter(
            user_id=user, invoice_status='completed',
            timestamp__gte=start_of_last_month, timestamp__lte=end_of_last_month
        ).exclude(customer_email=None).exclude(customer_email='')
        .values('customer_email').distinct().count()
    )
    prev_retention = round((returning_last_month / last_month_new_customers) * 100, 2) if last_month_new_customers > 0 else 0.0
    retention_change = round(customer_retention - prev_retention, 2)

    response = {
        "sales_today": round(float(daily_totals.get(today.date(), Decimal("0.0"))), 2),
        "sales_last_7_days": round(float(last_7_days_total), 2),
        "sales_this_month": round(float(this_month_total), 2),
        "sales_last_month_to_date": round(float(last_month_total_partial), 2),
        "sales_change_percentage": round(float(change_percentage), 2),
        "projected_monthly_revenue": round(float(forecasted_total), 2),
        "forecast_month_change_percentage": round(float(forecast_vs_last_month_change_percentage), 2),
        "expiring_soon": get_items_expiring_soon(user),
        "current_month_margin": round(current_margin, 2),
        "previous_month_margin": round(prev_margin, 2),
        "margin_percentage_difference": round(percent_diff, 2) if percent_diff is not None else None,
        "promo_items": sanitize_for_json(negative_items),
        "best_performing_items_week": [{
                "item": name,
                "item_id": item_id[0],
                "total_sales": round(float(data["total"]), 2),
                "unit_amount": round(float(item_id[1]), 2),
                "image_url": item_id[2]
            } for name, data in best_week
            if (item_id := get_item_id(user, name)) is not None and
               (item_obj := models.UserItems.objects.filter(item_id=item_id[0]).first()) is not None and
               is_older_than_two_weeks(item_obj)
        ],
        "worst_performing_items_week": [
            {
                "item": name,
                "item_id": item_id[0],
                "total_sales": round(float(data["total"]), 2),
                "unit_amount": round(float(item_id[1]), 2),
                "image_url": item_id[2]
            } for name, data in worst_week
            if (item_id := get_item_id(user, name)) is not None
        ],
        "best_performing_items_month": [
            {
                "item": name,
                "item_id": item_id[0],
                "total_sales": round(float(data["total"]), 2),
                "unit_amount": round(float(item_id[1]), 2),
                "image_url": item_id[2]
            } for name, data in best_month
            if (item_id := get_item_id(user, name)) is not None
        ],
        "worst_performing_items_month": [
            {
                "item": name,
                "item_id": item_id[0],
                "total_sales": round(float(data["total"]), 2),
                "unit_amount": round(float(item_id[1]), 2),
                "image_url": item_id[2]
            } for name, data in worst_month
            if (item_id := get_item_id(user, name)) is not None
        ],
        "week_over_week": {
            "adjustment_percentage": 5.0,
            "this_week_sales": round(float(this_week_sales), 2),
            "last_week_sales": round(float(last_week_sales), 2),
            "percentage_change": round(float(weekly_change_percentage), 2),
        },
        "monthly_sales": monthly_sales,
        "inventory_by_category": inventory_by_category,
        "department_sales": department_sales_dict,
        "daily_sales": {str(k): float(v) for k, v in daily_totals.items()},
        "total_paid": round(float(UserInvoiceItems.objects.filter(user__user_id=user, user__invoice_status='completed').aggregate(total=Sum(F('item_quantity') * F('item_amount')))['total'] or 0), 2),
        "total_outstanding": round(float(UserInvoiceItems.objects.filter(user__user_id=user, user__invoice_status='pending').aggregate(total=Sum(F('item_quantity') * F('item_amount')))['total'] or 0), 2),
        "pending_count": UserInvoices.objects.filter(user_id=user, invoice_status='pending').count(),
        "completed_count": UserInvoices.objects.filter(user_id=user, invoice_status='completed').count(),
        "overdue_count": UserInvoices.objects.filter(user_id=user, invoice_status='pending', timestamp__lt=now() - timedelta(days=30)).count(),
        "overdue_amount": round(float(UserInvoiceItems.objects.filter(user__user_id=user, user__invoice_status='pending', timestamp__lt=now() - timedelta(days=30)).aggregate(total=Sum(F('item_quantity') * F('item_amount')))['total'] or 0), 2),
        # Analytics stat cards
        "average_order_value": average_order_value,
        "prev_average_order_value": prev_aov,
        "aov_change_percentage": aov_change,
        "profit_margin": profit_margin,
        "prev_profit_margin": prev_profit_margin,
        "margin_change_percentage": margin_change,
        "inventory_turnover": inventory_turnover,
        "prev_inventory_turnover": prev_inventory_turnover,
        "turnover_change": turnover_change,
        "customer_retention": customer_retention,
        "prev_customer_retention": prev_retention,
        "retention_change": retention_change,
    }

    response.update({"summary_header": "Hello there!"})
    response.update({"summary_text": "Hang tight—your AI business manager is preparing to analyze your data. I hope you’re doing great!"})

    return sanitize_for_json(response)

def calculate_total_balance(user_id):
    transactions = models.UserTransactions.objects.filter(user=user_id, trx_status__in=['completed', 'pending'])
    total_deposit = transactions.filter(trx_type='credit', trx_status='completed').aggregate(
        total=Sum('trx_amount')
    )['total'] or 0.0

    total_outgoing = transactions.filter(trx_type__in=['withdrawal', 'transfer', 'payment', 'domain_purchase']).aggregate(
        total=Sum('trx_amount')
    )['total'] or 0.0

    # Calculate available balance
    available_balance = total_deposit - total_outgoing
    return available_balance

def payroll_details(user_id):
    payrolls = models.UserPayroll.objects.filter(user_id=user_id)

    now = datetime.now()
    today = now.day
    days_in_month = monthrange(now.year, now.month)[1]

    previous_year_compare_percent = 50
    previous_month_compare_percent = 50

    total_to_disburse = 0.0
    total_disbursed_so_far = 0.0

    active_count = 0
    blocked_count = 0

    for payroll in payrolls:
        if payroll.pay_status == 'active':
            active_count += 1
        else:
            blocked_count += 1
            
        base_amount = payroll.get_pay_amount()
        allowance_amount = payroll.get_allowances()
        deduction_amount = payroll.get_deductions()
        amount = base_amount + allowance_amount - deduction_amount
        frequency = payroll.get_pay_frequency() or 'monthly'

        if frequency == 'daily':
            total_to_disburse += amount * days_in_month
            total_disbursed_so_far += amount * today
        elif frequency == 'weekly':
            total_to_disburse += amount * (days_in_month // 7)
            start_of_month = now.replace(day=1)
            elapsed_days = (now - start_of_month).days + 1
            total_disbursed_so_far += amount * (elapsed_days // 7)
        elif frequency == 'monthly':
            total_to_disburse += amount
            total_disbursed_so_far += amount if today >= 1 else 0.0
        elif frequency == 'yearly':
            monthly_portion = amount / 12
            total_to_disburse += monthly_portion
            total_disbursed_so_far += monthly_portion * (today / days_in_month)

    overdraft_val = 0.0
    business_details = models.BusinessDetails.objects.filter(user=user_id).first()
    if business_details:
        overdraft_val = float(business_details.payroll_overdraft or 0.0)

    return {
            "total_monthly_disbursement": round(total_to_disburse, 2),
            "total_disbursed_so_far": round(0, 2),
            "active_count": active_count,
            "blocked_count": blocked_count,
            "overdraft": round(overdraft_val, 2),
            "previous_year_compare_percentage": previous_year_compare_percent,
            "previous_month_compare_percentage": previous_month_compare_percent
        }

def user_data_db(user_id, token='', request=None):
    queryset = get_object_or_404(models.UserSecure, user_id=user_id)
    instrument_queryset = models.FundingInstruments.objects.all()
    support_queryset = models.UserSupport.objects.filter(uniq_id=1).first()
    faq_queryset = models.AskedQuestions.objects.all()
    crypto_assets_queryset = models.CryptoAssets.objects.all()
    trx_queryset = models.UserTransactions.objects.filter(user=queryset).order_by('-id')
    # Serializing data
    details_serializer = UserSecureSerializer(queryset, context={'request': request})
    instruments = FundingInstrumentsSerializer(instrument_queryset)
    support_serializer = SupportSerializer(support_queryset)
    faq_serializer = FaqSerializer(faq_queryset, many=True)
    crypto_assets_serializer = CryptoAssetsSerializer(crypto_assets_queryset, many=True, context={'request': request})
    trx_serializer = UserTransactionsSerializer(trx_queryset, many=True)
    subscriptions = models.SubscriptionPlans.objects.all()
    subscriptions_serializer = SubscriptionSerializer(subscriptions, many=True)

    # user_info = {
    #     'title': "User info",
    #     "info": "This is an information reaching you because your account will be disabled soon.",
    #     "date": "2025-02-15T13:35:32.880469Z"
    # }
    user_info = {}
    general_info = {}

    data = details_serializer.data

    # Ensure serialized verification statuses match the user flags
    if not queryset.kyc_verified and 'verification' in data:
        data['verification'] = [
            v for v in data['verification']
            if not ((v.get('verification_type') or '').upper() == 'KYC' and str(v.get('verification_status')) == '1')
        ]
    if not queryset.kyb_verified and 'verification' in data:
        data['verification'] = [
            v for v in data['verification']
            if not ((v.get('verification_type') or '').upper() == 'KYB' and str(v.get('verification_status')) == '1')
        ]

    is_manager = False
    manager = None
    is_staff = False
    staff = None

    try:
        data.update({'manager_account': {}})
        data.update({'staff_account': {}})
        actual_user = None
        if request and hasattr(request, 'actual_user_id') and request.actual_user_id != user_id:
            actual_user = models.UserSecure.objects.filter(user_id=request.actual_user_id).first()
        elif request and hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False) and getattr(request.user, 'user_id', None) != user_id:
            actual_user = request.user

        if actual_user:
            if actual_user.user_type == 'manager':
                is_manager = True
                manager = models.UserManagers.objects.filter(manager_email__iexact=actual_user.user_email).first()
                if manager:
                    manager_serializer = UserManagersSerializer(manager)
                    data.update({'manager_account': manager_serializer.data})
            elif actual_user.user_type == 'staff':
                is_staff = True
                staff = models.UserPayroll.objects.filter(user_id=actual_user).first()
                if staff:
                    staff_serializer = UserPayrollSerializer(staff)
                    data.update({'staff_account': staff_serializer.data})
    except Exception as e:
        pass

    can_manage_finances = True
    can_manage_payroll = True

    if is_manager and manager:
        can_manage_finances = bool(manager.manage_finances)
        can_manage_payroll = bool(manager.manage_payroll)

    effective_withdrawals_disabled = bool(queryset.withdrawals_disabled or (actual_user and actual_user.withdrawals_disabled))
    effective_transfers_disabled = bool(queryset.transfers_disabled or (actual_user and actual_user.transfers_disabled))

    data.update({
        'is_manager': is_manager,
        'is_staff': is_staff,
        'can_manage_finances': can_manage_finances,
        'can_manage_payroll': can_manage_payroll,
        'finances_masked': not can_manage_finances,
        'payroll_masked': not can_manage_payroll,
        'withdrawals_disabled': effective_withdrawals_disabled,
        'transfers_disabled': effective_transfers_disabled,
    })

    data.update({'instruments': instruments.data})
    data.update({'support': support_serializer.data})
    data.update({'faq': faq_serializer.data})

    if can_manage_finances:
        data.update({'balance': calculate_total_balance(queryset)})
        data.update({'crypto_assets': crypto_assets_serializer.data})
    else:
        data.update({'balance': 0.0})
        data.update({'crypto_assets': []})

    data.update({'transactions': trx_serializer.data})
    data.update({'app_version': os.getenv("APP_VERSION")})
    data.update({'general_info': general_info})
    data.update({'user_info': user_info})
    data.update({'sales_summary': invoice_analytics_summary(queryset)})

    if can_manage_payroll:
        data.update({'payroll_details': payroll_details(queryset)})
    else:
        data.update({'payroll_details': {
            "total_monthly_disbursement": 0.0,
            "total_disbursed_so_far": 0.0,
            "active_count": 0,
            "blocked_count": 0,
            "overdraft": 0.0,
            "previous_year_compare_percentage": 0,
            "previous_month_compare_percentage": 0
        }})
        data['payroll'] = []

    data.update({'subscriptions': subscriptions_serializer.data})
    data.update({'visitor_analytics': visitor_analytics_summary(queryset)})
    
    owner_deposit = models.BankDepositDetails.objects.filter(user=queryset, account_owner='owner').first()
    if not owner_deposit:
        owner_deposit = models.BankDepositDetails.objects.filter(user=queryset).first()
    data.update({'deposit_account': BankDepositDetailsSerializer(owner_deposit).data if owner_deposit else None})
    
    if can_manage_payroll:
        staff_qs = models.UserSecure.objects.filter(business_owner=queryset, user_type='staff')
        data.update({'staff_summary': {
            'total': staff_qs.count(),
            'active': staff_qs.filter(is_active=True).count()
        }})
    else:
        data.update({'staff_summary': {
            'total': 0,
            'active': 0
        }})
    user_details_obj = models.UserDetails.objects.filter(user=queryset).first()
    user_country_val = user_details_obj.user_country if user_details_obj else ""
    user_curr_val = user_details_obj.currency if user_details_obj else "NGN"

    country_config = (
        models.AllowedCountries.objects.filter(code__iexact=user_country_val).first()
        or models.AllowedCountries.objects.filter(name__iexact=user_country_val).first()
        or models.AllowedCountries.objects.filter(currency__iexact=user_curr_val).first()
        or models.AllowedCountries.objects.filter(is_active=True).first()
    )

    t1_limit = float(country_config.tier1_daily_limit) if (country_config and country_config.tier1_daily_limit is not None) else 50000.0
    t1_curr = country_config.currency if (country_config and country_config.currency) else (user_curr_val or 'NGN')
    min_wdr = float(country_config.min_withdrawal_amount) if (country_config and country_config.min_withdrawal_amount is not None) else 100.0

    data.update({
        'tier1_daily_limit': t1_limit,
        'tier1_currency': t1_curr,
        'min_withdrawal_amount': min_wdr,
        'allowed_countries': list(models.AllowedCountries.objects.filter(is_active=True).values('name', 'code', 'currency', 'tier1_daily_limit', 'min_withdrawal_amount'))
    })

    low_stock_qs = models.UserItems.objects.filter(user=queryset, item_quantity__lte=2)
    data.update({'low_stock_items': [{'item_id': str(item.item_id), 'item_name': item.item_name, 'item_quantity': item.item_quantity} for item in low_stock_qs]})

    inv_agg = models.UserItems.objects.filter(user=queryset).aggregate(
        total=Sum(ExpressionWrapper(F('item_amount') * Coalesce(F('item_quantity'), 1), output_field=DecimalField()))
    )
    data.update({'inventory_value': float(inv_agg['total'] or 0.0)})

    data = sanitize_for_json(data)

    return {'status': True, 'message': "", "data": data}




@method_decorator(csrf_exempt, name="dispatch")
class UserData(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            auth_header = request.headers.get("Authorization")
            token = auth_header if auth_header else None
            return Response(user_data_db(user_id, token, request=request))
        except Exception as e:
            msg = str(e) or "Token validation error"
            print(f"DEBUG Error in UserData: {msg}")
            status_code = status.HTTP_401_UNAUTHORIZED if ("token" in msg.lower() or "authorization" in msg.lower() or "not found" in msg.lower()) else status.HTTP_400_BAD_REQUEST
            return Response({"status": False, "message": msg}, status=status_code)

class UserAIView(APIView):
    def get(self, request):
        try:
            user_id = misc.get_id(request)
            queryset = get_object_or_404(models.UserSecure, user_id=user_id)

            # Subscription manager
            sub_manager = SubscriptionManager(queryset)
            ai_allowed = sub_manager.require_ai_manager()

            summary = invoice_analytics_summary(queryset)
            ai_summary = self._analyze_with_ollama(summary, ai=ai_allowed)
            summary.update({'summary_text': ai_summary.get('summary')})
            summary.update({'summary_header': ai_summary.get('header')})
            summary['week_over_week']['adjustment_percentage'] = ai_summary.get("suggested_increase_percent")

            return Response({'status': True, 'data': summary})
        except Exception as e:
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': str(e), 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _analyze_with_ollama(data: dict, currency='naira', ai=True) -> dict:
        """Analyze business performance using local Ollama qwen model."""
        fallback = {
            "header": "Analysis unavailable",
            "summary": "Your current plan does not support AI analysis. Upgrade to get started.",
            "suggested_increase_percent": 5.0
        }
        if not ai:
            return fallback
        try:
            import ollama as _ollama
            import os
            model_name = os.environ.get('OLLAMA_MODEL', 'gemma4:latest')
            response = _ollama.chat(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an AI business analyst. "
                            "Analyze the provided performance data and return a structured recommendation. "
                            "Make the summary simple, clear, and written in plain language "
                            "so that a small business owner with no financial background can easily understand. "
                            "Avoid technical jargon and explain what it means in everyday terms. "
                            f"Understand that the values are in {currency} and use the {currency} symbol in monetary values. "
                            "Take into account that a negative margin sometimes means certain items are sold on promo because they are expiring soon. "
                            "You MUST respond with ONLY valid JSON in this exact format: "
                            '{"header": "<short title>", "summary": "<2-3 sentence summary>", "suggested_increase_percent": <number>}'
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Here is the business performance data:\n{data}"
                    }
                ],
                format="json",
                think=False
            )
            import json as _json
            result = _json.loads(response.message.content)
            return {
                "header": result.get("header", fallback["header"]),
                "summary": result.get("summary", fallback["summary"]),
                "suggested_increase_percent": float(result.get("suggested_increase_percent", 5.0))
            }
        except Exception:
            return fallback

class UserDataConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):

        query_string = self.scope["query_string"].decode()
        params = parse_qs(query_string)
        token_key = params.get("token", [None])[0]

        self.get_token_key = params.get("token", [None])[0]

        self.scope["user"] = await self.get_user_from_token(token_key)

        if isinstance(self.scope["user"], AnonymousUser):
            await self.close(code=4001)
            return

        self.user_id = self.scope["user"].user_id
        self.group_name = f"user_{self.user_id}_data"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_user_data()


    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)


    @database_sync_to_async
    def get_user_from_token(self, token_key):
        if not token_key:
            return AnonymousUser()
        try:
            access_token = AccessToken(token_key)
            user_id = access_token.get("user_id")
            return UserSecure.objects.get(user_id=user_id)
        except TokenError as e:
            # Log the error for debugging but return AnonymousUser
            
            return AnonymousUser()
        except UserSecure.DoesNotExist:
            return AnonymousUser()
        except Exception as e:
            # Catch any other unexpected errors
            
            return AnonymousUser()

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        data = json.loads(text_data)
        if data.get("action") == "refresh":
            await self.send_user_data()

    @sync_to_async
    def get_user_data(self):
        try:
            # Check if user is active before returning data
            user = UserSecure.objects.get(user_id=self.user_id)
            if not user.is_active:
                return {
                    'status': False,
                    'message': 'Your account has been deactivated. Please contact support for assistance.',
                    'logout_required': True
                }
            return user_data_db(self.user_id, token=self.get_token_key)
        except Exception as e:
            return {'status': False, 'message': str(e)}

    async def send_user_data(self):
        try:
            user_profile = await self.get_user_data()
            sanitized_data = sanitize_for_json(user_profile)
            
            # Check if logout is required
            if sanitized_data.get('logout_required') or (sanitized_data.get('status') == False and 'deactivated' in sanitized_data.get('message', '').lower()):
                await self.send(text_data=json.dumps({
                    "type": "user.logout",
                    "message": sanitized_data.get('message', 'Your account has been deactivated. Please contact support for assistance.')
                }, default=str))
            else:
                response = {
                    "type": "user.update",
                    "data": sanitized_data
                }
                await self.send(text_data=json.dumps(response, default=str))
        except Exception as e:
            traceback_message = traceback.format_exc()
            await self.send(text_data=json.dumps({
                "error": str(e),
                'traceback': 'traceback_message'
            }, default=str))

    async def send_updated_user_data(self, event):
        sanitized_data = sanitize_for_json(event["data"])
        await self.send(text_data=json.dumps({
            "type": "user.update",
            "data": sanitized_data
        }, default=str))
    
    async def send_logout_signal(self, event):
        """Send logout signal to user when account is deactivated"""
        await self.send(text_data=json.dumps({
            "type": "user.logout",
            "message": event.get("message", "Your account has been deactivated. Please contact support for assistance.")
        }, default=str))








class FilteredTransactions(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            
            # Filters
            start_date = request.data.get("start_date")
            end_date = request.data.get("end_date")
            status_filter = request.data.get("status")
            type_filter = request.data.get("type")
            category_filter = request.data.get("category")
            search = request.data.get("search", "")
            
            # Pagination
            page = int(request.data.get("page", 1))
            per_page = int(request.data.get("per_page", 10))
            
            trx_queryset = models.UserTransactions.objects.filter(user=user).order_by('-timestamp')
            
            if start_date:
                trx_queryset = trx_queryset.filter(timestamp__gte=start_date)
            if end_date:
                trx_queryset = trx_queryset.filter(timestamp__lte=end_date)
            if status_filter and status_filter != 'All Statuses' and status_filter != '':
                trx_queryset = trx_queryset.filter(trx_status__iexact=status_filter)
            if type_filter and type_filter != 'All Types' and type_filter != '':
                trx_queryset = trx_queryset.filter(trx_type__iexact=type_filter)
            if search:
                trx_queryset = trx_queryset.filter(
                    Q(description__icontains=search) |
                    Q(trx_id__icontains=search)
                )
            
            paginator = Paginator(trx_queryset, per_page)
            page_obj = paginator.get_page(page)
            
            serializer = UserTransactionsSerializer(page_obj, many=True, context={'request': request})
            
            return Response({
                'status': True,
                'data': serializer.data,
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'per_page': per_page,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                }
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class FilteredInvoices(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            
            # Filters
            start_date = request.data.get("start_date")
            end_date = request.data.get("end_date")
            status_filter = request.data.get("status")
            type_filter = request.data.get("type")
            search = request.data.get("search", "")
            
            # Pagination
            page = int(request.data.get("page", 1))
            per_page = int(request.data.get("per_page", 10))
            
            invoice_queryset = models.UserInvoices.objects.filter(user_id=user).order_by('-timestamp')
            
            if start_date:
                invoice_queryset = invoice_queryset.filter(timestamp__gte=start_date)
            if end_date:
                invoice_queryset = invoice_queryset.filter(timestamp__lte=end_date)
            if status_filter and status_filter != 'All Statuses':
                invoice_queryset = invoice_queryset.filter(invoice_status__iexact=status_filter)
            if type_filter and type_filter != 'All Types':
                invoice_queryset = invoice_queryset.filter(invoice_type__iexact=type_filter)
            if search:
                invoice_queryset = invoice_queryset.filter(
                    Q(invoice_id__icontains=search) |
                    Q(invoice_note__icontains=search)
                )
            
            paginator = Paginator(invoice_queryset, per_page)
            page_obj = paginator.get_page(page)
            
            serializer = UserInvoicesSerializer(page_obj, many=True, context={'request': request})
            
            return Response({
                'status': True,
                'data': serializer.data,
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'per_page': per_page,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                }
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FetchSubscriptionInvoicesView(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            page = int(request.data.get("page", 1))
            per_page = int(request.data.get("per_page", 10))
            
            queryset = models.SubscriptionInvoices.objects.filter(user__user_id=user_id).order_by('-timestamp')
            
            paginator = Paginator(queryset, per_page)
            page_obj = paginator.get_page(page)
            
            from .serializer import SubscriptionInvoicesSerializer
            serializer = SubscriptionInvoicesSerializer(page_obj, many=True)
            
            return Response({
                'status': True,
                'data': serializer.data,
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'per_page': per_page,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                }
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

from django.http import HttpResponse
from django.template.loader import render_to_string
class SubscriptionInvoiceDownloadView(APIView):
    def get(self, request, invoice_id):
        try:
            token_str = request.GET.get('token')
            if token_str:
                from rest_framework_simplejwt.tokens import AccessToken
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    access_token = AccessToken(token_str)
                    user = User.objects.get(id=access_token['user_id'])
                except Exception:
                    return HttpResponse('Unauthorized', status=401)
            else:
                user = request.user
                
            if not user.is_authenticated:
                return HttpResponse('Unauthorized', status=401)
                
            invoice = models.SubscriptionInvoices.objects.get(user=user, invoice_id=invoice_id)
            business = models.BusinessDetails.objects.filter(user=user).first()
            
            context = {
                'invoice': invoice,
                'business': business,
                'user': user
            }
            html_string = render_to_string('views/pdf/subscription_invoice_pdf.html', context)
            
            return HttpResponse(html_string)
        except models.SubscriptionInvoices.DoesNotExist:
            return HttpResponse('Invoice not found', status=404)
        except Exception as e:
            return HttpResponse(str(e), status=400)


class SubscriptionsPlansView(APIView):
    def get(self, request):
        try:
            subscriptions = models.SubscriptionPlans.objects.all()
            subscriptions_serializer = SubscriptionSerializer(subscriptions, many=True)

            return Response({'status': True, 'data': subscriptions_serializer.data})
        except Exception as e:
            return Response({'status': False, 'message': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)


class VerificationView(APIView):
    def post(self, request):
        data = request.data.copy()
        try:
            user = UserSecure.objects.get(user_email=data.get('email'))
            verification = user.verification.last()  # get latest record

            if not verification:
                return Response({'status': False, 'message': 'No verification details found.'})

            # Helper to build absolute URL
            def build_url(field):
                if field:
                    return request.build_absolute_uri(field.url)
                return None

            details = {
                "verification_type": verification.verification_type,
                "verification_id": verification.verification_id,
                "account_type": verification.account_type,
                "user_address": verification.user_address,
                "proof_of_address": build_url(verification.proof_of_address),
                "user_image": build_url(verification.user_image),
                "user_video": build_url(verification.user_video),
                "driver_licence": build_url(verification.driver_licence),
                "legal_id": verification.legal_id,
                "verification_status": verification.verification_status,
                "timestamp": verification.timestamp,
            }

            return Response({'status': True, 'data': details})

        except UserSecure.DoesNotExist:
            return Response({'status': False, 'message': 'User not found'})


class UserPayrollListView(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    def get(self, request):
        try:
            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'manage_payroll'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_payroll' permission."}, status=status.HTTP_403_FORBIDDEN)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            
            search = request.GET.get('search', '')
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 10))
            
            queryset = models.UserPayroll.objects.filter(user_id=user).order_by('-id')
            
            if search:
                queryset = queryset.filter(
                    Q(account_name__icontains=search) |
                    Q(account_number__icontains=search) |
                    Q(bank_name__icontains=search)
                )
            
            paginator = Paginator(queryset, per_page)
            page_obj = paginator.get_page(page)
            
            serializer = UserPayrollSerializer(page_obj, many=True, context={'request': request})
            
            return Response({
                'status': True, 
                'data': serializer.data,
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'per_page': per_page
                }
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class FilteredStaff(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            
            search = request.data.get('search', '')
            status_filter = request.data.get('status')
            dept_filter = request.data.get('department')
            page = int(request.data.get('page', 1))
            per_page = int(request.data.get('per_page', 10))
            
            queryset = models.UserSecure.objects.filter(business_owner=user, user_type='staff').order_by('-date_created')
            
            if status_filter and status_filter != 'All Statuses':
                if status_filter.lower() == 'active':
                    queryset = queryset.filter(is_active=True)
                elif status_filter.lower() in ['inactive', 'suspended']:
                    queryset = queryset.filter(is_active=False)
            if dept_filter and dept_filter != 'All Departments':
                queryset = queryset.filter(details__department__icontains=dept_filter)
            if search:
                queryset = queryset.filter(
                    Q(details__first_name__icontains=search) |
                    Q(details__last_name__icontains=search) |
                    Q(details__job_title__icontains=search) |
                    Q(details__department__icontains=search)
                )
            
            paginator = Paginator(queryset, per_page)
            page_obj = paginator.get_page(page)
            
            serializer = StaffSecureSerializer(page_obj, many=True, context={'request': request})
            
            return Response({
                'status': True,
                'data': serializer.data,
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'per_page': per_page,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                }
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class FilteredManagers(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            
            search = request.data.get('search', '')
            dept_filter = request.data.get('department')
            page = int(request.data.get('page', 1))
            per_page = int(request.data.get('per_page', 10))
            
            queryset = models.UserManagers.objects.filter(user=user).order_by('-uniq_id')
            
            if dept_filter and dept_filter != 'All Departments':
                queryset = queryset.filter(manager_department__icontains=dept_filter)
            if search:
                queryset = queryset.filter(
                    Q(manager_name__icontains=search) |
                    Q(manager_email__icontains=search) |
                    Q(manager_department__icontains=search)
                )
            
            paginator = Paginator(queryset, per_page)
            page_obj = paginator.get_page(page)
            
            serializer = UserManagersSerializer(page_obj, many=True, context={'request': request})
            
            return Response({
                'status': True,
                'data': serializer.data,
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'per_page': per_page,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                }
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class FilteredProducts(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            
            search = request.data.get('search', '')
            dept_filter = request.data.get('department')
            page = int(request.data.get('page', 1))
            per_page = int(request.data.get('per_page', 10))
            
            queryset = models.UserItems.objects.filter(user=user).order_by('-id')
            
            if dept_filter and dept_filter != 'All Departments':
                queryset = queryset.filter(item_department__icontains=dept_filter)
            if search:
                queryset = queryset.filter(
                    Q(item_name__icontains=search) |
                    Q(item_id__icontains=search) |
                    Q(item_description__icontains=search)
                )
            
            paginator = Paginator(queryset, per_page)
            page_obj = paginator.get_page(page)
            
            serializer = UserItemsSerializer(page_obj, many=True, context={'request': request})
            
            low_stock_qs = models.UserItems.objects.filter(user=user, item_quantity__lte=2)
            low_stock_items = [{'item_id': str(item.item_id), 'item_name': item.item_name, 'item_quantity': item.item_quantity} for item in low_stock_qs]
            
            # Calculate store catalog metrics across all products for this merchant
            all_user_items = models.UserItems.objects.filter(user=user)
            total_products_count = all_user_items.count()

            # Total inventory valuation: sum of (item_amount * Coalesce(item_quantity, 1))
            total_val_agg = all_user_items.aggregate(
                total=Sum(ExpressionWrapper(
                    F('item_amount') * Coalesce(F('item_quantity'), 1),
                    output_field=DecimalField()
                ))
            )['total']
            total_amount = float(total_val_agg or 0.0)

            # Currency configuration
            user_details = models.UserDetails.objects.filter(user=user).first()
            curr_code = (user_details.currency if user_details and user_details.currency else 'NGN') or 'NGN'
            from api.functions.subscription_validation import get_currency_symbol
            currency_symbol = get_currency_symbol(curr_code)

            # Change indicator calculation (this month vs last month & 30-day velocity)
            now_dt = timezone.now()
            current_month_start = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if current_month_start.month == 1:
                prev_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
            else:
                prev_month_start = current_month_start.replace(month=current_month_start.month - 1)
            prev_month_end = current_month_start - timedelta(seconds=1)

            new_this_month = all_user_items.filter(timestamp__gte=current_month_start).count()
            added_last_month = all_user_items.filter(timestamp__gte=prev_month_start, timestamp__lte=prev_month_end).count()

            if added_last_month > 0:
                change_pct = round(((new_this_month - added_last_month) / added_last_month) * 100, 1)
            elif new_this_month > 0:
                change_pct = 100.0
            else:
                change_pct = 0.0

            if change_pct > 0:
                change_direction = 'up'
                change_description = f"+{new_this_month} added this month"
            elif change_pct < 0:
                change_direction = 'down'
                change_description = f"{new_this_month} added this month" if new_this_month > 0 else f"No new items this month"
            else:
                change_direction = 'neutral'
                change_description = f"+{new_this_month} added this month" if new_this_month > 0 else "Catalog steady this month"

            metrics = {
                'total_products': total_products_count,
                'total_amount': total_amount,
                'currency': currency_symbol,
                'currency_code': curr_code,
                'change_pct': change_pct,
                'change_direction': change_direction,
                'change_description': change_description,
                'new_this_month': new_this_month,
            }

            return Response({
                'status': True,
                'data': serializer.data,
                'low_stock_items': low_stock_items,
                'metrics': metrics,
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'per_page': per_page,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                }
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class FilteredDepartments(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            
            queryset = models.CashierDepartments.objects.filter(user=user).order_by('-timestamp')
            
            serializer = DepartmentsSerializer(queryset, many=True)
            
            # Enrich with staff count
            data = serializer.data
            for dept in data:
                dept['staff_count'] = models.UserPayroll.objects.filter(user_id=user, department=dept['department_name']).count()
                dept['manager_count'] = models.UserManagers.objects.filter(user=user, manager_department=dept['department_name']).count()
            
            return Response({
                'status': True,
                'data': data
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class StaffDetailView(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    def get(self, request, staff_id):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            staff = get_object_or_404(models.UserSecure, uniq_id=staff_id, business_owner=user)
            serializer = StaffSecureSerializer(staff, context={'request': request})
            data = serializer.data
            
            # Fetch collection account if exists
            collection = models.BankDepositDetails.objects.filter(user=user, account_reference=str(staff.uniq_id)).first()
            if collection:
                data['has_collection_account'] = True
                data['collection_bank_name'] = collection.bank_name
                data['collection_account_number'] = collection.account_number
            else:
                data['has_collection_account'] = False
                
            return Response({'status': True, 'data': data})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class FilteredCategories(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            
            search = request.data.get('search', '')
            
            # Fetch all product categories for this user
            categories = models.ProductCategories.objects.filter(user=user)
            if search:
                categories = categories.filter(category_name__icontains=search)
            
            # For each category, count items using it in UserItems
            cat_list = []
            for cat in categories:
                product_count = models.UserItems.objects.filter(user=user, item_category=cat.category_name).count()
                
                name = (cat.category_name or 'General').lower()
                icon = 'package'
                if 'phone' in name or 'electronic' in name: icon = 'smartphone'
                elif 'laptop' in name or 'gadget' in name: icon = 'laptop'
                elif 'home' in name or 'appliance' in name: icon = 'home'
                elif 'fashion' in name or 'cloth' in name: icon = 'shirt'
                elif 'food' in name or 'grocery' in name: icon = 'shopping-basket'
                
                cat_list.append({
                    'id': cat.uniq_id,
                    'category_name': cat.category_name or 'General',
                    'active_products': product_count,
                    'icon': icon
                })
                
            return Response({
                'status': True,
                'data': cat_list
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RenewSubscriptionView(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            
            # Get duration and plan_id from request
            duration = request.data.get('duration', 'one_amount')
            plan_id = request.data.get('plan_id', None)
            is_promo = request.data.get('is_promo', False)
            
            sub_manager = SubscriptionManager(user)
            current_plan = sub_manager.get_plan()
            
            # Identify the new plan
            if plan_id:
                try:
                    new_plan = models.SubscriptionPlans.objects.get(uniq_id=plan_id)
                except models.SubscriptionPlans.DoesNotExist:
                    return Response({'status': False, 'message': "Invalid plan selected"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                new_plan = current_plan

            if not new_plan:
                return Response({'status': False, 'message': "No plan found to renew"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Determine amount based on duration or promo settings
            if is_promo:
                site_settings = models.SiteSettings.load()
                if not site_settings.promo_banner_enabled:
                    return Response({'status': False, 'message': "The promotional offer is no longer available or has been disabled."}, status=status.HTTP_400_BAD_REQUEST)
                
                promo_plan = site_settings.promo_plan
                promo_duration = site_settings.promo_duration
                
                if not promo_plan or str(new_plan.uniq_id) != str(promo_plan.uniq_id) or duration != promo_duration:
                    return Response({'status': False, 'message': "Invalid plan or duration for this promotional offer."}, status=status.HTTP_400_BAD_REQUEST)
                
                amount = 0.0
            else:
                if duration == 'prorated_upgrade':
                    from datetime import datetime
                    from django.utils import timezone
                    try:
                        expiry_str = sub_manager.business.subscription_expiry
                        if not expiry_str:
                            raise ValueError("No existing subscription expiry.")
                        
                        expiry = datetime.fromisoformat(str(expiry_str))
                        if timezone.is_naive(expiry):
                            expiry = timezone.make_aware(expiry, timezone=timezone.utc)
                        
                        remaining_days = max(0, (expiry - timezone.now()).days)
                        old_daily = float(current_plan.one_amount or 0) / 30
                        new_daily = float(new_plan.one_amount or 0) / 30
                        amount = max(0, remaining_days * (new_daily - old_daily))
                    except Exception as e:
                        return Response({'status': False, 'message': f"Failed to calculate prorated amount: {e}"}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    amounts = {
                        'one_amount': new_plan.one_amount,
                        'three_months': new_plan.three_months,
                        'six_months': new_plan.six_months,
                        'twelve_months': new_plan.twelve_months
                    }
                    amount = float(amounts.get(duration, new_plan.one_amount) or 0)
            
            if amount > 0:
                available_balance = calculate_total_balance(user)
                if float(available_balance) < amount:
                    return Response({'status': False, 'message': "Insufficient wallet balance to pay for this subscription."}, status=status.HTTP_400_BAD_REQUEST)
                
                # Deduct via UserTransactions
                models.UserTransactions.objects.create(
                    user=user,
                    trx_status='completed',
                    trx_amount=amount,
                    trx_type='payment',
                    trx_currency='NGN',
                    user_collection_id='0',
                    destination_id='0',
                    description=f"Subscription Payment: {new_plan.plan_name} ({duration.replace('_', ' ').capitalize()})"
                )

            if current_plan and current_plan.uniq_id == new_plan.uniq_id:
                success = sub_manager.renew_subscription(duration=duration)
            else:
                success = sub_manager.assign_plan(new_plan.uniq_id, duration=duration)
            
            if success:
                if is_promo:
                    user_details = models.UserDetails.objects.filter(user=user).first()
                    if user_details:
                        user_details.has_claimed_promo = True
                        user_details.save()
                        # Trigger congratulatory email
                        from api.tasks import send_promo_claim_congratulations
                        send_promo_claim_congratulations.delay(str(user.user_id), new_plan.plan_name)
                
                # Create a renewal invoice
                invoice_id = f"REN-{uuid.uuid4().hex[:10].upper()}"
                
                invoice = models.SubscriptionInvoices.objects.create(
                    user=user,
                    invoice_id=invoice_id,
                    invoice_status='completed',
                    invoice_payment_type='wallet',
                    invoice_note=f"Plan Subscription: {new_plan.plan_name} ({duration.replace('_', ' ').capitalize()})",
                    amount=amount,
                    plan_id=new_plan.uniq_id
                )
                return Response({'status': True, 'message': f"Subscription for {new_plan.plan_name} processed successfully!"})
            else:
                return Response({'status': False, 'message': "Subscription processing failed. Please try again later."}, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def store_view(request):
    from api.functions import misc
    from api.functions.subscription_validation import SubscriptionManager
    from api.models import SubscriptionPlans
    try:
        user = misc.get_owner_from_user(request.user)
        business = models.BusinessDetails.objects.filter(user=user).first()
        
        is_online_store_supported = False
        sub_manager = SubscriptionManager(user)
        try:
            sub_manager.require_online_store()
            is_online_store_supported = True
        except:
            pass
            
        context = {
            'is_online_store_supported': is_online_store_supported,
            'business': business
        }
        
        if not is_online_store_supported:
            from api.functions.subscription_validation import get_processed_subscription_context, format_currency_amount
            sub_ctx = get_processed_subscription_context(request.user)
            context.update(sub_ctx)
            raw_balance = calculate_total_balance(user)
            context['wallet_balance'] = raw_balance
            context['wallet_balance_display'] = format_currency_amount(raw_balance, sub_ctx['user_currency'])
            context['business_name'] = business.business_name if business else 'Your Business'
        
        if not business or not business.store_setup:
            allowed_countries = models.AllowedCountries.objects.filter(is_active=True)
            context['allowed_countries'] = allowed_countries
            context['biz'] = business if business else models.BusinessDetails()
            return render(request, 'views/dashboard/store-setup-wizard.html', context)
        return render(request, 'views/dashboard/store.html', context)
    except Exception as e:
        print(f"[store_view] Error resolving store for user {request.user}: {e}")
        # Only fall back to setup wizard if user is a business owner with no store
        # Do NOT silently redirect managers to the setup wizard
        if hasattr(request.user, 'user_type') and request.user.user_type in ['manager', 'staff']:
            # Manager/staff with error - still try to show the store page
            return render(request, 'views/dashboard/store.html', {'is_online_store_supported': True})
        allowed_countries = models.AllowedCountries.objects.filter(is_active=True)
        return render(request, 'views/dashboard/store-setup-wizard.html', {
            'allowed_countries': allowed_countries,
            'is_online_store_supported': True,
            'biz': models.BusinessDetails()
        })

from django.shortcuts import redirect

@login_required
def store_settings_view(request):
    from api.functions import misc
    from api.functions.subscription_validation import SubscriptionManager
    from api.models import SubscriptionPlans
    try:
        user = misc.get_owner_from_user(request.user)
        business = models.BusinessDetails.objects.filter(user=user).first()
        
        if not business or not business.store_setup:
            return redirect('/store/')
            
        is_online_store_supported = False
        sub_manager = SubscriptionManager(user)
        try:
            sub_manager.require_online_store()
            is_online_store_supported = True
        except:
            pass
            
        context = {
            'business': business,
            'is_online_store_supported': is_online_store_supported,
            'has_purchased_premium_layout': models.StoreLayoutPurchase.objects.filter(user=user).exists()
        }
        
        if not is_online_store_supported:
            from api.functions.subscription_validation import get_processed_subscription_context, format_currency_amount
            sub_ctx = get_processed_subscription_context(request.user)
            context.update(sub_ctx)
            raw_balance = calculate_total_balance(user)
            context['wallet_balance'] = raw_balance
            context['wallet_balance_display'] = format_currency_amount(raw_balance, sub_ctx['user_currency'])
            context['business_name'] = business.business_name if business else 'Your Business'
            
        return render(request, 'views/dashboard/store-settings.html', context)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error checking store eligibility: {e}")
        return redirect('/dashboard/')

@login_required
def store_layouts_page_view(request):
    """Render the Store Layouts selection page with pricing and ownership state."""
    try:
        user = misc.get_owner_from_user(request.user)
        business = models.BusinessDetails.objects.filter(user=user).first()
        
        active_layout = business.store_layout_template if (business and business.store_layout_template) else 'grid'
        user_currency = 'NGN'
        if user:
            user_details = models.UserDetails.objects.filter(user=user).first()
            if user_details and user_details.currency:
                user_currency = user_details.currency
                
        from api.templatetags.currency_tags import currency_symbol
        symbol = currency_symbol(user_currency)
        
        from api.user_data.domain_views import get_exchange_rate
        rate = get_exchange_rate(base_currency='NGN', target_currency=user_currency)
        
        raw_balance = calculate_total_balance(user)
        
        # Get user's purchased layouts
        purchased_qs = models.StoreLayoutPurchase.objects.filter(user=user)
        purchased_ids = set(purchased_qs.values_list('layout_id', flat=True))
        
        # Query all premium layout configs from DB
        from api.models import PremiumStoreLayout
        PremiumStoreLayout.objects.get_or_create(layout_id='luxe-horizon', defaults={'name': 'Horizon Luxe', 'price_ngn': 20000.00, 'is_active': True})
        PremiumStoreLayout.objects.get_or_create(layout_id='vanguard-atelier', defaults={'name': 'Atelier Vanguard', 'price_ngn': 25000.00, 'is_active': True})
        PremiumStoreLayout.objects.get_or_create(layout_id='metro-pulse', defaults={'name': 'Metro Pulse', 'price_ngn': 18000.00, 'is_active': True})
        PremiumStoreLayout.objects.get_or_create(layout_id='folio-press', defaults={'name': 'Folio Press', 'price_ngn': 22000.00, 'is_active': True})
        PremiumStoreLayout.objects.get_or_create(layout_id='premium-commerce-editorial', defaults={'name': 'Premium Commerce Editorial', 'price_ngn': 28000.00, 'is_active': True})
        
        premium_layouts_db = PremiumStoreLayout.objects.all().order_by('name')
        premium_layouts_data = {}
        for p in premium_layouts_db:
            price_ngn = float(p.price_ngn)
            if user_currency == 'NGN':
                price_local = price_ngn
            else:
                price_local = round(price_ngn * rate, 2)
                
            info = {
                'layout_id': p.layout_id,
                'name': p.name,
                'price_ngn': price_ngn,
                'price_local': price_local,
                'price_local_formatted': f"{price_local:,.2f}",
                'is_purchased': p.layout_id in purchased_ids,
                'is_active': p.is_active
            }
            premium_layouts_data[p.layout_id] = info
            premium_layouts_data[p.layout_id.replace('-', '_')] = info
            
        context = {
            'business': business,
            'active_layout': active_layout,
            'user_currency': user_currency,
            'currency_symbol': symbol,
            'user_balance': raw_balance,
            'user_balance_formatted': f"{raw_balance:,.2f}",
            'purchased_layout_ids': list(purchased_ids),
            'purchased_layout_ids_json': json.dumps(list(purchased_ids)),
            'premium_layouts_data': premium_layouts_data,
            'premium_layouts_json': json.dumps(premium_layouts_data),
            'has_purchased_premium_layout': len(purchased_ids) > 0,
            'exchange_rate': rate,
        }
        return render(request, 'views/dashboard/store-layouts.html', context)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return redirect('/dashboard/')

@api_view(['POST'])
def store_layout_buy_api(request):
    """API endpoint to purchase and unlock a premium store layout using wallet balance."""
    try:
        user_id = misc.get_id(request)
        if not user_id:
            return Response({'status': False, 'message': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
            
        user = models.UserSecure.objects.get(user_id=user_id)
        user_owner = misc.get_owner_from_user(user)
        business = models.BusinessDetails.objects.filter(user=user_owner).first()
        
        layout_id = (request.data.get('layout_id') or '').strip().lower()
        if not layout_id or layout_id not in ('luxe-horizon', 'vanguard-atelier', 'metro-pulse', 'folio-press', 'premium-commerce-editorial'):
            return Response({'status': False, 'message': 'Invalid layout specified.'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Check if already owned
        if models.StoreLayoutPurchase.objects.filter(user=user_owner, layout_id=layout_id).exists():
            return Response({
                'status': True,
                'message': 'You already own this theme layout!',
                'layout_id': layout_id,
                'already_owned': True
            })
            
        from api.models import PremiumStoreLayout
        layout_obj = PremiumStoreLayout.objects.filter(layout_id=layout_id).first()
        if not layout_obj or not layout_obj.is_active:
            return Response({'status': False, 'message': 'This theme layout is currently unavailable for purchase.'}, status=status.HTTP_400_BAD_REQUEST)
            
        price_ngn = float(layout_obj.price_ngn)
        
        # Determine user currency & exchange rate
        user_details = models.UserDetails.objects.filter(user=user_owner).first()
        user_currency = user_details.currency if (user_details and user_details.currency) else 'NGN'
        
        from api.user_data.domain_views import get_exchange_rate
        rate = get_exchange_rate(base_currency='NGN', target_currency=user_currency)
        
        if user_currency == 'NGN':
            price_local = price_ngn
        else:
            price_local = round(price_ngn * rate, 2)
            
        from api.templatetags.currency_tags import currency_symbol
        sym = currency_symbol(user_currency)
        
        with transaction.atomic():
            balance = calculate_total_balance(user_owner)
            if balance < price_local:
                return Response({
                    'status': False,
                    'message': f"Insufficient wallet balance. You need {sym}{price_local:,.2f} but have {sym}{balance:,.2f}."
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Debit user wallet via UserTransactions
            models.UserTransactions.objects.create(
                user=user_owner,
                trx_status='completed',
                trx_amount=price_local,
                trx_type='payment',
                trx_source='Theme Purchase',
                trx_currency=user_currency,
                description=f"Purchased Premium Store Layout: {layout_obj.name}",
                user_collection_id='LAYOUT-PURCHASE',
                destination_id=layout_id
            )
            
            # Record layout purchase
            models.StoreLayoutPurchase.objects.create(
                user=user_owner,
                business=business,
                layout_id=layout_id,
                amount_paid=price_local,
                currency=user_currency,
                amount_in_ngn=price_ngn,
                exchange_rate=rate
            )
            
            # Automatically activate theme for this store
            if business:
                business.store_layout_template = layout_id
                business.save()
                
        return Response({
            'status': True,
            'message': f"Successfully unlocked {layout_obj.name}! It is now active on your store.",
            'layout_id': layout_id,
            'new_balance': balance - price_local,
            'currency': user_currency
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'status': False, 'message': f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_default_layout_sections(layout_id, business=None):
    """Generate default Elementor-style section configurations for premium templates."""
    store_name = (business.store_name.strip() if (business and business.store_name) else '')
    store_desc = (business.store_description.strip() if (business and business.store_description) else '')

    if layout_id == 'vanguard-atelier':
        return [
            {
                'id': 'announcement_bar',
                'type': 'announcement',
                'name': 'Dispatch Notice Bar',
                'visible': True,
                'settings': {
                    'text': 'ATELIER VANGUARD: EDITION 2026 ACTIVE // WORLDWIDE DISPATCH AVAILABLE',
                    'show_badge': True,
                    'badge_text': 'DISPATCH 01',
                    'show_link': True,
                    'link_text': 'SYSTEM ARCHIVE',
                }
            },
            {
                'id': 'hero_banner',
                'type': 'hero',
                'name': 'Architectural Hero Space',
                'visible': True,
                'settings': {
                    'headline': store_name or '',
                    'tagline': store_desc or '',
                    'primary_button_text': 'Explore Inventory',
                    'secondary_button_text': 'View Monograph',
                    'show_cta': True,
                    'show_secondary_btn': True,
                    'show_floating_badge': True,
                    'floating_badge_text': 'STUDIO SPEC 04.2',
                    'alignment': 'left',
                    'show_product_carousel': False,
                }
            },
            {
                'id': 'trust_pillars',
                'type': 'pillars',
                'name': 'Studio Tenets & Guarantees',
                'visible': True,
                'settings': {
                    'pillar_1_title': 'Precise Geometry',
                    'pillar_1_desc': 'Laser-calibrated design and materials',
                    'pillar_2_title': 'Zero-Trust Encryption',
                    'pillar_2_desc': 'Enterprise institutional settlement',
                    'pillar_3_title': 'Priority Express Logistics',
                    'pillar_3_desc': 'Direct tracked courier fulfillment',
                    'pillar_4_title': 'Direct Studio Access',
                    'pillar_4_desc': 'Direct dialogue with master designers',
                }
            },
            {
                'id': 'hot_products',
                'type': 'hot_products',
                'name': 'High-Velocity Releases',
                'visible': True,
                'settings': {
                    'title': 'High-Velocity Artifacts',
                    'subtitle': 'Current high-demand design objects moving through active fabrication cycles',
                    'show_flame_badge': True,
                    'show_prices': True,
                    'show_add_to_cart': True,
                    'max_items': 4,
                }
            },
            {
                'id': 'category_showcase',
                'type': 'categories',
                'name': 'Discipline Index (Categories)',
                'visible': True,
                'settings': {
                    'title': 'System Categories',
                    'subtitle': 'Catalog organized by structural domain',
                    'show_item_count': True,
                    'show_thumbnails': True,
                    'show_view_all': True,
                    'layout_mode': 'grid',
                }
            },
            {
                'id': 'product_grid',
                'type': 'products',
                'name': 'Core Inventory Matrix',
                'visible': True,
                'settings': {
                    'title': 'Primary Archive',
                    'subtitle': 'Available products and limited serial releases',
                    'columns': 3,
                    'items_per_page': 8,
                    'show_filter_tabs': True,
                    'show_prices': True,
                    'show_ratings': True,
                    'show_stock_badge': True,
                    'show_quick_add': True,
                }
            },
            {
                'id': 'brand_story',
                'type': 'brand_story',
                'name': 'Design Manifest & Atelier Ethos',
                'visible': True,
                'settings': {
                    'eyebrow': 'MANIFESTO // 001',
                    'headline': 'The Intersection of Architecture and Object',
                    'story_text': 'We reject disposable ornamentation in favor of tectonic clarity. Every product is drafted like a monument—engineered for permanence, calibrated for functional beauty, and stripped of excess.',
                    'stat_1_value': '0.01mm',
                    'stat_1_label': 'Machining Tolerance',
                    'stat_2_value': '100%',
                    'stat_2_label': 'Recycled Metallurgy',
                    'stat_3_value': '24/7',
                    'stat_3_label': 'Global Availability',
                    'show_stats': True,
                    'show_quote': True,
                    'quote_author': 'Studio Principal',
                }
            },
            {
                'id': 'brand_film',
                'type': 'video',
                'name': 'Studio Monograph (Video)',
                'visible': True,
                'settings': {
                    'title': 'Kinematic Archive // 001',
                    'subtitle': 'Laser-calibrated fabrication and material engineering in motion',
                    'source_type': 'youtube',
                    'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                    'video_url': '',
                    'poster_image': '',
                    'aspect_ratio': '16/9',
                    'width_mode': 'contained',
                    'autoplay': False,
                    'loop': False,
                    'muted': False,
                    'controls': True,
                    'caption': '',
                }
            },
            {
                'id': 'testimonials',
                'type': 'testimonials',
                'name': 'Client & Curator Dispatches',
                'visible': True,
                'settings': {
                    'title': 'Curator Dispatches',
                    'subtitle': 'Critical commentary and field accounts from global studio patrons',
                    'show_stars': True,
                    'show_verified_badge': True,
                    'show_avatars': True,
                    'columns': 3,
                }
            },
            {
                'id': 'newsletter',
                'type': 'newsletter',
                'name': 'Studio Registry & Telemetry',
                'visible': True,
                'settings': {
                    'headline': 'Register with the Atelier Wire',
                    'subtext': 'Receive release keys, blueprint previews, and limited edition serial announcements.',
                    'button_text': 'Authenticate Subscription',
                    'placeholder_text': 'patron@domain.com',
                    'show_incentive_note': True,
                    'incentive_note': 'Initial registry entitles client to prioritized dispatch sequencing.',
                }
            },
            {
                'id': 'blog_news',
                'type': 'blog',
                'name': 'Blog & News Dispatches',
                'visible': True,
                'settings': {
                    'title': 'Blog & News',
                    'subtitle': 'Latest editorial releases & dispatches',
                    'show_view_all': True,
                }
            },
            {
                'id': 'footer',
                'type': 'footer',
                'name': 'Studio Colophon & Footer',
                'visible': True,
                'settings': {
                    'show_social_links': True,
                    'show_payment_methods': True,
                    'show_policies_links': True,
                    'show_copyright': True,
                    'copyright_text': 'All rights reserved. Powered by FlezPay Enterprise.',
                }
            }
        ]
    elif layout_id == 'metro-pulse':
        return [
            {
                'id': 'announcement_bar',
                'type': 'announcement',
                'name': 'Announcement Bar',
                'visible': True,
                'settings': {
                    'text': 'Free Shipping on All Orders Over ₦10,000 · Fast & Tracked Delivery',
                    'show_badge': True,
                    'badge_text': 'NEW',
                    'show_link': True,
                    'link_text': 'Shop Now',
                }
            },
            {
                'id': 'hero_banner',
                'type': 'hero',
                'name': 'Hero Product Showcase',
                'visible': True,
                'settings': {
                    'headline': store_name or '',
                    'tagline': store_desc or '',
                    'primary_button_text': 'Shop Now',
                    'secondary_button_text': 'Explore All Products',
                    'show_cta': True,
                    'show_secondary_btn': True,
                    'show_floating_badge': True,
                    'floating_badge_text': 'New Arrivals 2026',
                    'alignment': 'left',
                    'show_product_carousel': True,
                }
            },
            {
                'id': 'trust_pillars',
                'type': 'pillars',
                'name': 'Trust & Quality Pillars',
                'visible': True,
                'settings': {
                    'pillar_1_title': 'Quality Guaranteed',
                    'pillar_1_desc': 'Every product rigorously verified before listing',
                    'pillar_2_title': 'Secure Checkout',
                    'pillar_2_desc': '256-bit encrypted payment processing',
                    'pillar_3_title': 'Fast Delivery',
                    'pillar_3_desc': 'Door-to-door express tracked shipping',
                    'pillar_4_title': '24/7 Support',
                    'pillar_4_desc': 'Always here to help you',
                }
            },
            {
                'id': 'hot_products',
                'type': 'hot_products',
                'name': 'Hot Right Now Carousel',
                'visible': True,
                'settings': {
                    'title': 'Hot Right Now',
                    'subtitle': 'Top-selling products this week',
                    'show_flame_badge': True,
                    'show_prices': True,
                    'show_add_to_cart': True,
                    'max_items': 6,
                }
            },
            {
                'id': 'category_showcase',
                'type': 'categories',
                'name': 'Shop by Category',
                'visible': True,
                'settings': {
                    'title': 'Shop by Category',
                    'subtitle': 'Find exactly what you are looking for',
                    'show_item_count': True,
                    'show_thumbnails': True,
                    'show_view_all': True,
                    'layout_mode': 'grid',
                }
            },
            {
                'id': 'product_grid',
                'type': 'products',
                'name': 'Primary Archive & Product Grid',
                'visible': True,
                'settings': {
                    'title': 'Primary Archive',
                    'subtitle': 'Available products and limited serial releases',
                    'columns': 3,
                    'items_per_page': 9,
                    'show_filter_tabs': True,
                    'show_prices': True,
                    'show_ratings': True,
                    'show_stock_badge': True,
                    'show_quick_add': True,
                }
            },
            {
                'id': 'brand_story',
                'type': 'brand_story',
                'name': 'Our Story & Stats',
                'visible': True,
                'settings': {
                    'eyebrow': 'OUR STORY',
                    'headline': 'Built for Shoppers Who Demand More',
                    'story_text': 'We curate the best products from trusted sellers and deliver them straight to your door with unmatched speed and reliability.',
                    'stat_1_value': '50K+',
                    'stat_1_label': 'Happy Customers',
                    'stat_2_value': '24h',
                    'stat_2_label': 'Delivery SLA',
                    'stat_3_value': '99%',
                    'stat_3_label': 'Satisfaction Rate',
                    'show_stats': True,
                    'show_quote': True,
                    'quote_author': 'Founder & CEO',
                }
            },
            {
                'id': 'brand_film',
                'type': 'video',
                'name': 'Video Spotlight',
                'visible': True,
                'settings': {
                    'title': 'Behind the Scenes & Product Motion',
                    'subtitle': 'Watch our latest product drops and brand showcase in action',
                    'source_type': 'youtube',
                    'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                    'video_url': '',
                    'poster_image': '',
                    'aspect_ratio': '16/9',
                    'width_mode': 'contained',
                    'autoplay': False,
                    'loop': False,
                    'muted': False,
                    'controls': True,
                    'caption': '',
                }
            },
            {
                'id': 'testimonials',
                'type': 'testimonials',
                'name': 'Customer Reviews',
                'visible': True,
                'settings': {
                    'title': 'What Our Customers Say',
                    'subtitle': 'Real reviews from real customers',
                    'show_stars': True,
                    'show_verified_badge': True,
                    'show_avatars': True,
                    'columns': 3,
                    'review_1_text': 'Absolutely amazing quality. The product arrived exactly as described and the packaging was superb.',
                    'review_1_author': 'James K.',
                    'review_2_text': 'Fastest shipping I have ever experienced. Will definitely order again from this store.',
                    'review_2_author': 'Amara T.',
                    'review_3_text': 'Outstanding customer support and top-notch product quality. Highly recommended!',
                    'review_3_author': 'Olivia M.',
                }
            },
            {
                'id': 'newsletter',
                'type': 'newsletter',
                'name': 'Newsletter Signup',
                'visible': True,
                'settings': {
                    'headline': 'Stay in the Loop',
                    'subtext': 'Get the latest deals, new arrivals, and exclusive offers delivered to your inbox.',
                    'button_text': 'Subscribe',
                    'placeholder_text': 'Enter your email address',
                    'show_incentive_note': True,
                    'incentive_note': 'Subscribe today and get 10% off your first order!',
                }
            },
            {
                'id': 'blog_news',
                'type': 'blog',
                'name': 'Blog & News',
                'visible': True,
                'settings': {
                    'title': 'Blog & News',
                    'subtitle': 'Latest articles and updates from our team',
                    'show_view_all': True,
                }
            },
            {
                'id': 'footer',
                'type': 'footer',
                'name': 'Footer',
                'visible': True,
                'settings': {
                    'show_social_links': True,
                    'show_payment_methods': True,
                    'show_policies_links': True,
                    'show_copyright': True,
                    'copyright_text': 'All rights reserved. Powered by FlezPay.',
                }
            }
        ]
    elif layout_id == 'premium-commerce-editorial':
        return [
            {
                'id': 'announcement_bar',
                'type': 'announcement',
                'name': 'Announcement Bar',
                'visible': True,
                'settings': {
                    'text': 'Free shipping on selected orders. Shop now.',
                    'show_badge': False,
                    'show_link': True,
                    'link_text': 'Learn more',
                }
            },
            {
                'id': 'hero_banner',
                'type': 'hero',
                'name': 'Editorial Hero',
                'visible': True,
                'settings': {
                    'headline': store_name or 'Premium Commerce',
                    'tagline': store_desc or 'Cover up front of book and leave summary',
                    'primary_button_text': 'Shopping Now',
                    'show_cta': True,
                    'alignment': 'center',
                    'show_product_carousel': True,
                }
            },
            {
                'id': 'trust_pillars',
                'type': 'pillars',
                'name': 'Service Features',
                'visible': True,
                'settings': {
                    'pillar_1_title': 'Free Shipping',
                    'pillar_1_desc': 'Orders over $50',
                    'pillar_2_title': 'Money Back Guarantee',
                    'pillar_2_desc': '30-day return policy',
                    'pillar_3_title': 'Cash on Delivery',
                    'pillar_3_desc': 'Available nationwide',
                    'pillar_4_title': 'Help & Support',
                    'pillar_4_desc': '24/7 customer service',
                }
            },
            {
                'id': 'promo_banners',
                'type': 'feature_columns',
                'name': 'Promotional Banners',
                'visible': True,
                'settings': {
                    'title': 'Current Offers',
                    'subtitle': 'Check out our latest campaigns',
                }
            },
            {
                'id': 'collection_tabs',
                'type': 'categories',
                'name': 'Collection Tabs',
                'visible': True,
                'settings': {
                    'title': 'Shop by Category',
                    'show_item_count': True,
                    'layout_mode': 'grid',
                }
            },
            {
                'id': 'main_products',
                'type': 'products',
                'name': 'Product Grid',
                'visible': True,
                'settings': {
                    'title': 'Latest Arrivals',
                    'subtitle': 'Fresh additions to our catalog',
                }
            },
            {
                'id': 'deal_of_day',
                'type': 'promo_banner',
                'name': 'Deal of the Day',
                'visible': True,
                'settings': {
                    'headline': 'Deal of the day up to 20% off Special offer',
                    'tagline': 'Up to 50% off select items',
                    'button_text': 'Shop the Deal',
                    'show_cta': True,
                }
            },
            {
                'id': 'featured_editorial',
                'type': 'brand_story',
                'name': 'Featured Editorial',
                'visible': True,
                'settings': {
                    'title': 'Curated Collection',
                    'content': 'Discover products hand-picked by our editors.',
                }
            },
            {
                'id': 'bestsellers',
                'type': 'hot_products',
                'name': 'Bestsellers',
                'visible': True,
                'settings': {
                    'title': 'Best Sellers',
                    'subtitle': 'Most loved by our customers',
                }
            },
            {
                'id': 'media_banner',
                'type': 'video',
                'name': 'Large Media Banner',
                'visible': True,
                'settings': {
                    'title': 'Experience Our Quality',
                    'subtitle': 'Watch our latest brand video',
                }
            },
            {
                'id': 'secondary_collection',
                'type': 'products',
                'name': 'Secondary Collection',
                'visible': True,
                'settings': {
                    'title': 'More to Explore',
                    'subtitle': 'Secondary product showcase',
                }
            },
            {
                'id': 'campaign_cta',
                'type': 'rich_text',
                'name': 'Campaign CTA',
                'visible': True,
                'settings': {
                    'title': 'Join Our Campaign',
                    'content': 'Sign up to get the latest deals and exclusive offers.',
                    'show_button': True,
                    'button_text': 'Learn More',
                }
            },
            {
                'id': 'blog_news',
                'type': 'blog',
                'name': 'Blog & News',
                'visible': True,
                'settings': {
                    'title': 'Latest from the Blog',
                    'subtitle': 'News, stories, and tips',
                }
            },
            {
                'id': 'social_gallery',
                'type': 'image_gallery',
                'name': 'Social Gallery',
                'visible': True,
                'settings': {
                    'title': 'Follow Us on Instagram',
                    'subtitle': '@yourbrand',
                }
            },
            {
                'id': 'footer',
                'type': 'footer',
                'name': 'Footer',
                'visible': True,
                'settings': {
                    'show_social_links': True,
                    'show_payment_methods': True,
                    'show_policies_links': True,
                    'show_copyright': True,
                    'copyright_text': 'Copyright © 2026. All rights reserved.',
                }
            }
        ]
    else:  # luxe-horizon (default)
        return [
            {
                'id': 'announcement_bar',
                'type': 'announcement',
                'name': 'Announcement Bar',
                'visible': True,
                'settings': {
                    'text': 'Complimentary White-Glove Delivery on Orders Over $500 • Exclusive Horizon Salon Access',
                    'show_badge': True,
                    'badge_text': 'VIP ACCESS',
                    'show_link': True,
                    'link_text': 'Discover Curations',
                }
            },
            {
                'id': 'hero_banner',
                'type': 'hero',
                'name': 'Hero Showcase',
                'visible': True,
                'settings': {
                    'headline': store_name or '',
                    'tagline': store_desc or '',
                    'primary_button_text': 'Shop the Collection',
                    'secondary_button_text': 'View Lookbook',
                    'show_cta': True,
                    'show_secondary_btn': True,
                    'show_floating_badge': True,
                    'floating_badge_text': 'Spring/Summer 2026 Curations',
                    'alignment': 'left',
                    'show_product_carousel': False,
                }
            },
            {
                'id': 'trust_pillars',
                'type': 'pillars',
                'name': 'Luxury Brand Pillars',
                'visible': True,
                'settings': {
                    'pillar_1_title': 'Artisanal Craftsmanship',
                    'pillar_1_desc': 'Handcrafted with unmatched precision and precious materials',
                    'pillar_2_title': 'Secured Escrow Vault',
                    'pillar_2_desc': 'Institutional 256-bit encrypted checkout protection',
                    'pillar_3_title': 'Insured Worldwide Delivery',
                    'pillar_3_desc': 'Direct door-to-door express fulfillment with tracking',
                    'pillar_4_title': 'Private Concierge',
                    'pillar_4_desc': 'Dedicated personal advisory team for all patrons',
                }
            },
            {
                'id': 'hot_products',
                'type': 'hot_products',
                'name': 'Hot Products Carousel',
                'visible': True,
                'settings': {
                    'title': 'Atelier Curations',
                    'subtitle': 'Pieces of exquisite design commanding timeless demand',
                    'show_flame_badge': True,
                    'show_prices': True,
                    'show_add_to_cart': True,
                    'max_items': 4,
                }
            },
            {
                'id': 'category_showcase',
                'type': 'categories',
                'name': 'Collections Showcase',
                'visible': True,
                'settings': {
                    'title': 'Signature Collections',
                    'subtitle': 'Browse by bespoke curated discipline and style',
                    'show_item_count': True,
                    'show_thumbnails': True,
                    'show_view_all': True,
                    'layout_mode': 'grid',
                }
            },
            {
                'id': 'product_grid',
                'type': 'products',
                'name': 'Catalog & Product Grid',
                'visible': True,
                'settings': {
                    'title': 'The Master Catalog',
                    'subtitle': 'All items available for instant acquisition',
                    'columns': 3,
                    'items_per_page': 8,
                    'show_filter_tabs': True,
                    'show_prices': True,
                    'show_ratings': True,
                    'show_stock_badge': True,
                    'show_quick_add': True,
                }
            },
            {
                'id': 'brand_story',
                'type': 'brand_story',
                'name': 'Best Seller Books (Author Spotlight)',
                'visible': True,
                'settings': {
                    'headline': 'BEST SELLER BOOKS',
                    'author_name': 'John Sparks',
                    'author_image': 'https://smartbook-theme.myshopify.com/cdn/shop/files/img-module1-340x388_340x388.jpg',
                }
            },
            {
                'id': 'brand_film',
                'type': 'video',
                'name': 'Atelier Cinema (Video)',
                'visible': True,
                'settings': {
                    'title': 'The Horizon Monograph',
                    'subtitle': 'A visual journey through artisanal craft, timeless design, and unmatched materials',
                    'source_type': 'youtube',
                    'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                    'video_url': '',
                    'poster_image': '',
                    'aspect_ratio': '16/9',
                    'width_mode': 'contained',
                    'autoplay': False,
                    'loop': False,
                    'muted': False,
                    'controls': True,
                    'caption': '',
                }
            },
            {
                'id': 'testimonials',
                'type': 'testimonials',
                'name': 'Customer Testimonials',
                'visible': True,
                'settings': {
                    'title': 'Patron Acclaim',
                    'subtitle': 'Verified feedback from collectors and connoisseurs',
                    'show_stars': True,
                    'show_verified_badge': True,
                    'show_avatars': True,
                    'columns': 3,
                }
            },
            {
                'id': 'newsletter',
                'type': 'newsletter',
                'name': 'VIP Privilege Club',
                'visible': True,
                'settings': {
                    'headline': 'Join the Horizon Circle',
                    'subtext': 'Receive private previews, invite-only salon drops, and bespoke event invitations directly to your correspondence.',
                    'button_text': 'Request Invitation',
                    'placeholder_text': 'Enter your private email address...',
                    'show_incentive_note': True,
                    'incentive_note': 'Enjoy 10% complimentary courtesy on your debut order',
                }
            },
            {
                'id': 'blog_news',
                'type': 'blog',
                'name': 'The Journal & Stories',
                'visible': True,
                'settings': {
                    'title': 'Blog & News',
                    'subtitle': 'Curated stories and editorial releases',
                    'show_view_all': True,
                }
            },
            {
                'id': 'footer',
                'type': 'footer',
                'name': 'Store Footer',
                'visible': True,
                'settings': {
                    'show_social_links': True,
                    'show_payment_methods': True,
                    'show_policies_links': True,
                    'show_copyright': True,
                    'copyright_text': 'All rights reserved. Powered by FlezPay Enterprise.',
                }
            }
        ]


@login_required
def store_builder_view(request):
    """Elementor-style visual website builder for premium storefront layouts."""
    try:
        user = misc.get_owner_from_user(request.user)
        business = models.BusinessDetails.objects.filter(user=user).first()

        layout_id = request.GET.get('layout', 'luxe-horizon').strip().lower()
        if layout_id not in ('luxe-horizon', 'vanguard-atelier', 'metro-pulse', 'folio-press', 'premium-commerce-editorial'):
            layout_id = 'luxe-horizon'
            
        # Ensure user has purchased this premium layout before allowing access to builder
        from django.contrib import messages
        from django.shortcuts import redirect
        if not models.StoreLayoutPurchase.objects.filter(user=user, layout_id=layout_id).exists():
            messages.error(request, "You must purchase this premium layout to access its builder.")
            return redirect('/store-layouts')

        layout_names = {
            'luxe-horizon': 'Horizon Luxe',
            'vanguard-atelier': 'Atelier Vanguard',
            'metro-pulse': 'Metro Pulse',
            'folio-press': 'Folio Press',
            'premium-commerce-editorial': 'Premium Commerce Editorial',
        }
        layout_name = layout_names.get(layout_id, 'Horizon Luxe')

        user_currency = 'NGN'
        if user:
            user_details = models.UserDetails.objects.filter(user=user).first()
            if user_details and user_details.currency:
                user_currency = user_details.currency
        from api.templatetags.currency_tags import currency_symbol
        symbol = currency_symbol(user_currency)

        # Get or create layout customization
        customization, _ = models.StoreLayoutCustomization.objects.get_or_create(
            business=business,
            layout_id=layout_id,
            defaults={
                'sections_config': get_default_layout_sections(layout_id, business=business),
                'custom_elements': [],
                'general_settings': {}
            }
        )

        sections_config = customization.sections_config
        if not sections_config:
            sections_config = get_default_layout_sections(layout_id, business=business)
            customization.sections_config = sections_config
            customization.save()

        # Ensure hero headline and tagline reflect store details if using template preset defaults
        for sec in sections_config:
            if isinstance(sec, dict) and sec.get('type') == 'hero':
                s_settings = sec.setdefault('settings', {})
                if s_settings.get('headline') in ('ATELIER VANGUARD SPATIAL LAB', 'HAUTE HORIZONS & TIMELESS PRESTIGE', '', None):
                    s_settings['headline'] = business.store_name if (business and business.store_name) else ''
                if s_settings.get('tagline') in (
                    'Form follows future. Monolithic artifacts, precision industrial crafts, and brutalist lifestyle apparatus.',
                    'Bespoke fine objects and opulent living designed for the modern connoisseur of world-class luxury.',
                    '',
                    None
                ):
                    s_settings['tagline'] = business.store_description if (business and business.store_description) else ''
                if business and business.store_banner and not s_settings.get('cover_image'):
                    try:
                        s_settings['cover_image'] = business.store_banner.url
                    except Exception:
                        pass

        # Fetch products from user's store
        items = []
        categories = []
        if business and business.user:
            items_qs = models.UserItems.objects.filter(user=business.user, in_store=True).order_by('-timestamp')[:12]
            for it in items_qs:
                first_img = it.images.first()
                img_url = first_img.image.url if (first_img and first_img.image) else '/static/assets/image/placeholder-product.png'
                item_price = float(it.item_amount or 0.0)
                items.append({
                    'id': it.id,
                    'name': it.item_name,
                    'price': item_price,
                    'price_formatted': f"{symbol}{item_price:,.2f}",
                    'category': it.item_category or 'General',
                    'image': img_url,
                    'is_featured': getattr(it, 'is_featured', False),
                    'quantity': it.item_quantity or 10,
                })
            cat_list = models.UserItems.objects.filter(user=business.user, in_store=True).values_list('item_category', flat=True).distinct()
            categories = [c for c in cat_list if c]

        # Compute max promo discount percentage for builder and dynamic banner headline
        promo_context = get_promo_context(business) if business else {'promo_active': False, 'promo_percentage': 0}
        candidates = []
        if promo_context.get('promo_active') and promo_context.get('promo_percentage'):
            try:
                p_val = int(promo_context['promo_percentage'])
                if p_val > 0:
                    candidates.append(p_val)
            except (ValueError, TypeError):
                pass
        if business and business.user:
            all_promo_items = models.UserItems.objects.filter(user=business.user, in_store=True, is_promo=True)
            for it in all_promo_items:
                p_val = getattr(it, 'promo_amount', None)
                if p_val is not None:
                    try:
                        val = float(p_val)
                        if 0 < val <= 100:
                            candidates.append(round(val))
                    except (ValueError, TypeError):
                        pass
        highest_discount = max(candidates) if candidates else 20
        banner_deal_headline = f"Deal of the day up to {highest_discount}% off Special offer"

        for sec in sections_config:
            if isinstance(sec, dict) and (sec.get('type') == 'promo_banner' or sec.get('id') == 'deal_of_day'):
                s_settings = sec.setdefault('settings', {})
                curr_headline = s_settings.get('headline')
                if not curr_headline or curr_headline in ('Deal of the Day', 'MEGA PROMO: 50% OFF TODAY!') or curr_headline.startswith('Deal of the day'):
                    s_settings['headline'] = banner_deal_headline

        store_banner_url = business.store_banner.url if (business and business.store_banner) else ''
        store_logo_url = business.business_image.url if (business and business.business_image) else ''

        context = {
            'business': business,
            'layout_id': layout_id,
            'layout_name': layout_name,
            'user_currency': user_currency,
            'currency_symbol': symbol,
            'store_banner_url': store_banner_url,
            'store_logo_url': store_logo_url,
            'store_authors_json': json.dumps(business.store_authors or []),
            'store_featured_author': business.store_featured_author or '',
            'store_featured_author_image': business.store_featured_author_image or '',
            'sections_config': sections_config,
            'sections_config_json': json.dumps(sections_config),
            'custom_elements_json': json.dumps(customization.custom_elements or []),
            'general_settings_json': json.dumps(customization.general_settings or {}),
            'max_promo_percentage': highest_discount,
            'banner_deal_headline': banner_deal_headline,
            'store_settings_json': json.dumps({
                'store_name': business.store_name or business.business_name or '',
                'store_description': business.store_description or '',
                'hide_store_name': bool(business.hide_store_name),
                'hide_hot_products': bool(business.hide_hot_products),
                'store_banner_url': store_banner_url,
                'store_logo_url': store_logo_url,
                'store_authors': business.store_authors or [],
                'store_featured_author': business.store_featured_author or '',
                'store_featured_author_image': business.store_featured_author_image or '',
                'max_promo_percentage': highest_discount,
            }),
            'store_items_json': json.dumps(items),
            'store_categories_json': json.dumps(categories),
        }
        return render(request, 'views/dashboard/store-builder.html', context)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return redirect('/store-layouts')


@api_view(['POST'])
def store_builder_save_api(request):
    """Save builder section order, visibility, custom elements, and section settings."""
    try:
        user_id = None
        try:
            user_id = misc.get_id(request)
        except Exception:
            user_id = None
        if not user_id and request.user and request.user.is_authenticated:
            user_id = getattr(request.user, 'user_id', None)
        if not user_id:
            return Response({'status': False, 'message': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        user = models.UserSecure.objects.get(user_id=user_id)
        user_owner = misc.get_owner_from_user(user)
        business = models.BusinessDetails.objects.filter(user=user_owner).first()
        if not business:
            return Response({'status': False, 'message': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)

        layout_id = (request.data.get('layout_id') or 'luxe-horizon').strip().lower()
        sections_config = request.data.get('sections_config')
        custom_elements = request.data.get('custom_elements', [])
        general_settings = request.data.get('general_settings', {})
        store_settings = request.data.get('store_settings', {})

        if not isinstance(sections_config, list):
            return Response({'status': False, 'message': 'Invalid sections configuration format'}, status=status.HTTP_400_BAD_REQUEST)

        # Remove popular authors from layout sections
        sections_config = [
            sec for sec in sections_config
            if isinstance(sec, dict) and sec.get('type') != 'authors'
        ]

        # Clean up any template preset strings so they are never saved in DB
        for sec in sections_config:
            if isinstance(sec, dict) and sec.get('type') == 'hero':
                s_settings = sec.setdefault('settings', {})
                if s_settings.get('tagline') in (
                    'Form follows future. Monolithic artifacts, precision industrial crafts, and brutalist lifestyle apparatus.',
                    'Bespoke fine objects and opulent living designed for the modern connoisseur of world-class luxury.',
                ):
                    s_settings['tagline'] = business.store_description or ''
                if s_settings.get('headline') in (
                    'ATELIER VANGUARD SPATIAL LAB',
                    'HAUTE HORIZONS & TIMELESS PRESTIGE',
                    'METRO PULSE STORE',
                ):
                    s_settings['headline'] = business.store_name or ''

        customization, _ = models.StoreLayoutCustomization.objects.get_or_create(
            business=business,
            layout_id=layout_id
        )
        customization.sections_config = sections_config
        customization.custom_elements = custom_elements
        customization.general_settings = general_settings
        customization.save()

        # Update core storefront settings if provided
        if isinstance(store_settings, dict) and store_settings:
            if 'store_name' in store_settings and store_settings['store_name']:
                business.store_name = str(store_settings['store_name']).strip()
            if 'store_description' in store_settings:
                business.store_description = str(store_settings['store_description']).strip()
            if 'hide_store_name' in store_settings:
                business.hide_store_name = bool(store_settings['hide_store_name'])
            if 'hide_hot_products' in store_settings:
                business.hide_hot_products = bool(store_settings['hide_hot_products'])
            if store_settings.get('clear_store_banner') or ('store_banner_url' in store_settings and not store_settings.get('store_banner_url')):
                business.store_banner = None
            elif store_settings.get('store_banner_url') and str(store_settings['store_banner_url']).startswith('data:image'):
                import base64
                from django.core.files.base import ContentFile
                try:
                    format_part, imgstr = store_settings['store_banner_url'].split(';base64,')
                    ext = format_part.split('/')[-1]
                    banner_data = base64.b64decode(imgstr)
                    business.store_banner.save(f"banner_{business.id}.{ext}", ContentFile(banner_data), save=False)
                except Exception as b_err:
                    print("Error decoding banner base64:", b_err)

        # Keep business active layout template aligned with saved builder layout
        if layout_id in ['vanguard-atelier', 'luxe-horizon', 'metro-pulse', 'folio-press', 'premium-commerce-editorial', 'grid', 'minimal', 'modern']:
            business.store_layout_template = layout_id
        business.save()

        return Response({
            'status': True,
            'message': 'Layout changes saved successfully.'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'status': False, 'message': f'Error saving layout: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def store_builder_reset_api(request):
    """Reset builder configuration back to layout defaults."""
    try:
        user_id = None
        try:
            user_id = misc.get_id(request)
        except Exception:
            user_id = None
        if not user_id and request.user and request.user.is_authenticated:
            user_id = getattr(request.user, 'user_id', None)
        if not user_id:
            return Response({'status': False, 'message': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        user = models.UserSecure.objects.get(user_id=user_id)
        user_owner = misc.get_owner_from_user(user)
        business = models.BusinessDetails.objects.filter(user=user_owner).first()
        if not business:
            return Response({'status': False, 'message': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)

        layout_id = (request.data.get('layout_id') or 'luxe-horizon').strip().lower()
        default_sections = get_default_layout_sections(layout_id)

        customization, _ = models.StoreLayoutCustomization.objects.get_or_create(
            business=business,
            layout_id=layout_id
        )
        customization.sections_config = default_sections
        customization.custom_elements = []
        customization.general_settings = {}
        customization.save()

        if layout_id in ['vanguard-atelier', 'luxe-horizon', 'metro-pulse', 'folio-press', 'premium-commerce-editorial', 'grid', 'minimal', 'modern']:
            business.store_layout_template = layout_id
            business.save()

        return Response({
            'status': True,
            'message': 'Layout reset to defaults.',
            'sections_config': default_sections
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'status': False, 'message': f'Error resetting layout: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def store_builder_upload_video_api(request):
    """
    Upload a video file or poster image for store layout video sections.
    Enforces format validation and 30 MB size limit.
    """
    try:
        user_id = None
        try:
            user_id = misc.get_id(request)
        except Exception:
            user_id = None
        if not user_id and request.user and request.user.is_authenticated:
            user_id = getattr(request.user, 'user_id', None)
        if not user_id:
            return Response({'status': False, 'message': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
        user = models.UserSecure.objects.get(user_id=user_id)
        user_owner = misc.get_owner_from_user(user)
        business = models.BusinessDetails.objects.filter(user=user_owner).first()
        if not business:
            return Response({'status': False, 'message': 'Business not found'}, status=status.HTTP_404_NOT_FOUND)

        uploaded = request.FILES.get('video') or request.FILES.get('file')
        if not uploaded:
            return Response({'status': False, 'message': 'No video or media file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce size limit (30 MB for video)
        MAX_VIDEO_BYTES = 30 * 1024 * 1024
        if uploaded.size > MAX_VIDEO_BYTES:
            return Response({
                'status': False,
                'message': 'File exceeds maximum allowed size of 30 MB. Please upload a smaller video or link a YouTube URL.'
            }, status=status.HTTP_400_BAD_REQUEST)

        name_lower = uploaded.name.lower()
        _, ext = os.path.splitext(name_lower)
        ALLOWED_VIDEO_EXTS = {'.mp4', '.webm', '.ogg', '.mov', '.m4v'}
        ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

        is_video = ext in ALLOWED_VIDEO_EXTS
        is_image = ext in ALLOWED_IMAGE_EXTS

        if not is_video and not is_image:
            return Response({
                'status': False,
                'message': f'Unsupported file type ({ext}). Allowed formats: MP4, WebM, OGG, MOV (or JPEG/PNG/WebP for poster).'
            }, status=status.HTTP_400_BAD_REQUEST)

        safe_filename = f"store_video_{business.id}_{uuid.uuid4().hex}{ext}"

        from flezpay.storage import StoreVideoStorage, BrandStorage
        if is_video:
            storage = StoreVideoStorage()
        else:
            storage = BrandStorage()

        saved_name = storage.save(safe_filename, uploaded)
        file_url = storage.url(saved_name)

        return Response({
            'status': True,
            'message': 'Video uploaded successfully' if is_video else 'Poster image uploaded successfully',
            'url': file_url,
            'is_video': is_video,
            'filename': uploaded.name,
            'size': uploaded.size
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'status': False, 'message': f'Upload error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def pos_page_view(request):
    allowed_countries = models.AllowedCountries.objects.filter(is_active=True)
    return render(request, 'views/dashboard/pos.html', {'allowed_countries': allowed_countries})

def blog_list_view(request):
    """Global Blog List View"""
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    page = request.GET.get('page', 1)
    
    posts = models.BlogPost.objects.filter(is_published=True).order_by('-timestamp')
    
    if query:
        import re as regex_tool
        terms = [query]
        if query.lower().endswith('s') and len(query) > 3:
            terms.append(query[:-1])
        elif len(query) > 3:
            terms.append(query + 's')
            
        # Support multi-word or hyphenated search terms like "AI Insights", "Cross-Border"
        subwords = [w.strip() for w in regex_tool.split(r'[\s\-_]+', query) if len(w.strip()) >= 2]
        if len(subwords) > 1:
            for w in subwords:
                if w.lower() not in [t.lower() for t in terms]:
                    terms.append(w)
                    if w.lower().endswith('s') and len(w) > 3:
                        terms.append(w[:-1])
                    elif len(w) > 3:
                        terms.append(w + 's')
            
        q_filter = Q()
        for term in terms:
            q_filter |= Q(title__icontains=term) | Q(content__icontains=term) | Q(summary__icontains=term) | Q(category__name__icontains=term)
        posts = posts.filter(q_filter).distinct()
        
    if category:
        posts = posts.filter(category__name__iexact=category)
        
    # Get unique categories for the sidebar
    categories = models.BlogCategory.objects.filter(blogpost__is_published=True).values_list('name', flat=True).distinct()
    recent_posts = models.BlogPost.objects.filter(is_published=True).order_by('-timestamp')[:3]
    keywords = ['Retail POS', 'Inventory', 'Omnichannel', 'AI Insights', 'Storefronts', 'Cross-Border', 'Payments', 'Payroll']
    
    paginator = Paginator(posts, 4)
    page_obj = paginator.get_page(page)
    
    return render(request, 'views/public/blog.html', {
        'posts': page_obj,
        'page_obj': page_obj,
        'query': query,
        'current_category': category,
        'categories': sorted(categories),
        'recent_posts': recent_posts,
        'keywords': keywords,
    })

def blog_details_view(request, slug):
    """Global Blog Details View with functional comments and social sharing"""
    post = get_object_or_404(models.BlogPost, slug=slug, is_published=True)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        comment_text = request.POST.get('comment', '').strip()
        parent_id = request.POST.get('parent_id', '').strip()
        
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'
        
        if not name or not email or not comment_text:
            if is_ajax:
                return JsonResponse({'status': False, 'message': 'Please fill in all required fields (Name, Email, and Comment).'}, status=400)
            return redirect(f"/blog/{slug}?error=missing_fields#comment-form")
            
        parent_comment = None
        if parent_id and parent_id.isdigit():
            parent_comment = models.BlogComment.objects.filter(uniq_id=int(parent_id), post=post).first()
            
        new_comment = models.BlogComment.objects.create(
            post=post,
            name=name,
            email=email,
            comment=comment_text,
            parent=parent_comment,
            is_approved=True,
        )
        
        if is_ajax:
            return JsonResponse({
                'status': True,
                'message': 'Your comment has been posted successfully!',
                'comment_id': new_comment.uniq_id,
            })
        return redirect(f"/blog/{slug}?comment_posted=1#comments")

    recent_posts = models.BlogPost.objects.filter(is_published=True).exclude(pk=post.pk).order_by('-timestamp')[:3]
    if not recent_posts.exists():
        recent_posts = models.BlogPost.objects.filter(is_published=True).order_by('-timestamp')[:3]
    categories = models.BlogCategory.objects.filter(blogpost__is_published=True).values_list('name', flat=True).distinct()
    keywords = ['Retail POS', 'Inventory', 'Omnichannel', 'AI Insights', 'Storefronts', 'Cross-Border', 'Payments', 'Payroll']
    
    comments = post.comments.filter(is_approved=True, parent__isnull=True).prefetch_related('replies').order_by('-timestamp')
    comments_count = post.comments.filter(is_approved=True).count()
    
    comment_posted = request.GET.get('comment_posted') == '1'
    comment_error = request.GET.get('error')

    return render(request, 'views/public/blog-details.html', {
        'post': post,
        'recent_posts': recent_posts,
        'categories': sorted(categories),
        'keywords': keywords,
        'comments': comments,
        'comments_count': comments_count,
        'comment_posted': comment_posted,
        'comment_error': comment_error,
    })

def help_center_view(request):
    """Global Help Center View"""
    query = request.GET.get('q', '').strip()
    page_number = request.GET.get('page', 1)

    if query:
        import re as regex_tool
        terms = [query]
        if query.lower().endswith('s') and len(query) > 3:
            terms.append(query[:-1])
        elif len(query) > 3:
            terms.append(query + 's')
            
        subwords = [w.strip() for w in regex_tool.split(r'[\s\-_]+', query) if len(w.strip()) >= 2]
        if len(subwords) > 1:
            for w in subwords:
                if w.lower() not in [t.lower() for t in terms]:
                    terms.append(w)
                    if w.lower().endswith('s') and len(w) > 3:
                        terms.append(w[:-1])
                    elif len(w) > 3:
                        terms.append(w + 's')

        q_filter = Q()
        for term in terms:
            q_filter |= Q(title__icontains=term) | Q(content__icontains=term) | Q(category__name__icontains=term)

        articles = models.HelpArticle.objects.filter(q_filter).distinct()
    else:
        articles = models.HelpArticle.objects.all()

    paginator = Paginator(articles.order_by('-timestamp'), 9)
    page_obj = paginator.get_page(page_number)

    return render(request, 'views/public/help-center.html', {
        'articles': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'query': query,
        'articles_count': articles.count(),
    })

def help_center_details_view(request, slug):
    """Global Help Center Details View"""
    article = get_object_or_404(models.HelpArticle, slug=slug)
    
    embed_url = None
    if article.youtube_video_url:
        import re as regex
        match = regex.search(r'(?:v=|youtu\.be/)([^&?]+)', article.youtube_video_url)
        if match:
            # Adding origin helps prevent Error 153 on some browsers/setups
            origin = request.build_absolute_uri('/')[:-1]
            embed_url = f"https://www.youtube.com/embed/{match.group(1)}?origin={origin}"
        else:
            embed_url = article.youtube_video_url

    return render(request, 'views/public/help-center-details.html', {
        'article': article,
        'embed_url': embed_url
    })

@xframe_options_exempt
def store_contact_submit(request, slug):
    """Handle Contact Form Submission for Store"""
    if not getattr(request, 'store_slug', None):
        raise Http404("Page not found")
        
    if request.method == 'POST':
        business = models.BusinessDetails.objects.filter(store_slug=slug).first()
        if not business:
            return JsonResponse({'status': False, 'message': 'Store not found'}, status=404)
            
        customer_email = request.POST.get('customer_email')
        customer_phone = request.POST.get('customer_phone')
        message_text = request.POST.get('message')
        
        if not customer_email or not message_text:
            return JsonResponse({'status': False, 'message': 'Email and message are required'})
            
        # Send Email
        subject = f"New Contact Message from {business.store_name} Store"
        body = f"You have received a new message from your store contact form.\n\n" \
               f"From: {customer_email}\n" \
               f"Phone: {customer_phone}\n\n" \
               f"Message:\n{message_text}"
               
        store_owner_email = business.user.user_email
        
        try:
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[store_owner_email],
                reply_to=[customer_email]
            )
            email.send()
            return JsonResponse({'status': True, 'message': 'Your message has been sent successfully.'})
        except Exception as e:
            return JsonResponse({'status': False, 'message': str(e)}, status=500)
            
    return JsonResponse({'status': False, 'message': 'Invalid request method'}, status=405)
    
def get_promo_context(business):
    promo_active = False
    if business.store_promo_enabled:
        if not business.store_promo_end_date or business.store_promo_end_date > timezone.now():
            promo_active = True
    return {
        'promo_active': promo_active,
        'promo_percentage': business.store_promo_percentage if promo_active else 0,
        'promo_end_date': business.store_promo_end_date.isoformat() if promo_active and business.store_promo_end_date else None
    }

import json
def get_store_open_context(business):
    hours = business.store_operating_hours
    if not hours:
        return {'is_store_open': True}
    
    if isinstance(hours, str):
        try:
            hours = json.loads(hours)
        except:
            return {'is_store_open': True}
            
    if isinstance(hours, dict) and hours.get('always_open'):
        return {'is_store_open': True}
            
    from django.utils import timezone
    now = timezone.localtime()
    
    day_name_lower = now.strftime('%A').lower()
    day_name_cap = now.strftime('%A')
    
    today_hours = hours.get(day_name_lower) or hours.get(day_name_cap) or {}
    
    if not today_hours:
        return {'is_store_open': True}
        
    if 'enabled' in today_hours:
        enabled_val = today_hours.get('enabled')
        if str(enabled_val).lower() == 'false' or enabled_val is False:
            return {'is_store_open': False}
            
    if str(today_hours.get('closed', '')).lower() == 'true' or today_hours.get('closed') is True:
        return {'is_store_open': False}
        
    if today_hours.get('is_24_hours') is True or str(today_hours.get('is_24_hours', '')).lower() == 'true':
        return {'is_store_open': True}
        
    open_time_str = today_hours.get('open')
    close_time_str = today_hours.get('close')
    
    if open_time_str and close_time_str:
        if open_time_str in ['00:00', '0:00'] and close_time_str in ['23:59', '24:00', '00:00', '0:00']:
            return {'is_store_open': True}
        try:
            open_time = datetime.strptime(open_time_str, '%H:%M').time()
            close_time = datetime.strptime(close_time_str, '%H:%M').time()
            current_time = now.time()
            
            if open_time <= close_time:
                is_open = open_time <= current_time <= close_time
            else: # Overnight
                is_open = current_time >= open_time or current_time <= close_time
            return {'is_store_open': is_open}
        except ValueError:
            return {'is_store_open': True}
            
    return {'is_store_open': True}


def enrich_item_promo(item, business, promo_context):
    item.first_image = item.images.first()
    try:
        item_amt = float(item.item_amount or 0)
    except (ValueError, TypeError):
        item_amt = 0.0

    pct = None
    if getattr(item, 'is_promo', False):
        p_val = getattr(item, 'promo_amount', None)
        if p_val is not None:
            try:
                val = float(p_val)
                if 0 < val <= 100:
                    pct = round(val)
            except (ValueError, TypeError):
                pass
        
        # If individual promo percentage is not set, inherit from store promo if active
        if pct is None:
            if promo_context.get('promo_active') and promo_context.get('promo_percentage'):
                pct = int(promo_context['promo_percentage'])
            elif getattr(business, 'store_promo_enabled', False) and getattr(business, 'store_promo_percentage', 0):
                pct = int(business.store_promo_percentage)
    elif promo_context.get('promo_active') and promo_context.get('promo_percentage'):
        pct = int(promo_context['promo_percentage'])

    if pct is not None and pct > 0:
        item.discount_percentage = int(pct)
        item.discounted_price = round(item_amt * (100 - item.discount_percentage) / 100.0, 2)
    else:
        item.discount_percentage = None
        item.discounted_price = None

    return item




@xframe_options_exempt
@never_cache
def store_page_view(request, slug, page_slug):
    """Public/Preview view for a store static page"""
    if not getattr(request, 'store_slug', None):
        raise Http404("Page not found")
        
    business = models.BusinessDetails.objects.filter(store_slug=slug).first()
    
    preview_layout = request.GET.get('preview_layout') or request.GET.get('layout')
    
    layout = preview_layout if preview_layout else (business.store_layout_template if business else 'grid')
    
    
    
    if not business or not business.is_published:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {'business': business}, status=404)
        
    titles = {
        'privacy': 'Privacy Policy',
        'terms': 'Terms of Service',
        'help': 'Help Center',
        'contact': 'Contact Us',
        'returns': 'Returns & Refunds',
        'new-arrivals': 'New Arrivals',
        'best-sellers': 'Best Sellers',
        'sale': 'Sale',
    }
    
    title = titles.get(page_slug, 'Page Not Found')
    
    user = business.user
    items = []
    
    if page_slug == 'new-arrivals':
        items_qs = list(models.UserItems.objects.filter(user=user, in_store=True, is_featured=True).order_by('-timestamp')[:20])
    elif page_slug == 'best-sellers':
        from django.db.models import Sum, IntegerField, Subquery, OuterRef
        from django.db.models.functions import Coalesce

        sales_subquery = models.UserInvoiceItems.objects.filter(
            item_id=OuterRef('item_id')
        ).values('item_id').annotate(
            total_sales=Sum('item_quantity')
        ).values('total_sales')

        items_qs = list(models.UserItems.objects.filter(user=user, in_store=True, is_featured=True).annotate(
            sales=Coalesce(Subquery(sales_subquery, output_field=IntegerField()), 0)
        ).order_by('-sales', '-timestamp')[:20])
        
    from django.core.paginator import Paginator
    page_number = request.GET.get('page', 1)
    paginator = Paginator(items_qs if 'items_qs' in locals() else [], 12)
    page_obj = paginator.get_page(page_number)
        
    for item in page_obj:
        item.first_image = item.images.first()
    all_items = models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)
    
    context = {
        'business': business,
        'page_slug': page_slug,
        'title': title,
        'items': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'all_items': all_items,
        'layout': layout,
    }
    context.update(get_promo_context(business))
    context.update(get_store_open_context(business))
    
    return render(request, f'views/store_layouts/{layout}/store-page.html', context)


PREMIUM_STORE_LAYOUTS = {'luxe-horizon', 'vanguard-atelier', 'metro-pulse', 'folio-press', 'premium-commerce-editorial'}

def ensure_default_store_blog_posts(business):
    """Do not seed blogs to new users (merchant blogs must be user created)"""
    return


@xframe_options_exempt
@never_cache
def store_blog_detail_view(request, slug, post_slug):
    """Public view for a store's blog article detail page (backend StoreBlogPost model driven)"""
    if not getattr(request, 'store_slug', None):
        request.store_slug = slug
        
    business = models.BusinessDetails.objects.filter(store_slug=slug).first()
    preview_layout = request.GET.get('preview_layout') or request.GET.get('layout')
    layout = preview_layout if preview_layout else (business.store_layout_template if business else 'grid')
    
    if not business or not business.is_published:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {'business': business}, status=404)
    
    if layout not in PREMIUM_STORE_LAYOUTS:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {
            'business': business,
            'layout': layout,
            'page_not_found': True,
        }, status=404)
    
    # Lookup article from merchant's StoreBlogPost
    post_obj = models.StoreBlogPost.objects.filter(business=business, slug=post_slug, is_published=True).first()
    if not post_obj:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {
            'business': business,
            'layout': layout,
            'page_not_found': True,
        }, status=404)
        
    # Increment view counter
    models.StoreBlogPost.objects.filter(uniq_id=post_obj.uniq_id).update(views_count=F('views_count') + 1)
    post_obj.refresh_from_db()
    
    # Related articles from StoreBlogPost
    related_articles = list(
        models.StoreBlogPost.objects.filter(business=business, is_published=True)
        .exclude(uniq_id=post_obj.uniq_id)
        .order_by('-created_at')[:2]
    )
    
    user = business.user
    recent_items = list(models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)[:4]) if user else []
    for itm in recent_items:
        itm.first_image = itm.images.first()
        
    categories = list(
        models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)
        .values('item_category')
        .annotate(count=Count('item_id'))
        .order_by('-count')
    ) if user else []
    for c in categories:
        c['name'] = c['item_category'] or 'General'
        
    all_items = list(models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)) if user else []

    context = {
        'business': business,
        'layout': layout,
        'article': post_obj,
        'related_articles': related_articles,
        'recent_items': recent_items,
        'categories': categories,
        'all_items': all_items,
    }
    context.update(get_promo_context(business))
    context.update(get_store_open_context(business))
    
    return render(request, f'views/store_layouts/{layout}/store-blog-detail.html', context)


@xframe_options_exempt
@never_cache
def store_blog_list_view(request, slug):
    """Public store blog listing page with search, filter, and pagination (backend StoreBlogPost model driven)"""
    if not getattr(request, 'store_slug', None):
        request.store_slug = slug
        
    business = models.BusinessDetails.objects.filter(store_slug=slug).first()
    preview_layout = request.GET.get('preview_layout') or request.GET.get('layout')
    layout = preview_layout if preview_layout else (business.store_layout_template if business else 'grid')
    
    if not business or not business.is_published:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {'business': business}, status=404)
    
    if layout not in PREMIUM_STORE_LAYOUTS:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {
            'business': business,
            'layout': layout,
            'page_not_found': True,
        }, status=404)

    # Query all published StoreBlogPost records from DB
    posts_qs = models.StoreBlogPost.objects.filter(business=business, is_published=True).order_by('-created_at')

    from django.utils.text import slugify
    # Ensure any categories on published posts exist in StoreBlogCategory
    existing_cat_names = set(models.StoreBlogCategory.objects.filter(business=business).values_list('name', flat=True))
    post_cat_names = set(models.StoreBlogPost.objects.filter(business=business, is_published=True).values_list('category', flat=True).distinct())
    for p_cat in post_cat_names:
        if p_cat and p_cat not in existing_cat_names:
            models.StoreBlogCategory.objects.get_or_create(business=business, name=p_cat, defaults={'slug': slugify(p_cat)})
            existing_cat_names.add(p_cat)

    # Dynamic categories and published counts from database
    db_categories = models.StoreBlogCategory.objects.filter(business=business).order_by('name')
    blog_categories = []
    for cat in db_categories:
        count = models.StoreBlogPost.objects.filter(business=business, category__iexact=cat.name, is_published=True).count()
        blog_categories.append({
            'name': cat.name,
            'count': count,
            'slug': cat.slug
        })

    # Filter by category
    category_filter = request.GET.get('category', '').strip()
    if category_filter and category_filter.lower() != 'all':
        posts_qs = posts_qs.filter(category__iexact=category_filter)

    # Filter by search query
    search_query = request.GET.get('q', '').strip()
    if search_query:
        posts_qs = posts_qs.filter(
            Q(title__icontains=search_query) |
            Q(summary__icontains=search_query) |
            Q(category__icontains=search_query) |
            Q(content__icontains=search_query)
        )

    all_filtered_posts = list(posts_qs)
    total_count = len(all_filtered_posts)

    # Featured post (hero left)
    featured_post = all_filtered_posts[0] if all_filtered_posts else None

    # Latest 4 posts (hero right)
    if featured_post:
        latest_posts = [p for p in all_filtered_posts if p.uniq_id != featured_post.uniq_id][:4]
        # For grid below hero: exclude featured article when on default view
        if not (category_filter or search_query):
            grid_posts = [p for p in all_filtered_posts if p.uniq_id != featured_post.uniq_id]
        else:
            grid_posts = all_filtered_posts
    else:
        latest_posts = []
        grid_posts = all_filtered_posts

    # Pagination: 3 articles per page matching the 3-column Founders Corner grid
    from django.core.paginator import Paginator
    paginator = Paginator(grid_posts, 3)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    user = business.user
    recent_items = list(models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)[:4]) if user else []
    for itm in recent_items:
        itm.first_image = itm.images.first()
        
    store_categories = list(
        models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)
        .values('item_category')
        .annotate(count=Count('item_id'))
        .order_by('-count')
    ) if user else []
    for c in store_categories:
        c['name'] = c['item_category'] or 'General'
        
    all_items = list(models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)) if user else []

    context = {
        'business': business,
        'layout': layout,
        'page_obj': page_obj,
        'articles': page_obj.object_list,
        'featured_article': featured_post,
        'latest_articles': latest_posts,
        'blog_categories': blog_categories,
        'active_category': category_filter,
        'search_query': search_query,
        'total_count': total_count,
        'recent_items': recent_items,
        'categories': store_categories,
        'all_items': all_items,
    }
    context.update(get_promo_context(business))
    context.update(get_store_open_context(business))
    
    return render(request, f'views/store_layouts/{layout}/store-blog.html', context)


# ═════════════════════════════════════════════════════════════════
# STORE BLOG MANAGEMENT APIS (DASHBOARD STORE SETTINGS)
# ═════════════════════════════════════════════════════════════════

@login_required
def store_blog_articles_api(request):
    """List paginated store blog articles for Store Settings management table"""
    user = misc.get_owner_from_user(request.user)
    if not models.user_has_any_premium_layout(user):
        return JsonResponse({'status': False, 'message': 'Store Blog is a premium feature. Please unlock a premium theme to access blog articles.', 'premium_required': True}, status=403)
    business = models.BusinessDetails.objects.filter(user=user).first()
    if not business:
        return JsonResponse({'status': False, 'message': 'Business not found'}, status=404)
        
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', '').strip()
    
    posts = models.StoreBlogPost.objects.filter(business=business)
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(summary__icontains=query) | Q(category__icontains=query))
    if category and category.lower() != 'all':
        posts = posts.filter(category__iexact=category)
    if status_filter:
        if status_filter == 'published':
            posts = posts.filter(is_published=True)
        elif status_filter == 'draft':
            posts = posts.filter(is_published=False)
            
    posts = posts.order_by('-created_at')
    
    # Categories list from StoreBlogCategory model
    existing_cats = set(models.StoreBlogCategory.objects.filter(business=business).values_list('name', flat=True))
    post_cats = set(models.StoreBlogPost.objects.filter(business=business).values_list('category', flat=True).distinct())
    from django.utils.text import slugify
    for pc in post_cats:
        if pc and pc not in existing_cats:
            models.StoreBlogCategory.objects.get_or_create(business=business, name=pc, defaults={'slug': slugify(pc)})
    if 'General' not in existing_cats:
        models.StoreBlogCategory.objects.get_or_create(business=business, name='General', defaults={'slug': 'general'})

    categories = list(
        models.StoreBlogCategory.objects.filter(business=business)
        .values_list('name', flat=True)
        .order_by('name')
    )
    
    from django.core.paginator import Paginator
    page_size = int(request.GET.get('page_size', 10))
    paginator = Paginator(posts, page_size)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    articles_data = []
    for p in page_obj:
        articles_data.append({
            'id': p.uniq_id,
            'title': p.title,
            'slug': p.slug,
            'category': p.category or 'General',
            'summary': p.summary or '',
            'author_name': p.author_name or business.store_name,
            'read_time': p.read_time,
            'image_url': p.get_image_url(),
            'is_published': p.is_published,
            'views_count': p.views_count,
            'created_at': p.created_at.strftime('%b %d, %Y'),
            'updated_at': p.updated_at.strftime('%b %d, %Y')
        })
        
    return JsonResponse({
        'status': True,
        'articles': articles_data,
        'categories': categories,
        'total_count': paginator.count,
        'page': page_obj.number,
        'num_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'start_index': page_obj.start_index() if paginator.count > 0 else 0,
        'end_index': page_obj.end_index() if paginator.count > 0 else 0,
    })


@login_required
def store_blog_article_create_api(request):
    """Create a new store blog article"""
    if request.method != 'POST':
        return JsonResponse({'status': False, 'message': 'Invalid request method'}, status=405)
        
    user = misc.get_owner_from_user(request.user)
    if not models.user_has_any_premium_layout(user):
        return JsonResponse({'status': False, 'message': 'Store Blog is a premium feature. Please unlock a premium theme to write blog articles.', 'premium_required': True}, status=403)
    business = models.BusinessDetails.objects.filter(user=user).first()
    if not business:
        return JsonResponse({'status': False, 'message': 'Business not found'}, status=404)
        
    title = request.POST.get('title', '').strip()
    if not title:
        return JsonResponse({'status': False, 'message': 'Title is required'}, status=400)
        
    from django.utils.text import slugify
    raw_slug = request.POST.get('slug', '').strip()
    base_slug = slugify(raw_slug) if raw_slug else slugify(title)
    if not base_slug:
        base_slug = 'article'
        
    final_slug = base_slug
    counter = 1
    while models.StoreBlogPost.objects.filter(business=business, slug=final_slug).exists():
        final_slug = f"{base_slug}-{counter}"
        counter += 1
        
    category = request.POST.get('category', 'General').strip() or 'General'
    summary = request.POST.get('summary', '').strip()
    content = request.POST.get('content', '').strip()
    author_name = request.POST.get('author_name', '').strip() or business.store_name
    read_time = request.POST.get('read_time', '5 min read').strip() or '5 min read'
    is_published = request.POST.get('is_published', 'true').lower() in ('true', '1', 'yes')
    
    post = models.StoreBlogPost.objects.create(
        business=business,
        title=title,
        slug=final_slug,
        category=category,
        summary=summary,
        content=content,
        author_name=author_name,
        read_time=read_time,
        is_published=is_published
    )
    
    if 'image' in request.FILES:
        post.image = request.FILES['image']
        post.save()
    elif request.POST.get('cover_image_url'):
        post.cover_image_url = request.POST.get('cover_image_url').strip()
        post.save()
        
    models.StoreBlogCategory.objects.get_or_create(business=business, name=category, defaults={'slug': slugify(category)})
    
    return JsonResponse({
        'status': True,
        'message': 'Article created successfully!',
        'article_id': post.uniq_id,
        'slug': post.slug
    })


@login_required
def store_blog_article_detail_api(request, post_id):
    """Retrieve, update, or delete a store blog article"""
    user = misc.get_owner_from_user(request.user)
    if not models.user_has_any_premium_layout(user):
        return JsonResponse({'status': False, 'message': 'Store Blog is a premium feature. Please unlock a premium theme to manage blog articles.', 'premium_required': True}, status=403)
    business = models.BusinessDetails.objects.filter(user=user).first()
    if not business:
        return JsonResponse({'status': False, 'message': 'Business not found'}, status=404)
        
    post = models.StoreBlogPost.objects.filter(business=business, uniq_id=post_id).first()
    if not post:
        return JsonResponse({'status': False, 'message': 'Article not found'}, status=404)
        
    if request.method == 'GET':
        return JsonResponse({
            'status': True,
            'article': {
                'id': post.uniq_id,
                'title': post.title,
                'slug': post.slug,
                'category': post.category,
                'summary': post.summary or '',
                'content': post.content or '',
                'author_name': post.author_name or '',
                'read_time': post.read_time,
                'image_url': post.get_image_url(),
                'is_published': post.is_published,
                'views_count': post.views_count,
                'created_at': post.created_at.strftime('%b %d, %Y'),
            }
        })
        
    elif request.method == 'POST':
        from django.utils.text import slugify
        title = request.POST.get('title', '').strip()
        if title:
            post.title = title
            
        raw_slug = request.POST.get('slug', '').strip()
        if raw_slug and raw_slug != post.slug:
            base_slug = slugify(raw_slug) or 'article'
            final_slug = base_slug
            counter = 1
            while models.StoreBlogPost.objects.filter(business=business, slug=final_slug).exclude(uniq_id=post.uniq_id).exists():
                final_slug = f"{base_slug}-{counter}"
                counter += 1
            post.slug = final_slug
            
        if 'category' in request.POST:
            cat = request.POST.get('category', '').strip() or 'General'
            post.category = cat
            models.StoreBlogCategory.objects.get_or_create(business=business, name=cat, defaults={'slug': slugify(cat)})
            
        if 'summary' in request.POST:
            post.summary = request.POST.get('summary', '').strip()
            
        if 'content' in request.POST:
            post.content = request.POST.get('content', '').strip()
            
        if 'author_name' in request.POST:
            post.author_name = request.POST.get('author_name', '').strip()
            
        if 'read_time' in request.POST:
            post.read_time = request.POST.get('read_time', '').strip()
            
        if 'is_published' in request.POST:
            post.is_published = request.POST.get('is_published', 'true').lower() in ('true', '1', 'yes')
            
        if 'image' in request.FILES:
            post.image = request.FILES['image']
        elif request.POST.get('remove_image') == 'true':
            post.image = None
            post.cover_image_url = None
            
        post.save()
        return JsonResponse({'status': True, 'message': 'Article updated successfully!', 'article_id': post.uniq_id})
        
    elif request.method == 'DELETE':
        post.delete()
        return JsonResponse({'status': True, 'message': 'Article deleted successfully!'})
        
    return JsonResponse({'status': False, 'message': 'Method not allowed'}, status=405)


@login_required
def store_blog_categories_api(request):
    """List or create blog categories for this merchant's store"""
    user = misc.get_owner_from_user(request.user)
    if not models.user_has_any_premium_layout(user):
        return JsonResponse({'status': False, 'message': 'Store Blog is a premium feature. Please unlock a premium theme to manage blog categories.', 'premium_required': True}, status=403)
    business = models.BusinessDetails.objects.filter(user=user).first()
    if not business:
        return JsonResponse({'status': False, 'categories': [], 'categories_data': []})
        
    from django.utils.text import slugify

    # Handle POST: Create new category
    if request.method == 'POST':
        name = request.POST.get('name') or ''
        if not name and request.body:
            try:
                import json
                body_data = json.loads(request.body)
                name = body_data.get('name', '')
            except Exception:
                pass
        name = name.strip()
        if not name:
            return JsonResponse({'status': False, 'message': 'Category name cannot be empty.'}, status=400)
        if len(name) > 100:
            return JsonResponse({'status': False, 'message': 'Category name is too long (maximum 100 characters).'}, status=400)
            
        cat, created = models.StoreBlogCategory.objects.get_or_create(
            business=business,
            name=name,
            defaults={'slug': slugify(name)}
        )
        count = models.StoreBlogPost.objects.filter(business=business, category=cat.name).count()
        return JsonResponse({
            'status': True,
            'message': f'Category "{cat.name}" added successfully!' if created else f'Category "{cat.name}" already exists.',
            'created': created,
            'category': {
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug,
                'count': count
            }
        })

    # Handle DELETE: Can also delete via query param or body
    elif request.method == 'DELETE':
        cat_id = request.GET.get('id') or request.POST.get('id')
        if not cat_id and request.body:
            try:
                import json
                body_data = json.loads(request.body)
                cat_id = body_data.get('id')
            except Exception:
                pass
        if not cat_id:
            return JsonResponse({'status': False, 'message': 'Category ID is required for deletion.'}, status=400)
            
        cat = models.StoreBlogCategory.objects.filter(business=business, id=cat_id).first()
        if not cat:
            return JsonResponse({'status': False, 'message': 'Category not found.'}, status=404)
            
        cat_name = cat.name
        models.StoreBlogPost.objects.filter(business=business, category=cat_name).update(category='General')
        models.StoreBlogCategory.objects.get_or_create(business=business, name='General', defaults={'slug': 'general'})
        cat.delete()
        return JsonResponse({
            'status': True,
            'message': f'Category "{cat_name}" deleted successfully! Any articles were moved to General.'
        })

    # Handle GET: List all categories
    existing_cats = set(models.StoreBlogCategory.objects.filter(business=business).values_list('name', flat=True))
    post_cats = set(models.StoreBlogPost.objects.filter(business=business).values_list('category', flat=True).distinct())
    for pc in post_cats:
        if pc and pc not in existing_cats:
            models.StoreBlogCategory.objects.get_or_create(business=business, name=pc, defaults={'slug': slugify(pc)})
            
    if 'General' not in existing_cats:
        models.StoreBlogCategory.objects.get_or_create(business=business, name='General', defaults={'slug': 'general'})

    categories_qs = models.StoreBlogCategory.objects.filter(business=business).order_by('name')
    categories_data = []
    for cat in categories_qs:
        count = models.StoreBlogPost.objects.filter(business=business, category=cat.name).count()
        categories_data.append({
            'id': cat.id,
            'name': cat.name,
            'slug': cat.slug,
            'count': count
        })
        
    category_names = [c['name'] for c in categories_data]
    return JsonResponse({
        'status': True,
        'categories': category_names,
        'categories_data': categories_data
    })


@login_required
def store_blog_category_detail_api(request, category_id):
    """Delete or manage a specific store blog category"""
    user = misc.get_owner_from_user(request.user)
    if not models.user_has_any_premium_layout(user):
        return JsonResponse({'status': False, 'message': 'Store Blog is a premium feature. Please unlock a premium theme to manage blog categories.', 'premium_required': True}, status=403)
    business = models.BusinessDetails.objects.filter(user=user).first()
    if not business:
        return JsonResponse({'status': False, 'message': 'Business not found'}, status=404)
        
    cat = models.StoreBlogCategory.objects.filter(business=business, id=category_id).first()
    if not cat:
        return JsonResponse({'status': False, 'message': 'Category not found'}, status=404)
        
    if request.method in ('DELETE', 'POST'):
        cat_name = cat.name
        models.StoreBlogPost.objects.filter(business=business, category=cat_name).update(category='General')
        from django.utils.text import slugify
        models.StoreBlogCategory.objects.get_or_create(
            business=business, name='General', defaults={'slug': 'general'}
        )
        cat.delete()
        return JsonResponse({
            'status': True,
            'message': f'Category "{cat_name}" deleted successfully! Any articles were moved to General.'
        })
        
    return JsonResponse({'status': False, 'message': 'Method not allowed'}, status=405)


@login_required
def store_blog_editor_view(request, post_id=None):
    """Dedicated dashboard page for creating or editing a store blog article"""
    user = misc.get_owner_from_user(request.user)
    if not models.user_has_any_premium_layout(user):
        return redirect('/store-layouts#premium')
    business = models.BusinessDetails.objects.filter(user=user).first()
    if not business:
        return redirect('/store-settings')
        
    post = None
    if post_id:
        post = models.StoreBlogPost.objects.filter(business=business, uniq_id=post_id).first()
        if not post:
            return redirect('/store-settings#blog')
            
    from django.utils.text import slugify
    # Sync categories from existing posts
    existing_cats = set(models.StoreBlogCategory.objects.filter(business=business).values_list('name', flat=True))
    post_cats = set(models.StoreBlogPost.objects.filter(business=business).values_list('category', flat=True).distinct())
    for pc in post_cats:
        if pc and pc not in existing_cats:
            models.StoreBlogCategory.objects.get_or_create(business=business, name=pc, defaults={'slug': slugify(pc)})
            
    if 'General' not in existing_cats:
        models.StoreBlogCategory.objects.get_or_create(business=business, name='General', defaults={'slug': 'general'})

    categories_qs = models.StoreBlogCategory.objects.filter(business=business).order_by('name')
    categories = list(categories_qs.values_list('name', flat=True))
    categories_data = [
        {'id': c.id, 'name': c.name, 'slug': c.slug, 'count': models.StoreBlogPost.objects.filter(business=business, category=c.name).count()}
        for c in categories_qs
    ]
        
    context = {
        'business': business,
        'post': post,
        'post_id': post.uniq_id if post else '',
        'is_edit': bool(post),
        'categories': categories,
        'categories_data': categories_data,
    }
    return render(request, 'views/dashboard/store-blog-editor.html', context)


@login_required
def store_blog_articles_list_view(request):
    """Dedicated dashboard page for managing all store blog articles with search & pagination"""
    user = misc.get_owner_from_user(request.user)
    if not models.user_has_any_premium_layout(user):
        return redirect('/store-layouts#premium')
    business = models.BusinessDetails.objects.filter(user=user).first()
    if not business:
        return redirect('/store-settings')
        
    categories_qs = models.StoreBlogCategory.objects.filter(business=business).order_by('name')
    categories = list(categories_qs.values_list('name', flat=True))
    categories_data = [
        {'id': c.id, 'name': c.name, 'slug': c.slug, 'count': models.StoreBlogPost.objects.filter(business=business, category=c.name).count()}
        for c in categories_qs
    ]
    
    total_articles = models.StoreBlogPost.objects.filter(business=business).count()
    published_count = models.StoreBlogPost.objects.filter(business=business, is_published=True).count()
    draft_count = models.StoreBlogPost.objects.filter(business=business, is_published=False).count()
    
    context = {
        'business': business,
        'categories': categories,
        'categories_data': categories_data,
        'total_articles': total_articles,
        'published_count': published_count,
        'draft_count': draft_count,
        'has_purchased_premium_layout': True,
    }
    return render(request, 'views/dashboard/store-blog-articles.html', context)


@login_required
def domain_management_view(request):
    """Dashboard page for managing and connecting custom domains with business context"""
    user = misc.get_owner_from_user(request.user)
    business = models.BusinessDetails.objects.filter(user=user, store_setup=True).first() or models.BusinessDetails.objects.filter(user=user).first()
    return render(request, 'views/dashboard/domain-management.html', {'business': business})



from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
@xframe_options_exempt
@never_cache
def store_preview_view(request, slug):
    """Public/Preview view for a store by its slug"""
    if not getattr(request, 'store_slug', None):
        raise Http404("Page not found")
        
    business = models.BusinessDetails.objects.filter(store_slug=slug).first()
    
    preview_layout = request.GET.get('preview_layout') or request.GET.get('layout')
    
    layout = preview_layout if preview_layout else (business.store_layout_template if business else 'grid')
    
    
    
    if not business or not business.is_published:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {'business': business}, status=404)
    
    # Increment store views
    models.BusinessDetails.objects.filter(id=business.id).update(store_views=F('store_views') + 1)
    business.refresh_from_db()
    
    user = business.user
    items_qs = models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)
    
    # Category filter from query string
    raw_category = request.GET.get('category', '').strip()
    active_tab = 'featured'
    category = ''
    if raw_category.lower() in ['all', 'featured', 'featured-products', '']:
        active_tab = 'featured'
        category = ''
    elif raw_category.lower() in ['new-arrivals', 'new_arrivals']:
        active_tab = 'new-arrivals'
        category = ''
    elif raw_category.lower() in ['most-viewed', 'most_viewed']:
        active_tab = 'most-viewed'
        category = ''
    else:
        category = raw_category

    if category:
        items_qs = items_qs.filter(item_category__iexact=category)

    search_q = request.GET.get('search', '').strip()
    if search_q:
        items_qs = items_qs.filter(
            Q(item_name__icontains=search_q) |
            Q(item_category__icontains=search_q) |
            Q(item_description__icontains=search_q) |
            Q(book_author__icontains=search_q)
        )
    
    # Pagination
    page_number = request.GET.get('page', 1)
    per_page = 10 if layout in ['premium-commerce-editorial', 'folio-press'] else 12
    paginator = Paginator(items_qs, per_page)
    page_obj = paginator.get_page(page_number)
    
    promo_context = get_promo_context(business)
    open_context = get_store_open_context(business)
    
    # Enrich items with images for standard pagination
    for item in page_obj:
        enrich_item_promo(item, business, promo_context)
    
    # Get all categories for the sidebar (unfiltered)
    all_items = models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)
    
    # Category grouped layout logic
    grouped_items = {}
    grouped_items_new_arrivals = {}
    grouped_items_most_viewed = {}
    layout_style = getattr(business, 'store_category_layout', 'standard')
    if layout_style == 'categorized':
        if category:
            matched_cat = all_items.filter(item_category__iexact=category).values_list('item_category', flat=True).first()
            categories_list = [matched_cat or category]
        else:
            categories_list = list(all_items.values_list('item_category', flat=True).distinct())

        for cat in categories_list:
            if not cat:
                cat_name = 'Uncategorized'
                cat_filter = Q(item_category__isnull=True) | Q(item_category='')
            else:
                cat_name = cat
                cat_filter = Q(item_category__iexact=cat)
            
            limit = 50 if category else 10

            # Featured products
            featured_items_cat = list(all_items.filter(cat_filter).order_by('-is_featured', '-id')[:limit])
            for it in featured_items_cat:
                enrich_item_promo(it, business, promo_context)
            if featured_items_cat:
                grouped_items[cat_name] = featured_items_cat

            # New arrivals
            new_items_cat = list(all_items.filter(cat_filter).order_by('-timestamp', '-id')[:limit])
            for it in new_items_cat:
                enrich_item_promo(it, business, promo_context)
            if new_items_cat:
                grouped_items_new_arrivals[cat_name] = new_items_cat

            # Most viewed
            viewed_items_cat = list(all_items.filter(cat_filter).order_by('-id')[:limit])
            for it in viewed_items_cat:
                enrich_item_promo(it, business, promo_context)
            if viewed_items_cat:
                grouped_items_most_viewed[cat_name] = viewed_items_cat

    # Pre-enriched tab collections for standard grid mode
    featured_tab_items = list(all_items.order_by('-is_featured', '-id')[:16])
    for it in featured_tab_items:
        enrich_item_promo(it, business, promo_context)

    new_arrivals_tab_items = list(all_items.order_by('-timestamp', '-id')[:16])
    for it in new_arrivals_tab_items:
        enrich_item_promo(it, business, promo_context)

    most_viewed_tab_items = list(all_items.order_by('-id')[:16])
    for it in most_viewed_tab_items:
        enrich_item_promo(it, business, promo_context)

    hot_items_qs = models.UserItems.objects.filter(user=user, in_store=True, is_featured=True).order_by('?')[:4]
    hot_items = list(hot_items_qs)
    for hot_item in hot_items:
        enrich_item_promo(hot_item, business, promo_context)

    # Filter products specifically on promo for "Deal of the day" and promotional sections
    promo_items_qs = models.UserItems.objects.filter(user=user, in_store=True, is_promo=True).order_by('-id')
    promo_items = [enrich_item_promo(it, business, promo_context) for it in promo_items_qs]
    
    preview_layout = request.GET.get('preview_layout') or request.GET.get('layout')
    
    # Query published StoreBlogPost records for storefront home preview
    blog_articles = list(
        models.StoreBlogPost.objects.filter(business=business, is_published=True).order_by('-created_at')[:3]
    )
    
    try:
        store_reviews = list(models.ProductReview.objects.filter(item__user=user, is_approved=True).order_by('-created_at')[:5])
    except Exception:
        store_reviews = []

    context = {
        'business': business,
        'items': page_obj,
        'all_items': all_items,
        'promo_items': promo_items,
        'grouped_items': grouped_items,
        'grouped_items_new_arrivals': grouped_items_new_arrivals,
        'grouped_items_most_viewed': grouped_items_most_viewed,
        'featured_tab_items': featured_tab_items,
        'new_arrivals_tab_items': new_arrivals_tab_items,
        'most_viewed_tab_items': most_viewed_tab_items,
        'hot_items': hot_items,
        'blog_articles': blog_articles,
        'store_reviews': store_reviews,
        'layout': preview_layout or business.store_layout_template or 'grid',
        'category_layout': layout_style,
        'page_obj': page_obj,
        'paginator': paginator,
        'current_category': category or 'all',
        'is_category_page': bool(category),
        'active_tab': active_tab,
    }
    customization = models.StoreLayoutCustomization.objects.filter(business=business, layout_id=layout).first()
    context['layout_customization'] = customization
    if customization and customization.sections_config:
        context['sections_config'] = customization.sections_config

    if request.method == 'POST':
        draft_config_json = request.POST.get('sections_config')
        if draft_config_json:
            try:
                import json
                context['sections_config'] = json.loads(draft_config_json)
            except:
                pass

    if not context.get('sections_config'):
        if customization and customization.sections_config:
            context['sections_config'] = customization.sections_config
        else:
            context['sections_config'] = get_default_layout_sections(layout, business=business)

    # Filter out popular authors from layout sections
    if context.get('sections_config'):
        context['sections_config'] = [
            sec for sec in context['sections_config']
            if isinstance(sec, dict) and sec.get('type') != 'authors'
        ]

    # Ensure hero section displays business store details if preset defaults are still present
    for sec in context.get('sections_config', []):
        if isinstance(sec, dict) and sec.get('type') == 'hero':
            s_settings = sec.setdefault('settings', {})
            if s_settings.get('headline') in ('ATELIER VANGUARD SPATIAL LAB', 'HAUTE HORIZONS & TIMELESS PRESTIGE', 'METRO PULSE STORE', '', None):
                s_settings['headline'] = business.store_name if (business and business.store_name) else ''
            if s_settings.get('tagline') in (
                'Form follows future. Monolithic artifacts, precision industrial crafts, and brutalist lifestyle apparatus.',
                'Bespoke fine objects and opulent living designed for the modern connoisseur of world-class luxury.',
                '',
                None
            ):
                s_settings['tagline'] = business.store_description if (business and business.store_description) else ''
            if business and business.store_banner and not s_settings.get('cover_image'):
                try:
                    s_settings['cover_image'] = business.store_banner.url
                except Exception:
                    pass

    # Best Sellers & Author Spotlight Filtering (especially for Commerce Editorial layout)
    # Determine the selected author (from section settings or store featured author or author directory)
    selected_author = (business.store_featured_author or '').strip()
    if not selected_author and business.store_authors and isinstance(business.store_authors, list) and len(business.store_authors) > 0:
        first_a = business.store_authors[0]
        if isinstance(first_a, dict) and first_a.get('name'):
            selected_author = str(first_a['name']).strip()
        elif isinstance(first_a, str):
            selected_author = first_a.strip()

    for sec in context.get('sections_config', []):
        if isinstance(sec, dict) and sec.get('type') in ('hot_products', 'brand_story'):
            sec_author = (sec.get('settings', {}).get('author_name') or sec.get('settings', {}).get('selected_author') or '').strip()
            if sec_author:
                selected_author = sec_author
                break

    # Resolve author image from store_authors if store_featured_author_image is blank
    selected_author_image = (business.store_featured_author_image or '').strip()
    if not selected_author_image and business.store_authors and isinstance(business.store_authors, list):
        for a in business.store_authors:
            if isinstance(a, dict) and a.get('name') and str(a['name']).strip().lower() == selected_author.lower():
                selected_author_image = (a.get('image') or '').strip()
                break

    author_items = []
    if selected_author:
        author_items_qs = models.UserItems.objects.filter(
            user=user,
            in_store=True
        ).filter(
            Q(book_author__iexact=selected_author) | Q(book_author__icontains=selected_author)
        ).order_by('-is_featured', '-id')
        author_items = list(author_items_qs)
        for it in author_items:
            enrich_item_promo(it, business, promo_context)

    context['author_items'] = author_items
    context['selected_author'] = selected_author
    context['selected_author_image'] = selected_author_image

    if layout == 'premium-commerce-editorial':
        # On commerce editorial layout, only show products associated with the author selected
        context['hot_items'] = author_items

    # Attach all store items for the hero carousel element
    hero_carousel_items = list(models.UserItems.objects.filter(user=user, in_store=True).order_by('-id'))
    for it in hero_carousel_items:
        enrich_item_promo(it, business, promo_context)
    context['hero_carousel_items'] = hero_carousel_items

    # Compute max promo discount percentage across store and promo items (fallback to 20)
    max_promo_percentage = 0
    promo_active = promo_context.get('promo_active', False)
    promo_pct = promo_context.get('promo_percentage')

    promo_item_discounts = [
        int(it.discount_percentage)
        for it in promo_items
        if getattr(it, 'discount_percentage', None) and int(it.discount_percentage) > 0
    ]

    candidates = []
    if promo_active and promo_pct:
        try:
            p_val = int(promo_pct)
            if p_val > 0:
                candidates.append(p_val)
        except (ValueError, TypeError):
            pass

    if promo_item_discounts:
        candidates.extend(promo_item_discounts)

    # Check all promo items in store to ensure no discount is missed
    for it in models.UserItems.objects.filter(user=user, in_store=True, is_promo=True):
        p_val = getattr(it, 'promo_amount', None)
        if p_val is not None:
            try:
                val = float(p_val)
                if 0 < val <= 100:
                    candidates.append(round(val))
            except (ValueError, TypeError):
                pass

    if candidates:
        max_promo_percentage = max(candidates)
    else:
        max_promo_percentage = 20

    context['max_promo_percentage'] = max_promo_percentage
    highest_discount = max_promo_percentage
    banner_deal_headline = f"Deal of the day up to {highest_discount}% off Special offer"
    context['banner_deal_headline'] = banner_deal_headline

    # Set Deal of the Day headline dynamically
    for sec in context.get('sections_config', []):
        if isinstance(sec, dict):
            s_settings = sec.setdefault('settings', {})
            if sec.get('type') == 'promo_banner' or sec.get('id') == 'deal_of_day':
                curr_headline = s_settings.get('headline')
                if not curr_headline or curr_headline in ('Deal of the Day', 'MEGA PROMO: 50% OFF TODAY!') or curr_headline.startswith('Deal of the day'):
                    s_settings['headline'] = banner_deal_headline

    import json
    context['sections_config_json'] = json.dumps(context['sections_config'])

    sections_by_id = {}
    sections_by_type = {}
    for sec in context.get('sections_config', []):
        if isinstance(sec, dict):
            s_id = sec.get('id')
            s_type = sec.get('type')
            if s_id:
                sections_by_id[s_id] = sec
            if s_type:
                sections_by_type[s_type] = sec
    context['sections_by_id'] = sections_by_id
    context['sections_by_type'] = sections_by_type

    # Attach Instagram Social Gallery
    try:
        from api.services.instagram_service import get_instagram_service
        instagram_service = get_instagram_service()
        context['instagram_gallery'] = instagram_service.get_gallery_for_business(business, blocking=False)
    except Exception as e:
        context['instagram_gallery'] = {'configured': False, 'profile': None, 'posts': []}

    context.update(promo_context)
    context.update(open_context)
    
    response = render(request, f'views/store_layouts/{layout}/store-preview.html', context)
    return response

@xframe_options_exempt
@never_cache
def store_item_preview_view(request, slug, item_id):
    """Public/Preview view for a specific store item"""
    if not getattr(request, 'store_slug', None):
        request.store_slug = slug
        
    business = models.BusinessDetails.objects.filter(store_slug=slug).first()
    
    preview_layout = request.GET.get('preview_layout') or request.GET.get('layout')
    
    layout = preview_layout if preview_layout else (business.store_layout_template if business else 'grid')
    
    
    
    if not business or not business.is_published:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {'business': business}, status=404)
        
    user = business.user
    item_lookup = Q(item_id=item_id)
    if str(item_id).isdigit():
        item_lookup |= Q(id=int(item_id))
    try:
        item = models.UserItems.objects.filter(user=user, in_store=True).filter(item_lookup).first()
    except Exception:
        item = None
    
    if not item:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {'business': business, 'item_not_found': True}, status=404)
        
    images = item.images.all()
    
    # Fetch reviews
    reviews = item.reviews.filter(is_approved=True)
    reviews_count = reviews.count()
    average_rating = sum(r.rating for r in reviews) / reviews_count if reviews_count > 0 else 0
    average_rating_display = round(average_rating, 1)
    
    promo_context = get_promo_context(business)
    enrich_item_promo(item, business, promo_context)
    
    # Fetch similar items based on category, excluding the current item
    if item.item_category:
        similar_items = models.UserItems.objects.filter(
            user=user, in_store=True, is_featured=True, item_category=item.item_category
        ).exclude(item_id=item_id).order_by('?')[:4]
    else:
        similar_items = models.UserItems.objects.none()
        
    # If not enough similar items, fallback to random items
    similar_items = list(similar_items)
    if len(similar_items) < 4:
        existing_ids = [s.item_id for s in similar_items]
        existing_ids.append(item_id)
        additional_items = models.UserItems.objects.filter(
            user=user, in_store=True, is_featured=True
        ).exclude(item_id__in=existing_ids).order_by('?')[:4 - len(similar_items)]
        similar_items = similar_items + list(additional_items)
    
    # Enrich similar items with images
    for sim_item in similar_items:
        enrich_item_promo(sim_item, business, promo_context)
    
    preview_layout = request.GET.get('preview_layout') or request.GET.get('layout')
    all_items = models.UserItems.objects.filter(user=user, in_store=True, is_featured=True)
    context = {
        'business': business,
        'item': item,
        'images': images,
        'similar_items': similar_items,
        'reviews': reviews,
        'reviews_count': reviews_count,
        'average_rating': average_rating,
        'average_rating_display': average_rating_display,
        'all_items': all_items,
        'layout': preview_layout or business.store_layout_template or 'grid',
    }
    context.update(promo_context)
    
    open_context = get_store_open_context(business)
    context.update(open_context)
    
    return render(request, f'views/store_layouts/{layout}/store-item-preview.html', context)

@xframe_options_exempt
def store_checkout_view(request, slug):
    """Public checkout view for a store"""
    import json
    if not getattr(request, 'store_slug', None):
        raise Http404("Page not found")
        
    business = models.BusinessDetails.objects.filter(store_slug=slug).first()
    
    preview_layout = request.GET.get('preview_layout') or request.GET.get('layout')
    
    layout = preview_layout if preview_layout else (business.store_layout_template if business else 'grid')
    
    
    
    if not business or not business.is_published:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {'business': business}, status=404)
        
    allowed_countries = models.AllowedCountries.objects.filter(is_active=True)
    if business.store_countries:
        try:
            store_countries_list = business.store_countries
            if isinstance(store_countries_list, str):
                import json
                store_countries_list = json.loads(store_countries_list)
            if isinstance(store_countries_list, list) and store_countries_list:
                allowed_countries = allowed_countries.filter(code__in=store_countries_list)
        except Exception:
            pass
    
    import os
    currency = 'NGN'
    user_details = business.user.details.first() if business.user else None
    merchant_country = 'NG'
    if user_details:
        currency = user_details.currency
        merchant_country = user_details.user_country
        
    country_config = models.AllowedCountries.objects.filter(code=merchant_country).first()
    system_pod_enabled = country_config.system_delivery_pod_enabled if country_config else False
    system_card_enabled = country_config.system_delivery_card_enabled if country_config else True
    system_arc_enabled = country_config.system_arc_enabled if country_config else True
    all_items = models.UserItems.objects.filter(user=business.user, in_store=True, is_featured=True) if business.user else []
    digital_items = models.UserItems.objects.filter(user=business.user, is_digital=True) if business.user else []
    digital_item_ids = [str(item.item_id) for item in digital_items]
        
    context = {
        'business': business,
        'allowed_countries': allowed_countries,
        'store_currency': currency,
        'system_pod_enabled': system_pod_enabled,
        'system_card_enabled': system_card_enabled,
        'system_arc_enabled': system_arc_enabled,
        'layout': layout,
        'all_items': all_items,
        'digital_item_ids': digital_item_ids,
        'digital_item_ids_json': json.dumps(digital_item_ids),
        'is_checkout': True,
    }
    
    if currency == 'NGN':
        context['paystack_public_key'] = os.environ.get('PAYSTACK_PUBLIC_KEY', '')
        
    context.update(get_promo_context(business))
    
    open_context = get_store_open_context(business)
    context.update(open_context)
    
    return render(request, f'views/store_layouts/{layout}/store-checkout.html', context)

class CheckStoreSlugView(APIView):
    """Check if a store slug is available"""
    authentication_classes = [JWTAuthentication]
    
    def post(self, request):
        slug = request.data.get('slug', '').strip().lower()
        if not slug:
            return Response({'status': False, 'message': 'Slug is required'}, status=status.HTTP_400_BAD_REQUEST)
        from django.conf import settings
        reserved = getattr(settings, 'RESERVED_SUBDOMAINS', set())
        if slug in reserved:
            return Response({
                'status': True,
                'available': False,
                'message': 'Slug is reserved and cannot be used'
            })
        
        # Check if any other business is using this slug
        # Exclude the current user's business if they already have one
        exists = BusinessDetails.objects.filter(store_slug=slug).exclude(user=request.user).exists()
        
        return Response({
            'status': True,
            'available': not exists,
            'message': 'Slug is available' if not exists else 'Slug is already taken'
        })

class StaffActivityView(APIView):
    def get(self, request, staff_id):
        try:
            from django.db.models import Q, Sum
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            staff = get_object_or_404(models.UserSecure, business_owner=user, uniq_id=staff_id)
            
            # Logins
            logins_qs = models.StaffPosLogins.objects.filter(staff=staff).order_by('-login_time')[:10]
            logins_data = []
            for lg in logins_qs:
                logins_data.append({
                    'id': lg.id,
                    'terminal_id': lg.terminal_id,
                    'login_time': lg.login_time.isoformat() if lg.login_time else None,
                    'logout_time': lg.logout_time.isoformat() if lg.logout_time else None,
                    'ip_address': lg.ip_address,
                    'status': lg.status
                })
                
            # Transactions
            payroll = staff.payroll_profile.first()
            account_number = payroll.account_number if payroll else None
            
            if account_number:
                trxs_qs = models.UserTransactions.objects.filter(
                    user=user
                ).filter(
                    Q(destination_id=account_number) | Q(user_collection_id=account_number)
                ).order_by('-id')
            else:
                trxs_qs = models.UserTransactions.objects.none()
                
            trxs_data = []
            for t in trxs_qs[:10]:
                trxs_data.append({
                    'id': t.id,
                    'trx_id': str(t.trx_id),
                    'trx_status': t.trx_status,
                    'trx_amount': t.trx_amount,
                    'trx_currency': t.trx_currency,
                    'trx_type': t.trx_type,
                    'description': t.description
                })
                
            # Performance stats
            total_trx = trxs_qs.count()
            total_revenue = trxs_qs.filter(trx_type='credit', trx_status='completed').aggregate(Sum('trx_amount'))['trx_amount__sum'] or 0.0
            
            # Permissions
            details = staff.details.first()
            permissions = {
                'pos_access': details.pos_access if details else False,
                'can_apply_discounts': details.can_apply_discounts if details else False,
                'can_process_refunds': details.can_process_refunds if details else False,
                'can_view_reports': details.can_view_reports if details else False
            }
            
            return Response({
                'status': True,
                'data': {
                    'logins': logins_data,
                    'transactions': trxs_data,
                    'invoices': [],
                    'performance': {
                        'total_transactions': total_trx,
                        'total_revenue': total_revenue
                    },
                    'permissions': permissions
                }
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@never_cache
def public_product_info_view(request, item_id):
    """Dedicated public page showing product details, price, name, QR code, and Add to Cart option"""
    from django.shortcuts import render, get_object_or_404
    from django.conf import settings
    import qrcode
    import io
    import base64
    from api import models

    # Retrieve the item by UUID/item_id
    item = get_object_or_404(models.UserItems, item_id=item_id)
    
    # Retrieve the business/store details associated with this item's user
    business = models.BusinessDetails.objects.filter(user=item.user).first()
    
    # Determine currency symbol based on owner's settings
    user_details = models.UserDetails.objects.filter(user=item.user).first()
    currency_code = user_details.currency if user_details else 'NGN'
    
    from api.templatetags.currency_tags import currency_symbol as get_currency_symbol
    currency_symbol = get_currency_symbol(currency_code)

    # Build the full URL of the current page to generate its QR code
    scheme = 'https' if request.is_secure() else 'http'
    current_url = f"{scheme}://{request.get_host()}/product/{item_id}/info/"

    # Generate QR Code representing this URL
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(current_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, kind="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    # Get all images
    images = item.images.all()
    first_image = images[0].image.url if images.exists() else None
    all_images = [img.image.url for img in images]

    # Calculate online store URL
    online_store_url = None
    if business and business.store_setup:
        if business.store_custom_domain:
            # Assume HTTPS for custom domains
            online_store_url = f"https://{business.store_custom_domain}"
        else:
            store_subdomain = business.store_slug
            if store_subdomain:
                # Use STORE_BASE_DOMAIN from settings (e.g. localhost:8000 or flezpay.com)
                base_domain = getattr(settings, 'STORE_BASE_DOMAIN', 'localhost:8000')
                online_store_url = f"{scheme}://{store_subdomain}.{base_domain}"

    promo_context = get_promo_context(business) if business else {'promo_active': False}
    if promo_context.get('promo_active'):
        item.discount_percentage = promo_context['promo_percentage']
        item.discounted_price = float(item.item_amount) * (100 - promo_context['promo_percentage']) / 100.0

    context = {
        'item': item,
        'business': business,
        'currency_symbol': currency_symbol,
        'currency_code': currency_code,
        'qr_base64': qr_base64,
        'first_image': first_image,
        'all_images': all_images,
        'online_store_url': online_store_url,
        'current_url': current_url
    }
    if business:
        context.update(promo_context)
    return render(request, 'views/public/product-info.html', context)


def review_submission_view(request, token_id):
    """View for a customer to submit a product review via a unique link."""
    from api.models import ReviewToken, BusinessDetails
    layout = 'grid'  # safe default before business is resolved
    try:
        import uuid
        if isinstance(token_id, str):
            token_id = uuid.UUID(token_id)
            
        token = ReviewToken.objects.filter(id=token_id).first()
        if not token:
            return render(request, f'views/store_layouts/{layout}/store-not-found.html', {'item_not_found': True}, status=404)
            
        business = BusinessDetails.objects.filter(user=token.item.user).first()
        layout = business.store_layout_template if (business and business.store_layout_template) else 'grid'
        
        if token.is_used:
            # Token already used
            return render(request, f'views/store_layouts/{layout}/store-review.html', {
                'token': token,
                'already_used': True,
                'business': business,
                'layout': layout,
            })
            
        context = {
            'token': token,
            'business': business,
            'item': token.item,
            'already_used': False,
            'layout': layout,
        }
        return render(request, f'views/store_layouts/{layout}/store-review.html', context)
    except Exception as e:
        return render(request, f'views/store_layouts/{layout}/store-not-found.html', {'item_not_found': True}, status=404)



class CountryNamesProxyView(APIView):
    """
    GET /api/proxy/country-names?codes=ng,us
    Server-side proxy for the restcountries.com API so that the browser is
    not blocked by CORS.  Returns [{cca2, name: {common}}] matching the shape
    the front-end already expects.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        codes_param = request.query_params.get('codes', '').strip()
        if not codes_param:
            return Response({'error': 'codes parameter required'}, status=status.HTTP_400_BAD_REQUEST)

        # Sanitise: only allow letters and commas
        if not _re.fullmatch(r'[a-zA-Z,]+', codes_param):
            return Response({'error': 'invalid codes'}, status=status.HTTP_400_BAD_REQUEST)

        # Normalise to lowercase for the upstream call
        joined = ','.join(c.strip().lower() for c in codes_param.split(',') if c.strip())
        url = f'https://restcountries.com/v3.1/alpha?codes={joined}&fields=cca2,name'

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'FlezPay/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return Response({'error': f'upstream {e.code}'}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception:
            return Response({'error': 'upstream unavailable'}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(data)


@never_cache
def product_stock_view(request, item_id):
    """
    Public JSON endpoint returning real-time variant quantities and item stock for a product.
    Used by store_variant_modal.html to ensure live, accurate stock count even with cached DOM.
    """
    try:
        real_id = str(item_id).split('_')[0]
        try:
            uuid_obj = uuid.UUID(real_id)
            item_obj = models.UserItems.objects.filter(item_id=uuid_obj).first()
        except (ValueError, TypeError, AttributeError):
            item_obj = models.UserItems.objects.filter(item_id=real_id).first()

        if not item_obj:
            return JsonResponse({'status': False, 'message': 'Product not found'}, status=404)

        variants_data = []
        for v in item_obj.variants.all():
            opt_name = v.size if (v.variant_name == 'custom' or (not v.color_hex and not v.color_name)) else (v.color_name or v.size or '')
            variants_data.append({
                'id': v.id,
                'name': opt_name,
                'hex': '' if v.variant_name == 'custom' else (v.color_hex or ''),
                'color_name': v.color_name or '',
                'size': v.size or '',
                'variant_name': v.variant_name or ('color' if v.color_hex else 'custom'),
                'quantity': v.quantity,
                'price': float(v.price) if v.price is not None else None,
                'discounted_price': float(v.discounted_price) if v.discounted_price is not None else None
            })

        return JsonResponse({
            'status': True,
            'item_id': str(item_obj.item_id),
            'item_quantity': item_obj.item_quantity or 0,
            'variants': variants_data
        })
    except Exception as e:
        return JsonResponse({'status': False, 'message': str(e)}, status=500)


class StoreAuthorsView(APIView):
    """Manage store authors list and featured author for digital goods and Best Seller Books spotlight."""
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_business(self, request):
        user_id = None
        try:
            user_id = misc.get_id(request)
        except Exception:
            pass
        if not user_id and request.user and request.user.is_authenticated:
            user_id = getattr(request.user, 'user_id', None)
        if not user_id:
            return None
        return models.BusinessDetails.objects.filter(user__user_id=user_id).first()

    def get(self, request):
        business = self._get_business(request)
        if not business:
            return Response({'status': False, 'message': 'Unauthorized'}, status=401)

        authors = business.store_authors or []
        normalized = []
        for a in authors:
            if isinstance(a, str) and a.strip():
                normalized.append({'name': a.strip(), 'image': ''})
            elif isinstance(a, dict) and a.get('name'):
                normalized.append({
                    'name': a.get('name').strip(),
                    'image': (a.get('image') or '').strip()
                })

        featured_author = business.store_featured_author or ''
        featured_image = business.store_featured_author_image or ''
        if featured_author and not featured_image:
            matching = next((a for a in normalized if a['name'].lower() == featured_author.lower()), None)
            if matching and matching.get('image'):
                featured_image = matching['image']

        return Response({
            'status': True,
            'authors': normalized,
            'featured_author': featured_author,
            'featured_author_image': featured_image,
        })

    def post(self, request):
        business = self._get_business(request)
        if not business:
            return Response({'status': False, 'message': 'Unauthorized'}, status=401)

        data = request.data or {}
        action = data.get('action')

        authors = business.store_authors or []
        normalized = []
        for a in authors:
            if isinstance(a, str) and a.strip():
                normalized.append({'name': a.strip(), 'image': ''})
            elif isinstance(a, dict) and a.get('name'):
                normalized.append({
                    'name': a.get('name').strip(),
                    'image': (a.get('image') or '').strip()
                })

        if action == 'add_author':
            name = (data.get('name') or '').strip()
            if not name:
                return Response({'status': False, 'message': 'Author name cannot be empty'}, status=400)

            photo_file = (
                request.FILES.get('image') or
                request.FILES.get('author_image') or
                request.FILES.get('photo') or
                request.FILES.get('file')
            )
            raw_img = data.get('image')
            if not photo_file and hasattr(raw_img, 'read'):
                photo_file = raw_img

            image_url = ''
            if photo_file:
                import uuid
                ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
                raw_ext = photo_file.name.split('.')[-1].lower() if (hasattr(photo_file, 'name') and '.' in photo_file.name) else ''
                if raw_ext and raw_ext not in ALLOWED_EXTENSIONS:
                    return Response({
                        'status': False,
                        'message': f'Invalid image format ".{raw_ext}". Supported formats are JPG, PNG, WEBP, and GIF.'
                    }, status=400)

                content_type = getattr(photo_file, 'content_type', '')
                if content_type and not content_type.startswith('image/'):
                    return Response({
                        'status': False,
                        'message': 'Uploaded file is not a valid image format.'
                    }, status=400)

                if hasattr(photo_file, 'size') and photo_file.size > 5 * 1024 * 1024:
                    return Response({
                        'status': False,
                        'message': 'Author photo exceeds maximum allowed size of 5MB.'
                    }, status=400)

                ext = raw_ext if raw_ext in ALLOWED_EXTENSIONS else 'jpg'
                filename = f"store_authors/author_{business.id}_{uuid.uuid4().hex[:8]}.{ext}"
                saved_path = default_storage.save(filename, photo_file)
                image_url = default_storage.url(saved_path)
            else:
                raw_url = data.get('image_url') or (data.get('image') if isinstance(data.get('image'), str) else '') or ''
                image_url = raw_url.strip()

            existing = next((a for a in normalized if a['name'].lower() == name.lower()), None)
            if existing:
                if image_url:
                    existing['image'] = image_url
            else:
                normalized.append({'name': name, 'image': image_url})

            business.store_authors = normalized
            update_fields = ['store_authors']
            if business.store_featured_author and business.store_featured_author.lower() == name.lower() and image_url:
                business.store_featured_author_image = image_url
                update_fields.append('store_featured_author_image')
            business.save(update_fields=update_fields)

            return Response({
                'status': True,
                'message': f'Author "{name}" saved successfully',
                'authors': normalized,
                'featured_author': business.store_featured_author or '',
                'featured_author_image': business.store_featured_author_image or '',
            })

        elif action == 'delete_author':
            name = (data.get('name') or '').strip()
            if not name:
                return Response({'status': False, 'message': 'Author name required'}, status=400)
            normalized = [a for a in normalized if a['name'].lower() != name.lower()]
            business.store_authors = normalized
            update_fields = ['store_authors']
            if business.store_featured_author and business.store_featured_author.lower() == name.lower():
                business.store_featured_author = ''
                business.store_featured_author_image = ''
                update_fields.extend(['store_featured_author', 'store_featured_author_image'])
            business.save(update_fields=update_fields)

            return Response({
                'status': True,
                'message': f'Author "{name}" deleted successfully',
                'authors': normalized,
                'featured_author': business.store_featured_author or '',
                'featured_author_image': business.store_featured_author_image or '',
            })

        elif action == 'set_featured_author':
            selected_name = (data.get('author_name') or data.get('featured_author') or '').strip()
            if not selected_name:
                business.store_featured_author = ''
                business.store_featured_author_image = ''
                business.save(update_fields=['store_featured_author', 'store_featured_author_image'])
                return Response({
                    'status': True,
                    'message': 'Featured author spotlight cleared',
                    'authors': normalized,
                    'featured_author': '',
                    'featured_author_image': '',
                })

            update_fields = ['store_featured_author', 'store_featured_author_image']
            matching = next((a for a in normalized if a['name'].lower() == selected_name.lower()), None)
            if matching:
                business.store_featured_author = matching['name']
                fallback_img = (data.get('featured_author_image') or '').strip()
                author_img = matching.get('image') or fallback_img
                business.store_featured_author_image = author_img
                if fallback_img and not matching.get('image'):
                    matching['image'] = fallback_img
                    business.store_authors = normalized
                    update_fields.append('store_authors')
            else:
                business.store_featured_author = selected_name
                business.store_featured_author_image = (data.get('featured_author_image') or '').strip()

            business.save(update_fields=update_fields)
            return Response({
                'status': True,
                'message': f'BEST SELLER spotlight author set to "{business.store_featured_author}"',
                'authors': normalized,
                'featured_author': business.store_featured_author or '',
                'featured_author_image': business.store_featured_author_image or '',
            })

        else:
            if 'authors' in data:
                raw_list = data.get('authors')
                if isinstance(raw_list, str):
                    try:
                        raw_list = json.loads(raw_list)
                    except Exception:
                        raw_list = []
                new_normalized = []
                for item in raw_list:
                    if isinstance(item, str) and item.strip():
                        new_normalized.append({'name': item.strip(), 'image': ''})
                    elif isinstance(item, dict) and item.get('name'):
                        new_normalized.append({
                            'name': item['name'].strip(),
                            'image': (item.get('image') or '').strip()
                        })
                business.store_authors = new_normalized
                business.save(update_fields=['store_authors'])
                normalized = new_normalized

            return Response({
                'status': True,
                'authors': normalized,
                'featured_author': business.store_featured_author or '',
                'featured_author_image': business.store_featured_author_image or '',
            })


class StoreSocialGalleryView(APIView):
    """
    Public and Store Builder API endpoint for retrieving normalized Instagram social gallery posts.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        slug = request.GET.get('slug') or getattr(request, 'store_slug', None)
        instagram_url = request.GET.get('instagram_url')

        business = None
        if slug:
            business = models.BusinessDetails.objects.filter(store_slug=slug).first()

        from api.services.instagram_service import validate_instagram_url, get_instagram_service
        service = get_instagram_service()

        # Dynamic preview for Layout Builder
        if instagram_url:
            is_valid, username, canonical_url = validate_instagram_url(instagram_url)
            if is_valid and username:
                if business:
                    business.store_social_instagram = canonical_url
                    gallery = service.get_gallery_for_business(business)
                else:
                    posts = service.provider.fetch_posts(username)
                    gallery = {
                        "configured": True,
                        "profile": {"username": username, "url": canonical_url},
                        "posts": posts or []
                    }
                return Response({'status': True, 'data': gallery})
            else:
                return Response({
                    'status': True,
                    'data': {'configured': False, 'profile': None, 'posts': []}
                })

        if not business:
            return Response({'status': False, 'message': 'Store not found'}, status=404)

        gallery = service.get_gallery_for_business(business)
        return Response({'status': True, 'data': gallery})


from api.functions.digital_downloads import validate_digital_download_token
from django.http import HttpResponseForbidden, HttpResponseNotFound, FileResponse
from django.core import signing

def digital_product_download_view(request, token):
    """
    Secure download endpoint for purchased digital products.
    Requires a valid cryptographically signed token and verified completed order.
    """
    try:
        data = validate_digital_download_token(token)
    except signing.SignatureExpired:
        return HttpResponseForbidden("This download link has expired. Please contact support or the store owner.")
    except Exception:
        return HttpResponseForbidden("Invalid or corrupted download token.")

    invoice_id = data.get('invoice_id')
    item_id = data.get('item_id')

    if not invoice_id or not item_id:
        return HttpResponseForbidden("Invalid token payload.")

    invoice = models.UserInvoices.objects.filter(invoice_id=invoice_id).first()
    if not invoice:
        return HttpResponseNotFound("Order record not found.")

    if invoice.invoice_status != 'completed':
        return HttpResponseForbidden("Payment has not been completed for this order. Download is strictly restricted to paid purchases.")

    # Verify that the item was part of this invoice
    has_item = invoice.invoice_items.filter(item_id=item_id).exists()
    if not has_item:
        return HttpResponseForbidden("This item was not purchased as part of this order.")

    product = models.UserItems.objects.filter(item_id=item_id).first()
    if not product or not product.is_digital or not product.digital_file:
        return HttpResponseNotFound("Digital product asset not found.")

    try:
        file_obj = product.digital_file.open('rb')
        download_name = product.digital_file_name or os.path.basename(product.digital_file.name)
        response = FileResponse(file_obj, as_attachment=True, filename=download_name)
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except Exception as e:
        return HttpResponseNotFound(f"Error accessing file: {str(e)}")


def secure_digital_media_guard(request, filepath):
    """
    Guards direct access to /media/docs/user/digital_products/<filepath>.
    Only allows authenticated merchants who own the file. Prevents direct unauthorized downloads.
    """
    user_id = None
    try:
        user_id = misc.get_id(request)
    except Exception:
        user_id = None

    if user_id:
        merchant = models.UserSecure.objects.filter(user_id=user_id).first()
        if merchant:
            # Check if this merchant owns a product with this digital file
            item_match = models.UserItems.objects.filter(user=merchant, digital_file__contains=filepath).first()
            if item_match and item_match.digital_file:
                try:
                    file_obj = item_match.digital_file.open('rb')
                    download_name = item_match.digital_file_name or os.path.basename(item_match.digital_file.name)
                    return FileResponse(file_obj, as_attachment=True, filename=download_name)
                except Exception:
                    pass

    return HttpResponseForbidden("Direct access to digital product assets is forbidden. Files may only be accessed via authorized purchase download links.")



