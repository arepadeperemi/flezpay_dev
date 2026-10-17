"""
AI Business Intelligence Toolkit
=================================
Centralized query functions that produce JSON-serializable business data
for the AI chat context. Each function accepts a UserSecure instance and
optional period parameters (month, year, start_date, end_date).

All functions return plain Python dicts/lists — never Django model instances.
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from collections import defaultdict
from calendar import monthrange

from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count, Q
from django.db.models.functions import TruncDate
from django.utils.timezone import now, make_aware

from api import models
from api.models import UserInvoices, UserInvoiceItems, UserItems
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_period(month=None, year=None):
    """Return (start_date, end_date) for the requested period.
    Defaults to current month when neither is supplied.
    """
    today = now()
    y = int(year) if year else today.year
    m = int(month) if month else today.month
    start = make_aware(datetime(y, m, 1))
    last_day = monthrange(y, m)[1]
    end = make_aware(datetime(y, m, last_day, 23, 59, 59, 999999))
    return start, end


def _completed_invoice_ids(user):
    """Return invoice_id list for completed invoices."""
    return list(
        UserInvoices.objects.filter(
            user_id=user, invoice_status='completed'
        ).values_list('invoice_id', flat=True)
    )


def _sales_aggregate(user, start, end, status='completed'):
    """Sum of (qty * amount) for invoice items in the given period/status."""
    return UserInvoiceItems.objects.filter(
        user__user_id=user,
        user__invoice_status=status,
        timestamp__range=[start, end]
    ).aggregate(
        total=Sum(
            ExpressionWrapper(
                F('item_quantity') * F('item_amount'),
                output_field=DecimalField()
            )
        )
    )['total'] or Decimal('0.0')


def _round(val, places=2):
    return round(float(val), places)


# ---------------------------------------------------------------------------
# 1. Current Balance
# ---------------------------------------------------------------------------

def get_current_balance(user):
    """Wallet balance (credit minus outgoing)."""
    from api.user_data.data_views import calculate_total_balance
    balance = calculate_total_balance(user)
    return {"current_balance": _round(balance)}


# ---------------------------------------------------------------------------
# 2. Invoice Summary
# ---------------------------------------------------------------------------

def get_invoice_summary(user, month=None, year=None):
    """Paid/outstanding totals and counts for the given period."""
    start, end = _resolve_period(month, year)
    today = now()

    total_paid = _round(_sales_aggregate(user, start, end, 'completed'))
    total_outstanding = _round(_sales_aggregate(user, start, end, 'pending'))

    pending_count = UserInvoices.objects.filter(
        user_id=user, invoice_status='pending',
        timestamp__range=[start, end]
    ).count()

    completed_count = UserInvoices.objects.filter(
        user_id=user, invoice_status='completed',
        timestamp__range=[start, end]
    ).count()

    overdue_cutoff = today - timedelta(days=30)
    overdue_qs = UserInvoices.objects.filter(
        user_id=user, invoice_status='pending',
        timestamp__lt=overdue_cutoff
    )
    overdue_count = overdue_qs.count()
    overdue_amount = _round(
        UserInvoiceItems.objects.filter(
            user__user_id=user,
            user__invoice_status='pending',
            timestamp__lt=overdue_cutoff
        ).aggregate(
            total=Sum(ExpressionWrapper(
                F('item_quantity') * F('item_amount'),
                output_field=DecimalField()
            ))
        )['total'] or 0
    )

    return {
        "total_paid": total_paid,
        "total_outstanding": total_outstanding,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "overdue_count": overdue_count,
        "overdue_amount": overdue_amount,
    }


# ---------------------------------------------------------------------------
# 3. Invoices With Staff
# ---------------------------------------------------------------------------

def get_invoices_with_staff(user, month=None, year=None, limit=20):
    """Recent invoices enriched with cashier/staff names and line items."""
    start, end = _resolve_period(month, year)
    invoices = UserInvoices.objects.filter(
        user_id=user, timestamp__range=[start, end]
    ).order_by('-timestamp')[:limit]

    result = []
    for inv in invoices:
        # Resolve cashier name
        cashier_name = None
        if inv.cashier_id:
            manager = models.UserManagers.objects.filter(
                uniq_id=inv.cashier_id
            ).first()
            if manager:
                cashier_name = manager.manager_name

        items = UserInvoiceItems.objects.filter(
            item_invoice_id=inv.invoice_id
        ).values('item_name', 'item_amount', 'item_quantity')

        total = sum(
            float(i['item_amount']) * i['item_quantity'] for i in items
        )

        result.append({
            "invoice_id": inv.invoice_id,
            "status": inv.invoice_status,
            "type": inv.invoice_type,
            "cashier": cashier_name or "Owner",
            "customer_name": inv.customer_name or "Walk-in",
            "customer_email": inv.customer_email,
            "customer_phone": inv.customer_phone,
            "total": _round(total),
            "items_count": len(items),
            "items": list(items),
            "note": inv.invoice_note,
            "due_date": str(inv.due_date) if inv.due_date else None,
            "date": inv.timestamp.isoformat(),
        })

    return result


# ---------------------------------------------------------------------------
# 4. Revenue Projections
# ---------------------------------------------------------------------------

def get_revenue_projections(user, month=None, year=None):
    """Current month sales, projection, and month-over-month change."""
    start, end = _resolve_period(month, year)
    today = now()
    current_day = today.day

    this_month_total = _sales_aggregate(user, start, today, 'completed')

    # Previous month
    prev_end = start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    prev_start = make_aware(datetime.combine(prev_start, datetime.min.time()))
    prev_end_aware = make_aware(datetime.combine(prev_end, datetime.max.time()))
    last_month_total = _sales_aggregate(user, prev_start, prev_end_aware, 'completed')

    # Last 7 days average for weighted projection
    seven_days_ago = today - timedelta(days=6)
    last_7_days_total = _sales_aggregate(
        user,
        make_aware(datetime.combine(seven_days_ago, datetime.min.time())),
        today,
        'completed'
    )

    days_in_month = monthrange(today.year, today.month)[1]
    days_remaining = days_in_month - current_day

    avg_month = this_month_total / Decimal(current_day) if current_day else Decimal('0.0')
    avg_7d = last_7_days_total / Decimal(7)
    weighted_avg = (avg_7d * Decimal('0.7')) + (avg_month * Decimal('0.3'))
    projected = this_month_total + (weighted_avg * days_remaining)

    change_pct = (
        ((this_month_total - last_month_total) / last_month_total) * 100
        if last_month_total > 0
        else (100 if this_month_total > 0 else 0)
    )

    today_start = make_aware(datetime.combine(today, datetime.min.time()))
    yesterday = today - timedelta(days=1)
    yesterday_start = make_aware(datetime.combine(yesterday, datetime.min.time()))
    yesterday_end = make_aware(datetime.combine(yesterday, datetime.max.time()))

    sales_today = _sales_aggregate(user, today_start, today, 'completed')
    sales_yesterday = _sales_aggregate(user, yesterday_start, yesterday_end, 'completed')

    return {
        "sales_this_month": _round(this_month_total),
        "sales_today": _round(sales_today),
        "sales_yesterday": _round(sales_yesterday),
        "last_month_total": _round(last_month_total),
        "projected_monthly_revenue": _round(projected),
        "month_over_month_change_pct": _round(change_pct),
        "daily_average_this_month": _round(avg_month),
        "daily_average_last_7_days": _round(avg_7d),
        "days_remaining": days_remaining,
    }


# ---------------------------------------------------------------------------
# 5. Best Performing Items
# ---------------------------------------------------------------------------

def get_best_performing_items(user, month=None, year=None, by_department=False, limit=10):
    """
    Get top best-performing products/items ranked by total sales revenue.

    Args:
        user: The merchant user account instance.
        month: Optional integer month (1-12) to query.
        year: Optional integer year (e.g. 2025, 2026) to query.
        by_department: If True, group top items by department.
        limit: Number of top performing items to return (default 10).
    """
    start, end = _resolve_period(month, year)
    today = now()
    end_cap = min(end, today)

    invoice_ids = _completed_invoice_ids(user)

    items_qs = UserInvoiceItems.objects.filter(
        item_invoice_id__in=invoice_ids,
        timestamp__range=[start, end_cap]
    ).exclude(
        item_name__icontains='Tax'
    ).exclude(
        item_name__icontains='Subscription'
    ).exclude(
        item_name__icontains='Delivery'
    )

    if by_department:
        # Join back to UserItems to get department
        result = {}
        for item in items_qs.values('item_name').annotate(
            total_sales=Sum(ExpressionWrapper(
                F('item_quantity') * F('item_amount'),
                output_field=DecimalField()
            )),
            units_sold=Sum('item_quantity')
        ).order_by('-total_sales'):
            inv_item = UserItems.objects.filter(
                user=user, item_name__iexact=item['item_name']
            ).first()
            dept = (inv_item.item_department if inv_item and inv_item.item_department else 'General')
            if dept not in result:
                result[dept] = []
            result[dept].append({
                "item": item['item_name'],
                "total_sales": _round(item['total_sales']),
                "units_sold": item['units_sold'] or 0,
            })
        # Sort each department list and limit
        for dept in result:
            result[dept] = sorted(result[dept], key=lambda x: x['total_sales'], reverse=True)[:limit]
        return result
    else:
        return [
            {
                "item": item['item_name'],
                "total_sales": _round(item['total_sales']),
                "units_sold": item['units_sold'] or 0,
            }
            for item in items_qs.values('item_name').annotate(
                total_sales=Sum(ExpressionWrapper(
                    F('item_quantity') * F('item_amount'),
                    output_field=DecimalField()
                )),
                units_sold=Sum('item_quantity')
            ).order_by('-total_sales')[:limit]
        ]


# ---------------------------------------------------------------------------
# 6. Worst Performing Items
# ---------------------------------------------------------------------------

def get_worst_performing_items(user, month=None, year=None, limit=10):
    """
    Get bottom lowest-performing products/items by total sales revenue.

    Args:
        user: The merchant user account instance.
        month: Optional integer month (1-12) to query.
        year: Optional integer year (e.g. 2025, 2026) to query.
        limit: Number of lowest performing items to return (default 10).
    """
    start, end = _resolve_period(month, year)
    today = now()
    end_cap = min(end, today)

    invoice_ids = _completed_invoice_ids(user)

    return [
        {
            "item": item['item_name'],
            "total_sales": _round(item['total_sales']),
            "units_sold": item['units_sold'] or 0,
        }
        for item in UserInvoiceItems.objects.filter(
            item_invoice_id__in=invoice_ids,
            timestamp__range=[start, end_cap]
        ).exclude(
            item_name__icontains='Tax'
        ).exclude(
            item_name__icontains='Subscription'
        ).exclude(
            item_name__icontains='Delivery'
        ).values('item_name').annotate(
            total_sales=Sum(ExpressionWrapper(
                F('item_quantity') * F('item_amount'),
                output_field=DecimalField()
            )),
            units_sold=Sum('item_quantity')
        ).order_by('total_sales')[:limit]
    ]


# ---------------------------------------------------------------------------
# 6b. Inventory Items Lookup
# ---------------------------------------------------------------------------

def get_inventory_items(user, search="", department="", in_stock_only=False, limit=50):
    """
    Look up inventory products with current stock counts, prices, and cost prices.

    Args:
        user: The merchant user account instance.
        search: Optional search keyword to match product name or code. Pass empty string ("") to retrieve all.
        department: Optional department filter.
        in_stock_only: If True, only return products with quantity > 0.
        limit: Max products to return (default 50).
    """
    try:
        limit = int(limit) if limit and str(limit).isdigit() else 50
    except Exception:
        limit = 50

    qs = UserItems.objects.filter(user=user)
    if search:
        search_clean = str(search).strip()
        generic_search_terms = {
            "all", "*", "%", "all items", "all products", "everything", "products",
            "items", "none", "any", "all_items", "all_products", "inventory",
            "list", "all inventory", "store items", "item", "product", "null",
            "undefined", "all item", "all product", "total", "full", "show all",
            "get all", "fetch all"
        }
        if search_clean.lower() not in generic_search_terms:
            qs = qs.filter(
                Q(item_name__icontains=search_clean) |
                Q(item_serial_number__icontains=search_clean) |
                Q(item_category__icontains=search_clean) |
                Q(item_department__icontains=search_clean)
            )
    if department:
        dept_clean = str(department).strip()
        generic_dept_terms = {
            "all", "*", "%", "all departments", "any", "none", "every", "null",
            "undefined", "all department", "department", "departments"
        }
        if dept_clean.lower() not in generic_dept_terms:
            qs = qs.filter(item_department__icontains=dept_clean)
    if in_stock_only:
        qs = qs.filter(item_quantity__gt=0)
    items = qs.order_by('-item_quantity')[:limit]
    return [
        {
            "name": item.item_name,
            "quantity": item.item_quantity if item.item_quantity is not None else 0,
            "price": _round(item.item_amount or 0),
            "cost_price": _round(item.item_buy_amount or 0),
            "department": item.item_department or "General",
            "category": item.item_category or "",
            "serial_number": item.item_serial_number or "",
            "expiry": str(item.item_expiry) if item.item_expiry else None,
        }
        for item in items
    ]


# ---------------------------------------------------------------------------
# 7. Sales Trend
# ---------------------------------------------------------------------------

def get_sales_trend(user, month=None, year=None):
    """Daily sales data points for the requested period."""
    start, end = _resolve_period(month, year)
    today = now()
    end_cap = min(end, today)

    invoice_ids = _completed_invoice_ids(user)

    daily_data = UserInvoiceItems.objects.filter(
        item_invoice_id__in=invoice_ids,
        timestamp__range=[start, end_cap]
    ).annotate(
        day=TruncDate('timestamp')
    ).values('day').annotate(
        daily_total=Sum(ExpressionWrapper(
            F('item_quantity') * F('item_amount'),
            output_field=DecimalField()
        )),
        order_count=Count('user', distinct=True)
    ).order_by('day')

    result = []
    for d in daily_data:
        date_obj = d['day']
        label = str(date_obj)
        if date_obj == today.date():
            label += " (Today)"
        elif date_obj == (today - timedelta(days=1)).date():
            label += " (Yesterday)"
            
        result.append({
            "date": label,
            "sales": _round(d['daily_total']),
            "orders": d['order_count'],
        })

    return result


# ---------------------------------------------------------------------------
# 8. Business Alerts
# ---------------------------------------------------------------------------

def get_business_alerts(user):
    """Actionable alerts: expiring items, low stock, overdue, negative margin."""
    from api.user_data.data_views import get_items_expiring_soon
    alerts = []
    today = now()

    # Expiring items
    expiring = get_items_expiring_soon(user)
    for item in expiring:
        alerts.append({
            "type": "expiring_soon",
            "severity": "warning",
            "message": f"\"{item['item_name']}\" expires on {item['item_expiry']} — {item['item_quantity']} units remaining.",
            "item_name": item['item_name'],
        })

    # Low stock (quantity <= 5 and > 0)
    low_stock = UserItems.objects.filter(
        user=user, item_quantity__gt=0, item_quantity__lte=5
    ).values('item_name', 'item_quantity', 'item_department')
    for item in low_stock:
        alerts.append({
            "type": "low_stock",
            "severity": "warning",
            "message": f"\"{item['item_name']}\" has only {item['item_quantity']} units left.",
            "item_name": item['item_name'],
            "department": item['item_department'] or "General",
        })

    # Out of stock
    out_of_stock_count = UserItems.objects.filter(
        user=user, item_quantity=0
    ).count()
    if out_of_stock_count > 0:
        alerts.append({
            "type": "out_of_stock",
            "severity": "critical",
            "message": f"{out_of_stock_count} product(s) are completely out of stock.",
        })

    # Overdue invoices
    overdue_cutoff = today - timedelta(days=30)
    overdue_count = UserInvoices.objects.filter(
        user_id=user, invoice_status='pending',
        timestamp__lt=overdue_cutoff
    ).count()
    if overdue_count > 0:
        alerts.append({
            "type": "overdue_invoices",
            "severity": "critical",
            "message": f"{overdue_count} invoice(s) are overdue (unpaid for 30+ days).",
        })

    # Negative margin items (selling below cost)
    neg_margin = list(UserItems.objects.filter(
        user=user,
        item_amount__lt=F('item_buy_amount')
    ).values_list('item_name', flat=True))
    if neg_margin:
        alerts.append({
            "type": "negative_margin",
            "severity": "info",
            "message": f"{len(neg_margin)} item(s) are selling below cost price (may be on promo): {', '.join(neg_margin[:5])}.",
        })

    return alerts


# ---------------------------------------------------------------------------
# 9. Overdue Invoices
# ---------------------------------------------------------------------------

def get_overdue_invoices(user, limit=20):
    """Detailed list of overdue (pending 30+ days) invoices."""
    today = now()
    overdue_cutoff = today - timedelta(days=30)

    invoices = UserInvoices.objects.filter(
        user_id=user, invoice_status='pending',
        timestamp__lt=overdue_cutoff
    ).order_by('timestamp')[:limit]

    result = []
    for inv in invoices:
        days_overdue = (today - inv.timestamp).days
        total = _round(
            UserInvoiceItems.objects.filter(
                item_invoice_id=inv.invoice_id
            ).aggregate(
                total=Sum(ExpressionWrapper(
                    F('item_quantity') * F('item_amount'),
                    output_field=DecimalField()
                ))
            )['total'] or 0
        )
        result.append({
            "invoice_id": inv.invoice_id,
            "customer_name": inv.customer_name or "Walk-in",
            "customer_email": inv.customer_email,
            "customer_phone": inv.customer_phone,
            "total": total,
            "days_overdue": days_overdue,
            "due_date": str(inv.due_date) if inv.due_date else None,
            "date_created": inv.timestamp.isoformat(),
        })

    return result


# ---------------------------------------------------------------------------
# 10. Debt Summary
# ---------------------------------------------------------------------------

def get_debt_summary(user):
    """Outstanding totals with aging buckets (0-30, 31-60, 61-90, 90+ days)."""
    today = now()

    def _bucket_total(days_start, days_end=None):
        qs = UserInvoiceItems.objects.filter(
            user__user_id=user,
            user__invoice_status='pending'
        )
        if days_end is not None:
            qs = qs.filter(
                timestamp__lt=today - timedelta(days=days_start),
                timestamp__gte=today - timedelta(days=days_end)
            )
        else:
            qs = qs.filter(timestamp__lt=today - timedelta(days=days_start))

        return _round(
            qs.aggregate(
                total=Sum(ExpressionWrapper(
                    F('item_quantity') * F('item_amount'),
                    output_field=DecimalField()
                ))
            )['total'] or 0
        )

    total_outstanding = _round(
        UserInvoiceItems.objects.filter(
            user__user_id=user,
            user__invoice_status='pending'
        ).aggregate(
            total=Sum(ExpressionWrapper(
                F('item_quantity') * F('item_amount'),
                output_field=DecimalField()
            ))
        )['total'] or 0
    )

    return {
        "total_outstanding": total_outstanding,
        "aging": {
            "0_to_30_days": _round(total_outstanding - _bucket_total(30)),
            "31_to_60_days": _bucket_total(30, 60),
            "61_to_90_days": _bucket_total(60, 90),
            "over_90_days": _bucket_total(90),
        }
    }


# ---------------------------------------------------------------------------
# 11. Department Performance
# ---------------------------------------------------------------------------

def get_department_performance(user, month=None, year=None):
    """Revenue, item count, and staff count per department."""
    start, end = _resolve_period(month, year)
    today = now()
    end_cap = min(end, today)

    invoice_ids = _completed_invoice_ids(user)

    # Revenue per department via UserItems join
    dept_revenue = defaultdict(lambda: {"revenue": Decimal('0.0'), "units_sold": 0, "product_count": 0})

    sold_items = UserInvoiceItems.objects.filter(
        item_invoice_id__in=invoice_ids,
        timestamp__range=[start, end_cap]
    ).values('item_name').annotate(
        total_sales=Sum(ExpressionWrapper(
            F('item_quantity') * F('item_amount'),
            output_field=DecimalField()
        )),
        units_sold=Sum('item_quantity')
    )

    for si in sold_items:
        inv_item = UserItems.objects.filter(
            user=user, item_name__iexact=si['item_name']
        ).first()
        dept = (inv_item.item_department if inv_item and inv_item.item_department else 'General')
        dept_revenue[dept]["revenue"] += si['total_sales'] or Decimal('0.0')
        dept_revenue[dept]["units_sold"] += si['units_sold'] or 0

    # Product count + staff count per department
    departments = models.CashierDepartments.objects.filter(user=user)
    result = []

    seen_depts = set()
    for dept in departments:
        name = dept.department_name or 'General'
        seen_depts.add(name)
        data = dept_revenue.get(name, {"revenue": Decimal('0.0'), "units_sold": 0})
        result.append({
            "department": name,
            "revenue": _round(data["revenue"]),
            "units_sold": data["units_sold"],
            "product_count": UserItems.objects.filter(user=user, item_department=name).count(),
            "staff_count": models.UserPayroll.objects.filter(user_id=user, department=name).count(),
            "manager_count": models.UserManagers.objects.filter(user=user, manager_department=name).count(),
        })

    # Include departments that have sales but no CashierDepartments record
    for name, data in dept_revenue.items():
        if name not in seen_depts:
            result.append({
                "department": name,
                "revenue": _round(data["revenue"]),
                "units_sold": data["units_sold"],
                "product_count": UserItems.objects.filter(user=user, item_department=name).count(),
                "staff_count": models.UserPayroll.objects.filter(user_id=user, department=name).count(),
                "manager_count": models.UserManagers.objects.filter(user=user, manager_department=name).count(),
            })

    return sorted(result, key=lambda x: x['revenue'], reverse=True)


# ---------------------------------------------------------------------------
# 12. Payroll Summary
# ---------------------------------------------------------------------------

def get_payroll_summary(user):
    """Payroll totals awaiting disbursement, breakdown by pay date, and per-employee details."""
    payrolls = models.UserPayroll.objects.filter(user_id=user)

    current = datetime.now()
    today_day = current.day
    days_in_month = monthrange(current.year, current.month)[1]

    total_to_disburse = 0.0
    total_disbursed_so_far = 0.0
    active_count = 0
    blocked_count = 0

    by_date = defaultdict(lambda: {"amount": 0.0, "staff": []})
    employees = []

    for payroll in payrolls:
        if payroll.pay_status == 'active':
            active_count += 1
        else:
            blocked_count += 1

        base_amount = payroll.get_pay_amount()
        allowance_amount = payroll.get_allowances()
        deduction_amount = payroll.get_deductions()
        net_amount = base_amount + allowance_amount - deduction_amount
        frequency = payroll.get_pay_frequency() or 'monthly'
        pay_date = payroll.get_pay_date()

        # Calculate monthly obligation and disbursed-to-date
        monthly_obligation = 0.0
        disbursed = 0.0
        if frequency == 'daily':
            monthly_obligation = net_amount * days_in_month
            disbursed = net_amount * today_day
        elif frequency == 'weekly':
            monthly_obligation = net_amount * (days_in_month // 7)
            elapsed_days = (current - current.replace(day=1)).days + 1
            disbursed = net_amount * (elapsed_days // 7)
        elif frequency == 'monthly':
            monthly_obligation = net_amount
            disbursed = net_amount if today_day >= 1 else 0.0
        elif frequency == 'yearly':
            monthly_portion = net_amount / 12
            monthly_obligation = monthly_portion
            disbursed = monthly_portion * (today_day / days_in_month)

        total_to_disburse += monthly_obligation
        total_disbursed_so_far += disbursed

        employee_entry = {
            "name": payroll.account_name,
            "department": payroll.department or "General",
            "job_title": payroll.job_title or "N/A",
            "frequency": frequency,
            "pay_date": pay_date,
            "base_amount": _round(base_amount),
            "allowances": _round(allowance_amount),
            "deductions": _round(deduction_amount),
            "net_amount": _round(net_amount),
            "monthly_obligation": _round(monthly_obligation),
            "status": payroll.pay_status,
        }
        employees.append(employee_entry)

        # Group by pay date
        date_key = pay_date or "unscheduled"
        by_date[date_key]["amount"] += net_amount
        by_date[date_key]["staff"].append(payroll.account_name)

    awaiting_disbursement = max(total_to_disburse - total_disbursed_so_far, 0.0)

    return {
        "total_monthly_obligation": _round(total_to_disburse),
        "total_disbursed_so_far": _round(total_disbursed_so_far),
        "awaiting_disbursement": _round(awaiting_disbursement),
        "active_employees": active_count,
        "blocked_employees": blocked_count,
        "total_employees": active_count + blocked_count,
        "by_pay_date": {
            k: {"amount": _round(v["amount"]), "staff_count": len(v["staff"]), "staff_names": v["staff"]}
            for k, v in sorted(by_date.items())
        },
        "employees": employees,
    }


# ---------------------------------------------------------------------------
# 13. Business Summary
# ---------------------------------------------------------------------------

def get_business_summary(user, month=None, year=None):
    """High-level summary aggregating key metrics."""
    today = now()
    start, end = _resolve_period(month, year)

    # Business identity
    business = models.BusinessDetails.objects.filter(user=user).first()
    user_details = models.UserDetails.objects.filter(user=user).first()

    business_name = (
        business.business_name if business and business.business_name
        else (f"{user_details.first_name} {user_details.last_name}" if user_details else "Valued Merchant")
    )
    currency_symbol = user_details.currency if user_details and user_details.currency else "₦" 

    balance = get_current_balance(user)
    invoices = get_invoice_summary(user, month, year)
    revenue = get_revenue_projections(user, month, year)

    # Staff/manager counts
    total_staff = models.UserPayroll.objects.filter(user_id=user).count()
    total_managers = models.UserManagers.objects.filter(user=user).count()

    # Inventory snapshot
    total_products = UserItems.objects.filter(user=user).count()
    total_inventory_value = _round(
        UserItems.objects.filter(user=user).aggregate(
            total=Sum(ExpressionWrapper(
                F('item_amount') * F('item_quantity'),
                output_field=DecimalField()
            ))
        )['total'] or 0
    )

    return {
        "business_name": business_name,
        "currency": currency_symbol,
        "period": f"{start.strftime('%Y-%m')}",
        "current_balance": balance["current_balance"],
        "total_staff": total_staff,
        "total_managers": total_managers,
        "total_products": total_products,
        "total_inventory_value": total_inventory_value,
        **invoices,
        **revenue,
    }

# ---------------------------------------------------------------------------
# 14. Daily Sales Breakdown (per-day table for AI date lookups)
# ---------------------------------------------------------------------------

def get_daily_sales_breakdown(user, month=None, year=None):
    """Return a per-day table with sales, transaction count, and items sold.
    This gives the AI an unambiguous lookup table for any date in the month."""
    start, end = _resolve_period(month, year)
    today = now()
    end_cap = min(end, today)

    invoice_ids = _completed_invoice_ids(user)

    daily_data = UserInvoiceItems.objects.filter(
        item_invoice_id__in=invoice_ids,
        timestamp__range=[start, end_cap]
    ).annotate(
        day=TruncDate('timestamp')
    ).values('day').annotate(
        daily_total=Sum(ExpressionWrapper(
            F('item_quantity') * F('item_amount'),
            output_field=DecimalField()
        )),
        transaction_count=Count('user', distinct=True),
        items_sold=Sum('item_quantity')
    ).order_by('day')

    # Build a complete list for every day from start to end_cap
    result = []
    current_date = start.date()
    end_date = end_cap.date()

    # Index the query results by date for O(1) lookup
    data_by_date = {}
    for d in daily_data:
        data_by_date[d['day']] = d

    while current_date <= end_date:
        d = data_by_date.get(current_date)
        day_label = str(current_date)
        day_of_week = current_date.strftime('%A')

        if current_date == today.date():
            day_label += " (Today)"
        elif current_date == (today - timedelta(days=1)).date():
            day_label += " (Yesterday)"

        result.append({
            "date": day_label,
            "day_of_week": day_of_week,
            "sales": _round(d['daily_total']) if d else 0.0,
            "transactions": d['transaction_count'] if d else 0,
            "items_sold": d['items_sold'] if d else 0,
        })
        current_date += timedelta(days=1)

    return result


# ---------------------------------------------------------------------------
# 15. Date Range Sales (pre-computed aggregates for common ranges)
# ---------------------------------------------------------------------------

def get_date_range_sales(user):
    """Pre-compute sales aggregates for common date ranges the user might ask about."""
    today = now()
    today_start = make_aware(datetime.combine(today, datetime.min.time()))

    def _range_aggregate(start_dt, end_dt):
        """Aggregate sales, transactions, items for an arbitrary date range."""
        invoice_ids = list(
            UserInvoices.objects.filter(
                user_id=user, invoice_status='completed',
                timestamp__range=[start_dt, end_dt]
            ).values_list('invoice_id', flat=True)
        )
        agg = UserInvoiceItems.objects.filter(
            item_invoice_id__in=invoice_ids,
            timestamp__range=[start_dt, end_dt]
        ).aggregate(
            total_sales=Sum(ExpressionWrapper(
                F('item_quantity') * F('item_amount'),
                output_field=DecimalField()
            )),
            transaction_count=Count('user', distinct=True),
            items_sold=Sum('item_quantity')
        )
        return {
            "sales": _round(agg['total_sales'] or 0),
            "transactions": agg['transaction_count'] or 0,
            "items_sold": agg['items_sold'] or 0,
        }

    # Yesterday
    yesterday = today - timedelta(days=1)
    yesterday_start = make_aware(datetime.combine(yesterday, datetime.min.time()))
    yesterday_end = make_aware(datetime.combine(yesterday, datetime.max.time()))

    # Last 3 days
    three_days_ago = today - timedelta(days=3)
    three_days_start = make_aware(datetime.combine(three_days_ago, datetime.min.time()))

    # Last 7 days
    seven_days_ago = today - timedelta(days=7)
    seven_days_start = make_aware(datetime.combine(seven_days_ago, datetime.min.time()))

    # This week (Monday to today)
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    this_week_start = make_aware(datetime.combine(monday.date(), datetime.min.time()))

    # First week of month (1st to 7th)
    first_of_month_date = date(today.year, today.month, 1)
    first_week_end_day = min(7, monthrange(today.year, today.month)[1])
    first_week_end = make_aware(datetime.combine(
        date(today.year, today.month, first_week_end_day),
        datetime.max.time()
    ))
    first_week_start = make_aware(datetime.combine(
        first_of_month_date,
        datetime.min.time()
    ))

    # First of current month (single day)
    first_day_start = make_aware(datetime.combine(date(today.year, today.month, 1), datetime.min.time()))
    first_day_end = make_aware(datetime.combine(date(today.year, today.month, 1), datetime.max.time()))

    return {
        "today": {
            "period": str(today.date()),
            **_range_aggregate(today_start, today)
        },
        "yesterday": {
            "period": str(yesterday.date()),
            **_range_aggregate(yesterday_start, yesterday_end)
        },
        "last_3_days": {
            "period": f"{three_days_ago.date()} to {today.date()}",
            **_range_aggregate(three_days_start, today)
        },
        "last_7_days": {
            "period": f"{seven_days_ago.date()} to {today.date()}",
            **_range_aggregate(seven_days_start, today)
        },
        "this_week": {
            "period": f"{monday.date()} (Mon) to {today.date()}",
            **_range_aggregate(this_week_start, today)
        },
        "first_week_of_month": {
            "period": f"{date(today.year, today.month, 1)} to {date(today.year, today.month, first_week_end_day)}",
            **_range_aggregate(first_week_start, first_week_end)
        },
        "first_of_month": {
            "period": str(date(today.year, today.month, 1)),
            **_range_aggregate(first_day_start, first_day_end)
        },
    }


# ---------------------------------------------------------------------------
# Historical Monthly Overview — summary of ALL months with data
# ---------------------------------------------------------------------------

MONTH_NAMES = [
    '', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]


def get_monthly_overview(user):
    """Return a high-level summary of every month that has any sales data.
    This lets the AI know what time periods are available for querying."""
    from django.db.models.functions import TruncMonth
    import datetime as dt

    invoice_ids = _completed_invoice_ids(user)

    monthly_data = UserInvoiceItems.objects.filter(
        item_invoice_id__in=invoice_ids
    ).annotate(
        month=TruncMonth('timestamp', tzinfo=dt.timezone.utc)
    ).values('month').annotate(
        total_sales=Sum(ExpressionWrapper(
            F('item_quantity') * F('item_amount'),
            output_field=DecimalField()
        )),
        transaction_count=Count('user', distinct=True),
        items_sold=Sum('item_quantity')
    ).order_by('month')

    result = []
    for entry in monthly_data:
        if entry['month']:
            m = entry['month']
            result.append({
                "month": f"{MONTH_NAMES[m.month]} {m.year}",
                "month_num": m.month,
                "year": m.year,
                "total_sales": _round(entry['total_sales'] or 0),
                "transactions": entry['transaction_count'] or 0,
                "items_sold": entry['items_sold'] or 0,
            })
    return result


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 20. Invoice Payment Follow-up Emails
# ---------------------------------------------------------------------------

def send_invoice_followup_email(user, invoice_id="", custom_message=""):
    """
    Send polite payment reminder and follow-up emails to customers with outstanding or overdue invoices.
    
    Args:
        user: UserSecure merchant instance.
        invoice_id: Optional specific invoice ID (e.g. 'INV-ABC123XYZ'), list of IDs, or collective keywords like 'all', 'overdue', 'debtors'.
        custom_message: Optional custom note or urgency message to include in the email body.
    """
    

    biz = models.BusinessDetails.objects.filter(user=user).first()
    business_name = biz.business_name if (biz and biz.business_name) else "Our Store"

    # Base query: all pending invoices for this user
    base_query = UserInvoices.objects.filter(user_id=user, invoice_status='pending')

    # Normalize invoice_id parameter
    is_collective = False
    only_overdue = False
    target_ids = []

    collective_terms = {
        "all", "all_overdue", "all overdue", "overdue", "all_pending", "all pending", "pending",
        "all_outstanding", "all outstanding", "outstanding", "debtor", "debtors", "all debtors",
        "all_debtors", "all invoices", "all_invoices", "all the four", "all four", "all 4", "4", "four"
    }

    if not invoice_id:
        is_collective = True
    elif isinstance(invoice_id, (list, tuple, set)):
        raw_items = [str(x).strip() for x in invoice_id if str(x).strip()]
        for item in raw_items:
            clean = item.lstrip('#').strip()
            if clean.lower() in collective_terms:
                is_collective = True
                if "overdue" in clean.lower():
                    only_overdue = True
            elif clean:
                target_ids.append(clean.upper())
    elif isinstance(invoice_id, str):
        clean_str = invoice_id.strip()
        lower_str = clean_str.lower()
        if lower_str in collective_terms or lower_str.startswith("all ") or lower_str.startswith("all_") or "debtor" in lower_str or "overdue" in lower_str or "debt" in lower_str:
            is_collective = True
            if "overdue" in lower_str:
                only_overdue = True
        elif "," in clean_str:
            target_ids = [x.strip().lstrip('#').upper() for x in clean_str.split(",") if x.strip()]
        else:
            target_ids = [clean_str.lstrip('#').upper()]
    else:
        is_collective = True

    query = base_query
    if not is_collective and target_ids:
        # Check if requested IDs match in pending invoices
        matching = query.filter(invoice_id__in=target_ids)
        if not matching.exists():
            # Try case-insensitive matching
            q_objs = Q()
            for tid in target_ids:
                q_objs |= Q(invoice_id__iexact=tid)
            matching = query.filter(q_objs)

        if matching.exists():
            query = matching
        else:
            # Check if invoice exists in any status
            all_invoices = UserInvoices.objects.filter(user_id=user)
            existing = all_invoices.filter(Q(invoice_id__in=target_ids) | Q(invoice_id__iexact=target_ids[0])).first()
            if existing:
                if existing.invoice_status == 'completed':
                    return {"success": False, "message": f"Invoice '{existing.invoice_id}' has already been paid and marked completed."}
                if not existing.customer_email:
                    return {"success": False, "message": f"Invoice '{existing.invoice_id}' does not have a customer email address on file."}
            
            # If the user has pending invoices and target_id looked like natural language, fallback to collective
            if query.exists() and any(k in target_ids[0].lower() for k in ["debt", "overdue", "pending", "bill", "unpaid", "all"]):
                is_collective = True
            else:
                return {"success": False, "message": f"Invoice '{', '.join(target_ids)}' was not found in your records."}

    # If specifically requested overdue, try filtering to overdue first (due_date past or older than 30 days)
    if only_overdue:
        today = now().date()
        overdue_cutoff = now() - timedelta(days=30)
        overdue_query = query.filter(Q(due_date__lt=today) | Q(timestamp__lt=overdue_cutoff))
        if overdue_query.exists():
            query = overdue_query

    all_found_invoices = list(query)
    if not all_found_invoices:
        return {"success": False, "message": "No pending or overdue invoices were found in your records."}

    # Partition by presence of valid customer email
    invoices = [inv for inv in all_found_invoices if inv.customer_email and inv.customer_email.strip()]
    skipped_without_email = [inv for inv in all_found_invoices if not inv.customer_email or not inv.customer_email.strip()]

    if not invoices:
        no_email_ids = [inv.invoice_id for inv in skipped_without_email]
        return {
            "success": False,
            "message": f"Found {len(skipped_without_email)} pending invoice(s) ({', '.join(no_email_ids)}), but none have a customer email address on file to send reminders to."
        }

    # Group invoices by unique customer email to prevent sending duplicate emails to the same recipient
    grouped_customers = defaultdict(lambda: {
        "customer_name": "",
        "customer_email": "",
        "invoices": [],
        "bank_name": "",
        "account_number": "",
        "account_name": "",
    })

    for inv in invoices:
        email = inv.customer_email.strip().lower()
        if not email:
            continue

        items = UserInvoiceItems.objects.filter(item_invoice_id=inv.invoice_id)
        total_amount = sum(float(it.item_amount) * it.item_quantity for it in items)

        entry = grouped_customers[email]
        if not entry["customer_name"] and inv.customer_name:
            entry["customer_name"] = inv.customer_name
        entry["customer_email"] = inv.customer_email.strip()

        if not entry["bank_name"] and inv.designated_bank_name:
            entry["bank_name"] = inv.designated_bank_name
            entry["account_number"] = inv.designated_account_number or ""
            entry["account_name"] = inv.designated_account_name or business_name

        entry["invoices"].append({
            "invoice_id": inv.invoice_id,
            "total_amount": total_amount,
            "total_amount_formatted": f"₦{total_amount:,.2f}",
            "due_date": f"{inv.due_date}" if inv.due_date else "",
        })

    sent_records = []
    failed_records = []

    for email_key, cust in grouped_customers.items():
        invoices_list = cust["invoices"]
        invoices_count = len(invoices_list)
        is_multi_invoice = invoices_count > 1
        grand_total = sum(inv_item["total_amount"] for inv_item in invoices_list)
        cust_name = cust["customer_name"] or "Valued Customer"

        if is_multi_invoice:
            subject = f"Friendly Payment Reminder: {invoices_count} Outstanding Invoices - {business_name}"
            invoice_id_display = ", ".join(f"#{x['invoice_id']}" for x in invoices_list)
            first_due = next((x["due_date"] for x in invoices_list if x["due_date"]), "")
        else:
            first_inv = invoices_list[0]
            subject = f"Friendly Payment Reminder: Invoice #{first_inv['invoice_id']} - {business_name}"
            invoice_id_display = first_inv["invoice_id"]
            first_due = first_inv["due_date"]

        context = {
            "subject": subject,
            "customer_name": cust_name,
            "business_name": business_name,
            "is_multi_invoice": is_multi_invoice,
            "invoices_count": invoices_count,
            "invoices_list": invoices_list,
            "invoice_id": invoice_id_display,
            "total_amount": grand_total,
            "total_amount_formatted": f"₦{grand_total:,.2f}",
            "due_date": first_due,
            "bank_name": cust["bank_name"],
            "account_number": cust["account_number"],
            "account_name": cust["account_name"] or business_name,
            "custom_message": custom_message.strip() if custom_message else "",
            "user_email": cust["customer_email"],
        }

        try:
            html_content = render_to_string('emails/invoice_followup.html', context)
            text_content = strip_tags(html_content)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@flezpay.com'),
                to=[cust["customer_email"]]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            sent_records.append({
                "invoice_ids": [x["invoice_id"] for x in invoices_list],
                "customer_name": cust_name,
                "customer_email": cust["customer_email"],
                "invoices_count": invoices_count,
                "total_amount": f"₦{grand_total:,.2f}"
            })
        except Exception as e:
            failed_records.append({
                "customer_email": cust["customer_email"],
                "invoice_ids": [x["invoice_id"] for x in invoices_list],
                "error": str(e)
            })

    total_invoices_covered = sum(rec["invoices_count"] for rec in sent_records)
    skipped_ids = [inv.invoice_id for inv in skipped_without_email]
    
    if sent_records:
        msg = f"Successfully sent consolidated payment reminders directly to {len(sent_records)} unique customer(s) covering {total_invoices_covered} outstanding invoice(s)."
        if skipped_without_email:
            msg += f" Note: {len(skipped_without_email)} invoice(s) ({', '.join(skipped_ids)}) could not be emailed because no customer email address is on file."
    else:
        msg = f"Failed to send email reminders: {failed_records[0]['error'] if failed_records else 'Unknown error'}"

    return {
        "success": len(sent_records) > 0,
        "total_sent": len(sent_records),
        "total_invoices_covered": total_invoices_covered,
        "total_failed": len(failed_records),
        "skipped_without_email_count": len(skipped_without_email),
        "skipped_without_email_ids": skipped_ids,
        "sent_records": sent_records,
        "failed_records": failed_records,
        "message": msg
    }


# ---------------------------------------------------------------------------
# 21. Customer Promotional Marketing Emails
# ---------------------------------------------------------------------------

def send_customer_marketing_email(user, subject: str = "", message: str = ""):
    """
    Send promotional, special offer, or announcement emails to previous customers who have purchased before.
    Uses custom FlezPay email templates.
    
    Args:
        user: UserSecure merchant instance.
        subject: Email subject line.
        message: The promotional announcement or offer details.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags

    biz = models.BusinessDetails.objects.filter(user=user).first()
    business_name = biz.business_name if (biz and biz.business_name) else "Our Store"

    effective_subject = str(subject).strip() if subject and str(subject).strip() else f"A Special Offer Just For You — {business_name}"
    
    if message and str(message).strip():
        effective_message = str(message).strip()
    else:
        effective_message = f"Thank you for being a valued customer of {business_name}! We appreciate your continued support and look forward to serving you again."

    invoices = UserInvoices.objects.filter(
        user_id=user,
        invoice_status='completed',
        customer_email__isnull=False
    ).exclude(customer_email='').order_by('-timestamp')

    customer_dict = {}
    for inv in invoices:
        email = inv.customer_email.strip().lower()
        if email and email not in customer_dict:
            customer_dict[email] = {
                "name": inv.customer_name or "Valued Customer",
                "email": inv.customer_email.strip()
            }

    # Fallback: if no completed invoices with email exist, check all customer invoices with email
    if not customer_dict:
        fallback_invoices = UserInvoices.objects.filter(
            user_id=user,
            customer_email__isnull=False
        ).exclude(customer_email='').order_by('-timestamp')
        for inv in fallback_invoices:
            email = inv.customer_email.strip().lower()
            if email and email not in customer_dict:
                customer_dict[email] = {
                    "name": inv.customer_name or "Valued Customer",
                    "email": inv.customer_email.strip()
                }

    if not customer_dict:
        return {
            "success": False,
            "total_sent": 0,
            "message": "No previous customers with valid email addresses found in your sales history."
        }

    sent_count = 0
    failed_count = 0
    recipients_preview = []

    for email, cust in customer_dict.items():
        cust_name = cust["name"]
        context = {
            "customer_name": cust_name,
            "business_name": business_name,
            "subject": effective_subject,
            "message": effective_message,
            "offer_code": "",
            "user_email": cust["email"],
        }

        try:
            html_content = render_to_string('emails/customer_marketing.html', context)
            text_content = strip_tags(html_content)

            msg = EmailMultiAlternatives(
                subject=effective_subject,
                body=text_content,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@flezpay.com'),
                to=[cust["email"]]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            sent_count += 1
            if len(recipients_preview) < 15:
                recipients_preview.append({"name": cust_name, "email": cust["email"]})
        except Exception:
            failed_count += 1

    return {
        "success": sent_count > 0,
        "total_sent": sent_count,
        "total_failed": failed_count,
        "recipients_preview": recipients_preview,
        "message": f"Successfully dispatched custom promotional emails directly to {sent_count} previous customer(s)."
    }


# ---------------------------------------------------------------------------
# 22. Outstanding Monthly Taxes & VAT Calculation
# ---------------------------------------------------------------------------

def get_outstanding_taxes(user, month=None, year=None):
    """
    Calculate outstanding monthly VAT/taxes to file based on completed invoices and user's VAT settings.
    If the business VAT percentage is not configured (0%), prompts the user to configure their VAT in Settings.
    
    Args:
        user: UserSecure merchant instance.
        month: Optional specific month (1-12) to calculate. If omitted, provides year-to-date monthly breakdown.
        year: Optional specific year (e.g. 2026). Defaults to current year.
    """
    today = now()
    target_year = int(year) if year else today.year

    biz = models.BusinessDetails.objects.filter(user=user).first()
    vat_pct = float(biz.vat_percentage) if (biz and biz.vat_percentage is not None) else 0.0
    business_name = biz.business_name if (biz and biz.business_name) else "Business"

    if vat_pct <= 0:
        return {
            "vat_configured": False,
            "vat_percentage": 0.0,
            "business_name": business_name,
            "message": "Your business VAT percentage is currently set to 0% or not configured. To calculate accurate monthly taxes to file, please configure your VAT percentage in Store Settings (Settings > Business Details), or provide your VAT rate (e.g. 7.5% standard VAT in Nigeria).",
            "action_required": "Please configure your VAT percentage in Store Settings to file monthly returns.",
            "settings_url": "/settings"
        }

    # Fetch completed invoice items for target year
    start_of_year = make_aware(datetime(target_year, 1, 1))
    end_of_year = make_aware(datetime(target_year, 12, 31, 23, 59, 59, 999999))

    invoice_items = UserInvoiceItems.objects.filter(
        user__user_id=user,
        user__invoice_status='completed',
        timestamp__range=[start_of_year, end_of_year]
    ).annotate(
        line_total=ExpressionWrapper(F('item_quantity') * F('item_amount'), output_field=DecimalField())
    )

    monthly_sales = defaultdict(Decimal)
    monthly_counts = defaultdict(int)

    for itm in invoice_items:
        m = itm.timestamp.month
        monthly_sales[m] += itm.line_total or Decimal('0.0')

    invoices = UserInvoices.objects.filter(
        user_id=user,
        invoice_status='completed',
        timestamp__range=[start_of_year, end_of_year]
    )
    for inv in invoices:
        monthly_counts[inv.timestamp.month] += 1

    monthly_filings = []
    total_taxable_sales_ytd = Decimal('0.0')
    total_vat_payable_ytd = Decimal('0.0')

    months_to_process = [int(month)] if month else range(1, 13)

    for m in months_to_process:
        sales = monthly_sales[m]
        count = monthly_counts[m]
        # Only skip future months with 0 sales when viewing full year
        if not month and m > today.month and sales == 0:
            continue

        vat_due = round(float(sales) * (vat_pct / 100.0), 2)
        total_taxable_sales_ytd += sales
        total_vat_payable_ytd += Decimal(str(vat_due))

        monthly_filings.append({
            "month_number": m,
            "month_name": MONTH_NAMES[m],
            "year": target_year,
            "completed_invoices_count": count,
            "gross_taxable_sales": _round(sales),
            "vat_rate_percentage": vat_pct,
            "outstanding_vat_to_file": vat_due,
            "filing_status": "Due for filing" if vat_due > 0 else "No tax activity"
        })

    return {
        "vat_configured": True,
        "vat_percentage": vat_pct,
        "business_name": business_name,
        "year": target_year,
        "filter_month": MONTH_NAMES[int(month)] if month else "All Months (YTD)",
        "total_taxable_sales_ytd": _round(total_taxable_sales_ytd),
        "total_vat_payable_ytd": _round(total_vat_payable_ytd),
        "monthly_filings": monthly_filings,
        "instructions": f"Based on your configured {vat_pct}% VAT rate, your total VAT payable for tax filing is ₦{float(total_vat_payable_ytd):,.2f}."
    }


# ---------------------------------------------------------------------------
# Aggregator — single entry point for AI context
# ---------------------------------------------------------------------------

def build_ai_performance_data(user, month=None, year=None):
    """
    Build a comprehensive performance data dict for the AI chat context.
    This is the single entry point called from AIChatView.
    When month/year are provided, all period-scoped data is loaded for that month.
    """
    # Determine the queried period label
    today = now()
    req_month = int(month) if month else today.month
    req_year = int(year) if year else today.year
    is_current = (req_month == today.month and req_year == today.year)
    period_label = f"{MONTH_NAMES[req_month]} {req_year}"

    data = {
        "queried_period": period_label,
        "is_current_month": is_current,
        "summary": get_business_summary(user, month, year),
        "revenue_projections": get_revenue_projections(user, month, year),
        "invoice_summary": get_invoice_summary(user, month, year),
        "recent_invoices": get_invoices_with_staff(user, month, year, limit=10),
        "best_performing_items": get_best_performing_items(user, month, year, limit=10),
        "best_performing_by_department": get_best_performing_items(user, month, year, by_department=True, limit=5),
        "worst_performing_items": get_worst_performing_items(user, month, year, limit=10),
        "inventory_items": get_inventory_items(user, limit=10),
        "sales_trend": get_sales_trend(user, month, year),
        "daily_sales_breakdown": get_daily_sales_breakdown(user, month, year),
        "quick_date_ranges": get_date_range_sales(user),
        "department_performance": get_department_performance(user, month, year),
        "payroll_summary": get_payroll_summary(user),
        "alerts": get_business_alerts(user),
        "overdue_invoices": get_overdue_invoices(user, limit=10),
        "debt_summary": get_debt_summary(user),
        "monthly_overview": get_monthly_overview(user),
        "tax_summary": get_outstanding_taxes(user, month, year),
    }
    return data


