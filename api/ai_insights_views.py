"""
AI Insights Views
=================
Dedicated API endpoints for the Smart AI Insights tab on the Business Analytics page.

GET  /api/business/ai-insights/       → Cached structured insights (summary, opportunities, recommendations)
POST /api/business/ai-insights/ask/   → One-shot streaming Q&A using merchant business context
"""

import json
import os
import logging

from django.core.cache import cache
from django.http import StreamingHttpResponse
from django.utils.timezone import now

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from api.onboarding.authenticate import UnsafeSessionAuthentication

from api import models
from api.functions.ai_business_tools import build_ai_performance_data, get_business_summary
from api.functions.ai_chat import AIChatHandler

logger = logging.getLogger(__name__)

# Default cache TTL: 4 hours
AI_INSIGHTS_CACHE_TTL = int(os.environ.get('AI_INSIGHTS_CACHE_TTL', 14400))

# Ollama model (inherits from environment, same as AIChatView)
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'gemma4:latest')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_business_owner(user):
    """Resolve the business owner, same pattern as AIChatView."""
    if hasattr(user, 'user_type') and user.user_type in ['manager', 'staff']:
        if getattr(user, 'business_owner', None):
            return user.business_owner
        try:
            manager_record = models.UserManagers.objects.filter(
                manager_email__iexact=user.user_email
            ).first()
            if manager_record and manager_record.user:
                return manager_record.user
        except Exception:
            pass
    return user


def _cache_key(user):
    period = now().strftime('%Y-%m')
    return f"ai_insights:{user.pk}:{period}"


def _build_insights_prompt(data_summary: str, currency: str) -> str:
    """
    Build a structured prompt that instructs the LLM to output a strict JSON object.
    Financial metrics are pre-calculated — we only ask the LLM to interpret and frame them.
    """
    return f"""You are a senior business intelligence analyst for FlezPay merchants.
Your role is to interpret the merchant's real business data and generate actionable insights.

RULES — CRITICAL:
- You MUST return ONLY a single valid JSON object. No markdown, no explanation, no code fences.
- Every insight MUST be grounded in the data provided. Do NOT invent numbers, products, or events.
- If a metric is zero or data is missing, say so honestly — do not fabricate interpretations.
- Use the merchant's actual currency: {currency}
- Keep language clear, professional, and actionable. Write for a busy business owner.

OUTPUT FORMAT (return this exact structure):
{{
  "summary": "2-4 sentence executive summary of what is happening in the business right now.",
  "opportunities": [
    {{
      "title": "Short opportunity title",
      "description": "1-2 sentence explanation grounded in the data.",
      "metric": "A specific supporting figure from the data (e.g. '18% MoM revenue growth').",
      "priority": "high_impact|opportunity|watch|positive",
      "action": "Specific recommended action."
    }}
  ],
  "recommendations": [
    {{
      "title": "Recommendation title",
      "description": "What the merchant should do and why.",
      "cta_label": "Action button label (e.g. Create Campaign, View Inventory, Review Pricing)",
      "cta_type": "create_campaign|view_inventory|review_pricing|view_invoices|none"
    }}
  ],
  "data_quality": "sufficient|limited|insufficient"
}}

Generate 2-4 opportunities and 2-4 recommendations based strictly on this business data:

{data_summary}

Return ONLY the JSON object now."""


def _call_ollama_structured(prompt: str) -> dict:
    """
    Call Ollama synchronously and parse the JSON response.
    Returns the parsed dict, or raises an exception on failure.
    """
    import ollama
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        options={"num_ctx": 8192, "num_predict": 2048, "temperature": 0.3}
    )
    msg = response.get("message", {}) if isinstance(response, dict) else getattr(response, 'message', None)
    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, 'content', '')

    # Strip markdown code fences if model wrapped the JSON
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        # Remove first and last fence lines
        lines = [l for l in lines if not l.startswith("```")]
        content = "\n".join(lines).strip()

    return json.loads(content)


def _generate_fallback_insights(summary: dict, performance_data: dict, currency: str) -> dict:
    """
    Generate grounded, high-quality business insights deterministically from performance data
    if the external LLM call is temporarily unavailable or times out.
    """
    sales_this_month = summary.get('sales_this_month', 0)
    rev_proj = performance_data.get('revenue_projections', {})
    mom_pct = rev_proj.get('month_over_month_change_pct', 0)
    alerts = performance_data.get('alerts', [])
    best = performance_data.get('best_performing_items', [])
    completed_count = summary.get('completed_count', 0)
    total_products = summary.get('total_products', 0)

    # Executive Summary
    if sales_this_month > 0:
        summary_text = (
            f"Your business has generated {currency}{sales_this_month:,.2f} this month across {completed_count} completed orders. "
            f"Month-over-month revenue is trending {'up' if mom_pct >= 0 else 'down'} by {abs(mom_pct):.1f}%. "
            f"With {total_products} active product(s) in your catalog, key focus areas include scaling top performers and maintaining healthy stock."
        )
    else:
        summary_text = (
            f"Your store currently has {total_products} products ready for sale. "
            f"Customer activity is steady with {completed_count} lifetime order(s). "
            f"Launching promotional campaigns and sharing direct store links will help accelerate early sales momentum."
        )

    # Opportunities
    opps = []
    if best:
        top_item = best[0]
        opps.append({
            "title": f"Top Revenue Driver: {top_item.get('item', 'Best Seller')}",
            "description": f"{top_item.get('item')} is generating the highest volume in recent sales. Expanding promotion can drive higher conversions.",
            "metric": f"{currency}{top_item.get('total_sales', 0):,.2f} sales ({top_item.get('units_sold', 0)} units)",
            "priority": "high_impact",
            "action": f"Feature {top_item.get('item')} on your primary social marketing and ad campaigns."
        })

    if mom_pct > 0:
        opps.append({
            "title": "Positive Growth Trajectory",
            "description": "Your revenue trajectory is positive compared to the previous period. Maintaining product availability will protect this momentum.",
            "metric": f"+{mom_pct:.1f}% MoM revenue growth",
            "priority": "positive",
            "action": "Increase visibility on your highest margin products while customer interest is peak."
        })
    elif mom_pct < 0:
        opps.append({
            "title": "Revenue Pace Recovery",
            "description": f"Monthly revenue is {abs(mom_pct):.1f}% behind last month's pace. Re-engaging past customers can restore sales velocity.",
            "metric": f"{mom_pct:.1f}% MoM change",
            "priority": "opportunity",
            "action": "Run a limited-time discount or customer appreciation offer."
        })

    if alerts:
        first_alert = alerts[0]
        opps.append({
            "title": first_alert.get('title', 'Inventory Alert'),
            "description": first_alert.get('message', 'Some items require inventory attention to prevent stockouts.'),
            "metric": f"{len(alerts)} alert(s) flagged",
            "priority": "watch",
            "action": "Review inventory levels in product management."
        })

    if len(opps) == 0:
        opps.append({
            "title": "Expand Product Assortment",
            "description": "Adding complimentary items to your catalog will help increase average order value per transaction.",
            "metric": f"{total_products} catalog item(s)",
            "priority": "opportunity",
            "action": "Add fresh items to your store inventory."
        })

    # Recommendations
    recs = [
        {
            "title": "Launch a Targeted Growth Campaign",
            "description": "Reach potential buyers near your business by running a Meta Ads promotion linked to your top products.",
            "cta_label": "Create Campaign",
            "cta_type": "create_campaign"
        },
        {
            "title": "Review Inventory & Product Stock",
            "description": "Ensure best-selling items remain in stock to avoid lost sales and fulfillment delays.",
            "cta_label": "View Products",
            "cta_type": "view_inventory"
        }
    ]

    return {
        "summary": summary_text,
        "opportunities": opps[:4],
        "recommendations": recs[:4],
        "data_quality": "sufficient" if sales_this_month > 0 else "limited"
    }


# ---------------------------------------------------------------------------
# View 1: Cached / Background Insights (GET & POST)
# ---------------------------------------------------------------------------

class AIInsightsView(APIView):
    """
    GET /api/business/ai-insights/
    Returns structured AI-generated insights for the merchant's business.
    Results are cached in Redis for AI_INSIGHTS_CACHE_TTL seconds.

    If not cached or ?refresh=true, dispatches an asynchronous Celery task
    to generate the insights in the background (identical to the Campaign AI Creator),
    returning {'status': True, 'generating': True, 'task_id': task_id}.

    POST /api/business/ai-insights/
    Directly starts a new background generation task.
    """
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        business_user = _get_business_owner(user)
        force_refresh = request.query_params.get('refresh', '').lower() == 'true'
        key = _cache_key(business_user)

        # --- Try cache first if not refreshing ---
        if not force_refresh:
            cached = cache.get(key)
            if cached:
                cached['from_cache'] = True
                return Response({'status': True, 'data': cached})

        # --- Dispatch Background Celery Task ---
        import uuid
        task_id = str(uuid.uuid4())
        from api.tasks import generate_ai_insights_task
        generate_ai_insights_task.delay(business_user.id, task_id)

        return Response({
            'status': True,
            'generating': True,
            'task_id': task_id,
            'message': 'Smart AI Insights generation started in the background.'
        }, status=status.HTTP_202_ACCEPTED)

    def post(self, request):
        user = request.user
        business_user = _get_business_owner(user)
        import uuid
        task_id = str(uuid.uuid4())
        from api.tasks import generate_ai_insights_task
        generate_ai_insights_task.delay(business_user.id, task_id)

        return Response({
            'status': True,
            'success': True,
            'generating': True,
            'task_id': task_id,
            'message': 'Smart AI Insights generation started in the background.'
        }, status=status.HTTP_202_ACCEPTED)


class AIInsightsStatusView(APIView):
    """
    GET /api/business/ai-insights/status/<str:task_id>/
    Polls status of an ongoing Smart AI Insights generation task.
    Returns:
      {'status': 'pending'}
      {'status': 'completed', 'data': {...}}
      {'status': 'failed', 'error': '...'}
    """
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        result = cache.get(f"ai_insights_task_{task_id}")
        if result is None:
            return Response({'status': 'pending'})

        if isinstance(result, dict) and 'error' in result and len(result) == 1:
            return Response({'status': 'failed', 'error': result['error']})

        return Response({'status': 'completed', 'data': result})


def _build_metrics_snapshot(summary: dict, performance_data: dict) -> dict:
    """
    Build a clean metrics snapshot for the UI header strip and operational gauge.
    All values are calculated in Python — never derived by the LLM.
    """
    rev = performance_data.get('revenue_projections', {})
    alerts = performance_data.get('alerts', [])
    best = performance_data.get('best_performing_items', [])
    opportunities_count = len(best) + len(alerts)

    mom_change = rev.get('month_over_month_change_pct', 0)
    sales_this_month = summary.get('sales_this_month', 0)
    total_products = summary.get('total_products', 0)

    # -----------------------------------------------------------------------
    # Dynamic Store Operational Health Score Algorithm (0 - 100 scale)
    # Starts from a base of 100, evaluates real operational indicators:
    # inventory health, overdue invoices, margin integrity, and sales momentum.
    # -----------------------------------------------------------------------
    health_score = 100
    deductions = 0
    bonuses = 0
    health_factors = []

    # 1. Inventory & Catalog Operations
    if total_products == 0:
        deductions += 35
        health_factors.append("No active products in catalog")
    else:
        out_of_stock = [a for a in alerts if a.get('type') == 'out_of_stock']
        low_stock = [a for a in alerts if a.get('type') == 'low_stock']
        expiring = [a for a in alerts if a.get('type') == 'expiring_soon']
        neg_margin = [a for a in alerts if a.get('type') == 'negative_margin']

        if out_of_stock:
            ded = min(len(out_of_stock) * 8, 24)
            deductions += ded
            health_factors.append(f"{len(out_of_stock)} item(s) out of stock")
        if low_stock:
            ded = min(len(low_stock) * 3, 12)
            deductions += ded
            health_factors.append(f"{len(low_stock)} item(s) running low on stock")
        if expiring:
            ded = min(len(expiring) * 4, 12)
            deductions += ded
            health_factors.append(f"{len(expiring)} item(s) expiring soon")
        if neg_margin:
            ded = min(len(neg_margin) * 8, 16)
            deductions += ded
            health_factors.append("Product(s) selling below cost")

    # 2. Financial & Invoicing Health
    overdue_invoices = [a for a in alerts if a.get('type') == 'overdue_invoices']
    if overdue_invoices:
        ded = min(len(overdue_invoices) * 12, 24)
        deductions += ded
        health_factors.append(f"{len(overdue_invoices)} overdue unpaid invoice(s)")

    # 3. Revenue & Business Momentum
    if mom_change < -20:
        ded = 15
        deductions += ded
        health_factors.append("Significant MoM revenue drop")
    elif mom_change < 0:
        ded = 8
        deductions += ded
        health_factors.append("Slight MoM revenue decline")
    elif mom_change > 15:
        bonuses += 5
        health_factors.append("Strong positive sales momentum")
    elif mom_change > 0:
        bonuses += 2

    if sales_this_month > 0:
        bonuses += 5
        health_factors.append("Active customer revenue this month")

    # Final score clamping and classification
    raw_score = health_score - deductions + bonuses
    final_score = max(15, min(raw_score, 98 if deductions > 0 else 100))

    if final_score >= 80:
        health_status = 'Optimal'
        health_color = 'emerald'
    elif final_score >= 65:
        health_status = 'Good'
        health_color = 'teal'
    elif final_score >= 50:
        health_status = 'Fair'
        health_color = 'amber'
    else:
        health_status = 'Needs Attention'
        health_color = 'rose'

    active_alerts_count = len([a for a in alerts if a.get('severity') in ('critical', 'warning')])

    return {
        'currency': summary.get('currency', '₦'),
        'sales_this_month': sales_this_month,
        'last_month_total': rev.get('last_month_total', 0),
        'mom_change_pct': round(mom_change, 1),
        'total_products': total_products,
        'active_alerts': active_alerts_count,
        'top_product': best[0]['item'] if best else None,
        'top_product_revenue': best[0]['total_sales'] if best else 0,
        'operational_health_score': int(final_score),
        'health_status': health_status,
        'health_color': health_color,
        'health_factors': health_factors[:3],
    }


# ---------------------------------------------------------------------------
# View 2: AI Business Manager Q&A (POST, streaming)
# ---------------------------------------------------------------------------

class AIInsightsAskView(APIView):
    """
    POST /api/business/ai-insights/ask/
    One-shot streaming Q&A using the merchant's analytics context.
    
    Body: { "message": "Why did my revenue drop this month?" }
    Response: plain text stream
    """
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        business_user = _get_business_owner(user)

        message = request.data.get('message', '').strip()
        if not message:
            return Response(
                {'status': False, 'message': 'No message provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            performance_data = build_ai_performance_data(business_user)
            summary = get_business_summary(business_user)
            currency = summary.get('currency', '₦')
        except Exception as e:
            logger.error(f"AIInsightsAskView: failed to build context: {e}")
            return Response(
                {'status': False, 'message': 'Could not load business data.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        handler = AIChatHandler(
            performance_data=performance_data,
            user=business_user,
            currency=currency
        )

        user_context = {
            'business_name': summary.get('business_name', 'Merchant'),
            'currency': currency,
            'monthly_sales': summary.get('sales_this_month', 0),
        }

        messages = [{'role': 'user', 'content': message}]

        import asyncio
        from asgiref.sync import sync_to_async

        async def stream_response():
            try:
                async for chunk in handler.chat_stream_async(messages, user_context=user_context):
                    # Strip the <think> wrapper — insights Q&A should stream clean text only
                    if chunk in ('<think>\n', '\n</think>\n\n'):
                        continue
                    if 'Evaluating' in chunk or 'Analyzing' in chunk or 'Reviewing' in chunk or \
                       'Structuring' in chunk or 'Finalizing' in chunk or 'Fetching' in chunk or \
                       'Still processing' in chunk or 'Formatting' in chunk or \
                       chunk.startswith('<!--') or 'heartbeat' in chunk:
                        continue
                    yield chunk
            except Exception as e:
                yield f"I'm unable to answer that right now. Please try again. ({e})"

        response = StreamingHttpResponse(stream_response(), content_type='text/plain')
        response['X-Accel-Buffering'] = 'no'
        return response
