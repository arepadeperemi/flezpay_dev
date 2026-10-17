import json
import os
import re
from typing import Dict, Any, Optional

import ollama
from django.db.models import Sum

from api.models import (
    BusinessDetails,
    UserItems,
    UserInvoices,
    UserTransactions,
    SiteSettings
)
from api.functions.ai_business_tools import get_business_summary, build_ai_performance_data, get_best_performing_items

class AIPromotionService:
    def __init__(self, user):
        self.user = user
        self.model_name = os.environ.get('OLLAMA_MODEL', 'gemma4:latest')

    def collect_business_context(self) -> Dict[str, Any]:
        """
        Gathers business context for the user, including business details, 
        top products, and some basic sales metrics.
        """
        # 1. Business Info
        business = BusinessDetails.objects.filter(user=self.user).first()
        business_name = business.business_name if business and business.business_name else f"{self.user.first_name}'s Business"
        business_type = business.business_type if business and business.business_type else "Retail"
        
        # 2. Products
        # Fetch best performing items first, fallback to newest
        best_items = get_best_performing_items(self.user, limit=10)
        product_catalog = []
        added_item_ids = set()
        
        if best_items:
            for b_item in best_items:
                item_obj = UserItems.objects.filter(user=self.user, item_name=b_item['item']).first()
                if item_obj and item_obj.item_id not in added_item_ids:
                    product_catalog.append({
                        "id": str(item_obj.item_id),
                        "name": item_obj.item_name,
                        "price": str(item_obj.item_amount) if item_obj.item_amount else "0",
                        "description": item_obj.item_description or "",
                        "performance": f"Top Seller ({b_item['units_sold']} sold recently)"
                    })
                    added_item_ids.add(item_obj.item_id)
                    
        # Fill remaining slots with newest items if we have less than 10
        if len(product_catalog) < 10:
            recent_items = UserItems.objects.filter(user=self.user).exclude(item_id__in=added_item_ids).order_by('-id')[:10 - len(product_catalog)]
            for item in recent_items:
                product_catalog.append({
                    "id": str(item.item_id),
                    "name": item.item_name,
                    "price": str(item.item_amount) if item.item_amount else "0",
                    "description": item.item_description or "",
                    "performance": "New/Regular Item"
                })
            
        # 3. Basic Sales Data
        total_sales = UserInvoices.objects.filter(user_id=self.user, invoice_status='paid').count()
        
        # 4. Deep Business Insights (like AI Chat)
        summary = get_business_summary(self.user)
        performance_data = build_ai_performance_data(self.user)
        
        return {
            "business_name": business_name,
            "business_type": business_type,
            "product_catalog": product_catalog,
            "total_sales": total_sales,
            "summary": summary,
            "performance_data": performance_data
        }

    def generate_promotion_plan(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses Ollama to generate a complete promotion plan in JSON format based on business context and optional user preferences.
        """
        context = self.collect_business_context()
        
        # Filter performance data to prevent context window overflow
        perf_data = context.get('performance_data', {})
        filtered_perf = {
            "monthly": perf_data.get("monthly_summary"),
            "ytd": perf_data.get("year_to_date")
        }
        
        # Build prompt
        prompt = (
            f"You are an expert AI marketing assistant for a small business named '{context['business_name']}' "
            f"operating in the '{context['business_type']}' sector. They have {context['total_sales']} recent sales.\n"
            f"Here is a deep summary of their business: {json.dumps(context['summary'], default=str)}\n"
            f"Here is their recent performance data: {json.dumps(filtered_perf, default=str)}\n"
        )
        
        if context["product_catalog"]:
            prompt += "Here are some of their products:\n"
            for p in context["product_catalog"]:
                prompt += f"- ID: {p['id']}, Name: {p['name']} (Price: {p['price']}). Performance: {p.get('performance', 'Unknown')}. Description: {p['description']}\n"
        else:
            prompt += "The business currently has no products listed.\n"

        prompt += "\nThe user wants to create a promotion. They have provided the following optional preferences:\n"
        
        promote_pref = preferences.get('promote', 'Let AI choose')
        goal_pref = preferences.get('goal', 'Let AI choose')
        style_pref = preferences.get('style', 'Friendly')
        
        prompt += f"- What to promote: {promote_pref}\n"
        prompt += f"- Goal of promotion: {goal_pref}\n"
        prompt += f"- Tone/Style: {style_pref}\n\n"
        
        # Strictly enforce user preferences
        if promote_pref == "My whole store":
            prompt += "CRITICAL: The user explicitly wants to promote the ENTIRE STORE. DO NOT promote a specific product. Set `suggested_product_id` to null and `promote_type` to 'store'.\n"
        elif promote_pref == "A sale":
            prompt += "CRITICAL: The user explicitly wants to promote a general SALE/DISCOUNT. Focus the copy on discounts. Set `promote_type` to 'discount'.\n"
        elif promote_pref == "A product":
            prompt += "CRITICAL: The user explicitly wants to promote a SINGLE PRODUCT. You MUST select one product from the catalog, and set `suggested_product_id` to its ID. Set `promote_type` to 'product'.\n"

        if goal_pref == "Get more sales":
            prompt += "CRITICAL: The goal is to drive immediate sales. Set `action_type` to 'buy'.\n"
        elif goal_pref == "Get more visitors":
            prompt += "CRITICAL: The goal is to drive foot traffic or website visits. Set `action_type` to 'visit'.\n"
        elif goal_pref == "Receive more messages":
            prompt += "CRITICAL: The goal is to encourage customer inquiries. Set `action_type` to 'message'.\n"
        else:
            prompt += "CRITICAL: The user wants YOU to choose the goal. Analyze the business context and pick the most logical goal. Set `action_type` to ONE of 'buy', 'visit', or 'message'. Do not always default to 'buy' - vary your choices based on what the business actually needs right now.\n"
        
        prompt += "\n"

        from api.growth_views import get_usd_to_local_exchange_rate
        from api.models import UserDetails
        user_details = UserDetails.objects.filter(user=self.user).first()
        currency = user_details.currency if user_details and user_details.currency else 'NGN'
        usd_rate = get_usd_to_local_exchange_rate(currency)
        min_budget = int(1 * usd_rate)
        max_budget = int(500 * usd_rate)
        
        prompt += (
            "Based on this, generate a complete promotional campaign. "
            "CRITICAL: When writing the headline and message for a specific product, YOU MUST explicitly take the product's actual NAME into account, not just its description. Ensure the copy logically matches what the product is. "
            "Respond ONLY with a valid JSON object. Do not include markdown fences, comments, or explanations.\n"
            "The JSON object must have exactly these keys and types:\n"
            "- suggested_product_id (string UUID or null)\n"
            "- promote_type (string, one of: product, store, discount, new)\n"
            "- action_type (string, one of: buy, visit, message)\n"
            "- audience_type (string, one of: near, past, similar)\n"
            f"- daily_budget (integer between {min_budget} and {max_budget})\n"
            "- duration_days (integer between 3 and 14)\n"
            "- headline (string, max 10 words)\n"
            "- message (string, 2-3 sentences)\n"
            "- insight (string, 1-sentence explanation)\n"
        )
        
        response = ollama.chat(
            model=self.model_name,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.7, 'num_ctx': 8192}
        )
        
        raw = response['message']['content'].strip()
        
        # Strip any <think>...</think> blocks from models that output reasoning
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        
        raw = re.sub(r'^```json', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'```$', '', raw)
        raw = raw.strip()

        try:
            try:
                plan = json.loads(raw)
            except json.JSONDecodeError:
                # Try to extract JSON if there's surrounding text
                json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                if json_match:
                    plan = json.loads(json_match.group(0))
                else:
                    raise ValueError("AI returned invalid JSON format.")
        except Exception as e:
            print(f"AIPromotionService parsing failed. Raw response: {raw}. Error: {e}")
            # Fallback parsing strategy
            headline = "Special Offer"
            message = "Check out our latest products and deals today!"
            
            # Simple regex fallback extraction
            headline_match = re.search(r'"headline":\s*"([^"]+)"', raw)
            message_match = re.search(r'"message":\s*"([^"]+)"', raw)
            if headline_match:
                headline = headline_match.group(1)
            if message_match:
                message = message_match.group(1)
            elif raw:
                # Fallback text splitting, completely ignoring JSON punctuation lines
                lines = []
                for l in raw.split('\n'):
                    cleaned = re.sub(r'[{}\[\]",]', '', l).strip()
                    if len(cleaned) > 2:
                        lines.append(cleaned)
                
                if lines:
                    headline = lines[0][:80]
                    if len(lines) > 1:
                        message = " ".join(lines[1:])[:255]

            plan = {
                "suggested_product_id": None,
                "promote_type": "store",
                "action_type": "visit",
                "audience_type": "near",
                "daily_budget": 10,
                "duration_days": 7,
                "headline": headline,
                "message": message,
                "insight": "AI strategy constructed using fallback parser rules."
            }
                
        # Validate suggested_product_id
        if plan.get("suggested_product_id") in ("null", "", "None"):
            plan["suggested_product_id"] = None

        # Retrieve product details if suggested_product_id is present
        product_name = None
        product_image_url = None
        if plan.get("suggested_product_id"):
            try:
                prod = UserItems.objects.filter(item_id=plan["suggested_product_id"], user=self.user).first()
                if prod:
                    product_name = prod.item_name
                    if prod.images.exists():
                        product_image_url = prod.images.first().image.url
            except Exception:
                pass
        
        plan["suggested_product_name"] = product_name
        plan["suggested_product_image"] = product_image_url
                
        return plan

