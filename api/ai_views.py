import json
import re
from datetime import datetime

from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from api.functions import ai_chat
from api.functions.ai_business_tools import build_ai_performance_data, get_business_summary
from asgiref.sync import sync_to_async

from api.user_data.serializer import UserAIChatSerializer
from api import models


MONTH_MAP = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}


def _extract_date_intent(messages):
    """
    Scan the last few user messages for month/year references.
    Returns (month: int|None, year: int|None).
    Supports patterns like:
      - "January", "jan", "february 2025"
      - "last month", "2 months ago", "3 months back"
      - "this month"
      - "2025-03", "03/2025"
    """
    # Collect recent user messages (check last 3 for context)
    user_texts = []
    for msg in reversed(messages):
        if msg.get('role') == 'user':
            user_texts.append(msg.get('content', ''))
            if len(user_texts) >= 3:
                break
    if not user_texts:
        return None, None

    combined = ' '.join(user_texts).lower()
    now = datetime.now()

    # Pattern 1: Explicit month name + optional year
    # e.g. "january 2025", "jan this year", "sales in march", "february last year"
    month_names = '|'.join(MONTH_MAP.keys())
    match = re.search(
        rf'\b({month_names})\s*(?:of\s+)?(?:(\d{{4}})|(?:(this|last|previous)\s+year))?',
        combined
    )
    if match:
        month = MONTH_MAP[match.group(1)]
        if match.group(2):
            year = int(match.group(2))
        elif match.group(3) in ('last', 'previous'):
            year = now.year - 1
        else:
            year = now.year
        return month, year

    # Pattern 2: "last month", "2 months ago", "3 months back"
    match = re.search(r'(\d+)\s+months?\s+(?:ago|back)', combined)
    if match:
        months_back = int(match.group(1))
        target_month = now.month - months_back
        target_year = now.year
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        return target_month, target_year

    if re.search(r'\blast\s+month\b', combined):
        target_month = now.month - 1
        target_year = now.year
        if target_month <= 0:
            target_month += 12
            target_year -= 1
        return target_month, target_year

    # Pattern 3: ISO-style "2025-03" or "03/2025"
    match = re.search(r'(\d{4})[-/](\d{1,2})', combined)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            return month, year

    match = re.search(r'(\d{1,2})[-/](\d{4})', combined)
    if match:
        month = int(match.group(1))
        year = int(match.group(2))
        if 1 <= month <= 12:
            return month, year

    return None, None


class AIChatView(APIView):
    """
    Industry-grade streaming AI chat endpoint powered by Ollama.
    Supports chat history persistence and live business data context.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_business_owner(self, user):
        """Resolve the business owner for manager/staff users."""
        if hasattr(user, 'user_type') and user.user_type in ['manager', 'staff']:
            if getattr(user, 'business_owner', None):
                return user.business_owner
            # Fallback: resolve via UserManagers
            try:
                manager_record = models.UserManagers.objects.filter(
                    manager_email__iexact=user.user_email
                ).first()
                if manager_record and manager_record.user:
                    return manager_record.user
            except Exception:
                pass
        return user

    def get(self, request):
        try:
            user = request.user
            business_user = self._get_business_owner(user)
            
            try:
                from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
                SubscriptionManager(business_user).require_ai_manager()
            except SubscriptionLimitError as e:
                return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
                
            session_id = request.query_params.get('session_id')
            get_sessions = request.query_params.get('sessions') == 'true'
            
            if get_sessions:
                chats = models.UserAIChat.objects.filter(user=business_user, session_id__isnull=False).order_by('-timestamp')
                sessions_map = {}
                for chat in chats:
                    if chat.session_id not in sessions_map:
                        preview_content = chat.content.strip()
                        preview_content = re.sub(r'<think>.*?</think>', '', preview_content, flags=re.DOTALL).strip()
                        preview_content = preview_content.split('\n')[0]
                        if len(preview_content) > 40:
                            preview_content = preview_content[:37] + '...'
                            
                        sessions_map[chat.session_id] = {
                            'session_id': chat.session_id,
                            'preview': preview_content,
                            'timestamp': chat.timestamp.isoformat()
                        }
                return Response({'status': True, 'data': list(sessions_map.values())})
            
            # Chat history is shared across the business but scoped by session
            chats = models.UserAIChat.objects.filter(user=business_user)
            if session_id:
                chats = chats.filter(session_id=session_id)
            chats = chats.order_by('timestamp')
            
            serializer = UserAIChatSerializer(chats, many=True)
            return Response({'status': True, 'data': serializer.data})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
            user = request.user
            # Resolve business owner to fetch the correct business data context and chat history
            business_user = self._get_business_owner(user)
            
            try:
                from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
                SubscriptionManager(business_user).require_ai_manager()
            except SubscriptionLimitError as e:
                return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

            messages = request.data.get('messages', [])
            session_id = request.data.get('session_id')
            if not messages:
                return Response({'status': False, 'message': "No messages provided"}, status=status.HTTP_400_BAD_REQUEST)

            # Save the last user message to history (stored under the business owner)
            last_message = messages[-1]
            if last_message.get('role') == 'user':
                models.UserAIChat.objects.create(
                    user=business_user,
                    session_id=session_id,
                    role='user',
                    content=last_message.get('content')
                )

            if user.is_anonymous:
                user_context = {
                    "business_name": "Valued Merchant",
                    "current_balance": 0.0,
                    "monthly_sales": 0.0,
                    "best_performing_item": "N/A"
                }
                performance_data = {}
            else:
                # Build comprehensive live business data using the owner's account
                summary = get_business_summary(business_user)
                user_context = {
                    "business_name": summary["business_name"],
                    "currency": summary["currency"],
                    "current_balance": summary["current_balance"],
                    "monthly_sales": summary["sales_this_month"],
                    "projected_revenue": summary["projected_monthly_revenue"],
                    "total_staff": summary["total_staff"],
                    "total_managers": summary["total_managers"],
                    "total_products": summary["total_products"],
                    "total_inventory_value": summary["total_inventory_value"],
                    "pending_invoices": summary["pending_count"],
                    "overdue_invoices": summary["overdue_count"],
                    "total_outstanding": summary["total_outstanding"],
                }
                # Extract date intent from user messages for historical queries
                req_month, req_year = _extract_date_intent(messages)
                performance_data = build_ai_performance_data(business_user, month=req_month, year=req_year)

            handler = ai_chat.AIChatHandler(
                performance_data=performance_data,
                user=business_user if not user.is_anonymous else None,
                currency=user_context.get("currency", "Naira (₦)")
            )

            import time
            async def wrapped_stream():
                full_content = ""
                start_time = time.time()
                first_yield_time = None
                try:
                    async for chunk in handler.chat_stream_async(messages, user_context=user_context):
                        if first_yield_time is None and '</think>' in chunk:
                            first_yield_time = time.time()
                        full_content += chunk
                        yield chunk
                finally:
                    # After stream finishes or is interrupted, save the assistant's response
                    if full_content:
                        if first_yield_time:
                            thought_seconds = first_yield_time - start_time
                            full_content += f"\n<!-- THOUGHT_TIME: {thought_seconds:.1f} -->"
                        
                        await sync_to_async(models.UserAIChat.objects.create)(
                            user=business_user,
                            session_id=session_id,
                            role='assistant',
                            content=full_content
                        )

            response = StreamingHttpResponse(wrapped_stream(), content_type='text/plain')
            response['X-Accel-Buffering'] = 'no'
            return response

        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
