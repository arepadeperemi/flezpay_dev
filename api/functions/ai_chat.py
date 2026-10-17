import ollama
from ollama import AsyncClient
import json
from datetime import datetime
import os
import re
import asyncio
from asgiref.sync import sync_to_async


class AIChatHandler:
    def __init__(self, model=None, performance_data=None, user=None, currency="Naira (₦)"):
        self.model = model or os.environ.get('OLLAMA_MODEL', 'gemma4:latest')
        self.client = ollama
        self.user = user
        self.performance_data = performance_data or {}
        self.currency_symbol = self.performance_data.get("summary", {}).get("currency", "₦")
        self.currency = currency

    def get_tools(self):
        """
        Build and return tools callable by the AI model.
        Each tool has an explicit docstring and type hints for Ollama function calling.
        """
        if not self.user:
            return [], {}

        user = self.user

        def get_best_performing_items(limit: int = 10):
            """
            Get the top best-performing products/items by sales revenue for the store.
            
            Args:
                limit: Number of top items to return (e.g. 5, 8, 10, 15, 20).
            """
            from api.functions import ai_business_tools
            return ai_business_tools.get_best_performing_items(user=user, limit=limit)

        def get_worst_performing_items(limit: int = 10):
            """
            Get the bottom lowest-performing or worst-selling products/items by sales revenue for the store.
            
            Args:
                limit: Number of lowest performing items to return (e.g. 5, 6, 8, 10, 15).
            """
            from api.functions import ai_business_tools
            return ai_business_tools.get_worst_performing_items(user=user, limit=limit)

        def get_inventory_items(search: str = "", limit: int = 50):
            """
            Look up inventory products with their current stock levels, selling price, and cost price.
            
            Args:
                search: Optional keyword to search product name, category, or code. Leave empty ("") to retrieve all products.
                limit: Maximum number of products to return (default 50).
            """
            from api.functions import ai_business_tools
            return ai_business_tools.get_inventory_items(user=user, search=search, limit=limit)

        def get_recent_invoices(limit: int = 10):
            """
            Get recent customer invoices with cashier name, line items, and totals.
            
            Args:
                limit: Number of invoices to return (default 10).
            """
            from api.functions import ai_business_tools
            return ai_business_tools.get_invoices_with_staff(user=user, limit=limit)

        def get_department_performance():
            """
            Get revenue and employee breakdown per department for the store.
            """
            from api.functions import ai_business_tools
            return ai_business_tools.get_department_performance(user=user)

        def get_daily_sales_breakdown():
            """
            Get daily sales, transaction count, and items sold for each day of the current month.
            """
            from api.functions import ai_business_tools
            return ai_business_tools.get_daily_sales_breakdown(user=user)

        def send_invoice_followup_email(invoice_id: str = "all_overdue", custom_message: str = ""):
            """
            Send payment reminders and follow-up emails to customers with outstanding or overdue invoices.
            
            Args:
                invoice_id: Optional invoice ID (e.g. 'INV-ABC123XYZ', or 'all' to send to all debtors/overdue invoices). If empty, 'all', or 'overdue', sends to all customers with pending invoices.
                custom_message: Optional custom message or reminder note to include in the email.
            """
            from api.functions import ai_business_tools
            return ai_business_tools.send_invoice_followup_email(user=user, invoice_id=invoice_id, custom_message=custom_message)

        def send_customer_marketing_email(subject: str = "", message: str = ""):
            """
            Send promotional emails, new offers, or announcements to previous customers who have bought before.
            If subject or message are not specified, appropriate customer appreciation defaults are generated automatically.
            
            Args:
                subject: Optional subject of the email (e.g. 'Special Offer Just For You').
                message: Optional body of the promotional offer or announcement.
            """
            from api.functions import ai_business_tools
            return ai_business_tools.send_customer_marketing_email(user=user, subject=subject, message=message)

        def get_outstanding_taxes(month: int = 0, year: int = 0):
            """
            Calculate and report outstanding VAT/taxes to file based on sales invoices and user's VAT rate settings.
            If VAT is not configured (0%), it returns instructions for the user to configure VAT in Settings.
            
            Args:
                month: Optional month number (1 for Jan, 2 for Feb, ..., 12 for Dec). Leave 0 or omit to get all months year-to-date.
                year: Optional year (e.g. 2026). Defaults to current year if 0.
            """
            from api.functions import ai_business_tools
            m = month if month and month > 0 else None
            y = year if year and year > 0 else None
            return ai_business_tools.get_outstanding_taxes(user=user, month=m, year=y)

        tools_list = [
            get_best_performing_items,
            get_worst_performing_items,
            get_inventory_items,
            get_recent_invoices,
            get_department_performance,
            get_daily_sales_breakdown,
            send_invoice_followup_email,
            send_customer_marketing_email,
            get_outstanding_taxes,
        ]
        tools_map = {
            'get_best_performing_items': get_best_performing_items,
            'get_worst_performing_items': get_worst_performing_items,
            'get_inventory_items': get_inventory_items,
            'get_recent_invoices': get_recent_invoices,
            'get_department_performance': get_department_performance,
            'get_daily_sales_breakdown': get_daily_sales_breakdown,
            'send_invoice_followup_email': send_invoice_followup_email,
            'send_customer_marketing_email': send_customer_marketing_email,
            'get_outstanding_taxes': get_outstanding_taxes,
        }
        return tools_list, tools_map

    def _build_data_summary(self):
        """
        Pre-digest the performance data into plain text so the model
        can quote exact numbers without needing to parse JSON.
        Optimized for token efficiency to speed up TTFT (Time To First Token).
        """
        d = self.performance_data
        if not d:
            return "No business data available.\n"

        c = self.currency_symbol
        lines = []

        # --- Queried Period ---
        queried_period = d.get("queried_period", "Current Month")
        is_current = d.get("is_current_month", True)
        lines.append(f"=== DATA PERIOD: {queried_period} {'(CURRENT MONTH)' if is_current else '(HISTORICAL)'} ===")

        # --- Summary ---
        summary = d.get("summary", {})
        if summary:
            lines.append(f"Business: {summary.get('business_name', 'N/A')} | Bal: {c}{summary.get('current_balance', 0):,.0f} | Inv Value: {c}{summary.get('total_inventory_value', 0):,.0f}")
            lines.append(f"Products: {summary.get('total_products', 0)} | Staff: {summary.get('total_staff', 0)} (Mgrs: {summary.get('total_managers', 0)})")

        # --- Inventory Items Preview ---
        inv_items = d.get("inventory_items", [])
        if inv_items:
            lines.append("=== INVENTORY PRODUCTS (Preview) ===")
            for itm in inv_items[:5]:
                lines.append(f"  - {itm['name']} (Qty: {itm['quantity']}, Price: {c}{itm['price']:,.0f})")

        # --- Revenue ---
        rev = d.get("revenue_projections", {})
        if rev:
            lines.append("=== REVENUE ===")
            lines.append(f"This Month: {c}{rev.get('sales_this_month', 0):,.0f} | Today: {c}{rev.get('sales_today', 0):,.0f} | Yesterday: {c}{rev.get('sales_yesterday', 0):,.0f}")
            lines.append(f"Last Month: {c}{rev.get('last_month_total', 0):,.0f} | Projected: {c}{rev.get('projected_monthly_revenue', 0):,.0f} | MoM Change: {rev.get('month_over_month_change_pct', 0):.1f}%")

        # --- Invoice Summary ---
        inv = d.get("invoice_summary", {})
        if inv:
            lines.append("=== INVOICES ===")
            lines.append(f"Paid: {c}{inv.get('total_paid', 0):,.0f} | Outstanding: {c}{inv.get('total_outstanding', 0):,.0f} | Completed: {inv.get('completed_count', 0)} | Pending: {inv.get('pending_count', 0)} | Overdue: {inv.get('overdue_count', 0)}")

        # --- Best & Worst Performing Items ---
        best = d.get("best_performing_items", [])
        if best:
            lines.append("=== TOP PERFORMING ITEMS ===")
            for i, item in enumerate(best[:10], 1):
                lines.append(f"  #{i}: {item['item']} ({c}{item['total_sales']:,.0f} rev, {item['units_sold']} units)")

        worst = d.get("worst_performing_items", [])
        if worst:
            lines.append("=== BOTTOM PERFORMING ITEMS ===")
            for i, item in enumerate(worst[:10], 1):
                lines.append(f"  #{i}: {item['item']} ({c}{item['total_sales']:,.0f} rev, {item['units_sold']} units)")

        # --- Best by Department ---
        best_dept = d.get("best_performing_by_department", {})
        if best_dept:
            lines.append("=== TOP ITEMS BY DEPT ===")
            for dept, items in best_dept.items():
                dept_items = ", ".join([f"{it['item']}({c}{it['total_sales']:,.0f})" for it in items[:2]])
                lines.append(f"  {dept}: {dept_items}")

        # --- Quick Date Ranges ---
        qdr = d.get("quick_date_ranges", {})
        if qdr:
            lines.append("=== SALES BY DATE RANGE ===")
            for key, val in qdr.items():
                lines.append(f"  {key.replace('_', ' ').title()} ({val.get('period', '')}): {c}{val.get('sales', 0):,.0f} ({val.get('transactions', 0)} txn)")

        # --- Daily Sales Breakdown (Condensed Format) ---
        daily = d.get("daily_sales_breakdown", [])
        if daily:
            lines.append("=== DAILY SALES ===")
            daily_strs = [f"{day['date'][-5:]}: {c}{day['sales']:,.0f} ({day['transactions']}txn)" for day in daily]
            # Print 4 days per line to heavily reduce token length
            for i in range(0, len(daily_strs), 4):
                lines.append("  " + " | ".join(daily_strs[i:i+4]))

        # --- Department Performance ---
        depts = d.get("department_performance", [])
        if depts:
            lines.append("=== DEPT PERFORMANCE ===")
            for dept in depts:
                lines.append(f"  {dept['department']}: {c}{dept['revenue']:,.0f} rev, {dept['units_sold']} units")

        # --- Payroll ---
        pay = d.get("payroll_summary", {})
        if pay:
            lines.append("=== PAYROLL ===")
            lines.append(f"Obligation: {c}{pay.get('total_monthly_obligation', 0):,.0f} | Disbursed: {c}{pay.get('total_disbursed_so_far', 0):,.0f} | Awaiting: {c}{pay.get('awaiting_disbursement', 0):,.0f}")
            employees = pay.get("employees", [])
            if employees:
                lines.append("  Top Employees:")
                for emp in employees[:5]:
                    lines.append(f"    - {emp['name']} ({emp['job_title']}): {c}{emp['net_amount']:,.0f} status={emp['status']}")

        # --- Alerts ---
        alerts = d.get("alerts", [])
        if alerts:
            lines.append("=== ALERTS ===")
            for alert in alerts:
                lines.append(f"  [{alert['severity'].upper()}] {alert['message']}")

        # --- Overdue Invoices (Capped) ---
        overdue = d.get("overdue_invoices", [])
        if overdue:
            lines.append(f"=== OVERDUE INVOICES ({len(overdue)} total) ===")
            for oinv in overdue[:3]:
                lines.append(f"  #{oinv['invoice_id']}: {oinv['customer_name']} — {c}{oinv['total']:,.0f} ({oinv['days_overdue']}d overdue)")
            if len(overdue) > 3:
                lines.append(f"  ...and {len(overdue) - 3} more.")

        # --- Debt Summary ---
        debt = d.get("debt_summary", {})
        if debt:
            lines.append("=== DEBT SUMMARY ===")
            lines.append(f"Total: {c}{debt.get('total_outstanding', 0):,.0f}")
            aging = debt.get("aging", {})
            if aging:
                lines.append(f"  0-30d: {c}{aging.get('0_to_30_days', 0):,.0f} | 31-60d: {c}{aging.get('31_to_60_days', 0):,.0f} | 61-90d: {c}{aging.get('61_to_90_days', 0):,.0f} | 90d+: {c}{aging.get('over_90_days', 0):,.0f}")

        # --- Recent Invoices (Capped) ---
        recent = d.get("recent_invoices", [])
        if recent:
            lines.append("=== RECENT INVOICES ===")
            for rinv in recent[:3]:
                lines.append(f"  {rinv['date'][:10]} | {rinv['customer_name']} | {c}{rinv['total']:,.0f}")

        # --- Monthly Overview ---
        overview = d.get("monthly_overview", [])
        if overview:
            lines.append("=== HISTORICAL SALES ===")
            mo_strs = [f"{mo['month']}: {c}{mo['total_sales']:,.0f}" for mo in overview[-6:]]
            for i in range(0, len(mo_strs), 3):
                lines.append("  " + " | ".join(mo_strs[i:i+3]))

        # --- Tax & VAT Status ---
        tax = d.get("tax_summary", {})
        if tax:
            vat_configured = tax.get("vat_configured", False)
            vat_rate = tax.get("vat_percentage", 0)
            ytd_vat = tax.get("total_vat_payable_ytd", 0)
            if vat_configured and vat_rate > 0:
                lines.append(f"=== TAX & VAT STATUS ===\nConfigured Rate: {vat_rate}% | Total VAT to File (YTD): {c}{ytd_vat:,.2f}")
            else:
                lines.append(f"=== TAX & VAT STATUS ===\nVAT Rate: Not Set (0%). User must configure in Settings to calculate monthly taxes.")

        return "\n".join(lines)

    def get_system_prompt(self, user_context=None):
        """
        Construct a system prompt to give the AI context about FlezPay and the user.
        """
        now = datetime.now().strftime("%Y-%m-%d")
        data_summary = self._build_data_summary()

        prompt = (
            "You are the FlezPay AI Business Manager, a premium and helpful AI assistant. "
            "Your personality is professional, concise, and proactive. "
            "Since your responses are read aloud via text-to-speech, keep your answers focused and avoid long lists unless asked. "
            "Break down complex financial data into simple, actionable insights. "
            f"Current timestamp: {now}\n\n"
            "Guidelines:\n"
            "- Your responses are rendered on screen as beautiful, modern, colorful minimal cards and interactive charts for the business owner.\n"
            "- Structure your answers into clear, punchy sections: an executive insight, key figures, and recommended next actions.\n"
            f"- Use {self.currency} for all currency and financial amounts. Never use dollars.\n"
            "- Use bold markdown for key numbers and percentages (e.g. **₦1,450,000**, **+15.2%**, **3 overdue**).\n"
            "- CHARTS POLICY: Do NOT output a chart on every response. Most responses should be concise, colorful insight cards with text and metrics. Only include a chart when the user explicitly requests one (e.g. 'chart', 'graph', 'visualize', 'plot'), or when comparing multiple time periods, categories, or top items where a visual chart truly adds value. Never include a chart for greetings, simple questions, general advice, operational guidance, or single data points.\n"
            "- When a visual chart is genuinely appropriate or requested, provide a clean chart block in valid JSON:\n"
            "```chart\n"
            '{"type": "bar", "title": "Top Selling Products", "labels": ["Product A", "Product B"], "data": [120000, 95000], "color": "emerald"}\n'
            "```\n"
            "(Supported chart types: 'bar', 'line', 'doughnut'. Supported colors: 'emerald', 'violet', 'cyan', 'amber', 'rose').\n"
            "- When general operational tasks are relevant, suggest clear next steps (such as 'View Analytics', 'Check Inventory', 'Create Invoice', 'Run Payroll', 'Open POS', 'Manage Staff', 'Check Wallet', 'Configure VAT Settings').\n"
            "- NATURAL EXECUTIVE TONE & PERSONALITY (CRITICAL):\n"
            "  * You are the merchant's proactive AI Business Manager. Speak in a natural, warm, first-person voice ('I just sent...', 'I've reviewed...').\n"
            "  * NEVER speak about yourself in the third person (NEVER say 'The AI will execute...', 'The assistant has...').\n"
            "  * NEVER treat the user as a software developer. NEVER use technical developer jargon like 'Executing Tool', 'Executing tool call', 'Delivery Confirmation:', 'tool call', 'parameters', or 'placeholder values'.\n"
            "  * When taking action (like sending an email), respond naturally to the business owner:\n"
            "    Example: 'I just sent a follow-up email to all previous customers with an exclusive discount code (COMEBACK15) to welcome them back!'\n"
            "    Example: 'I just sent polite payment reminders to 3 customers for their outstanding invoices.'\n"
            "- DIRECT EMAIL ACTIONS (SEND DIRECTLY FROM CHAT — NO ACTION BUTTONS):\n"
            "  * CRITICAL MANDATORY TOOL EXECUTION RULE:\n"
            "    - When the user asks to send promotional emails, launch discounts, or re-engage previous buyers (e.g. 'send the promotional email to customers who have bought from us before', 'send promotional email', 'send discount offer'), YOU MUST IMMEDIATELY CALL `send_customer_marketing_email(subject, message)`.\n"
            "    - When the user asks to follow up on outstanding, overdue, or pending invoices, or send emails to debtors (e.g. 'send followup email to our debtors', 'send follow up email for overdue invoices', 'remind customers about invoices', 'send to all the four at once'), YOU MUST IMMEDIATELY CALL `send_invoice_followup_email(invoice_id='all', custom_message=...)`.\n"
            "    - RESEND RULE: When the user says something like 'send again', 'resend', 'send the mails again', 'we did not receive', 'they did not get it', 'not received', 'send it again' — look at the conversation history above to determine which email action was requested before, and IMMEDIATELY CALL THAT SAME TOOL AGAIN. Do not just describe what you are doing. Call the tool.\n"
            "    - NEVER assume an email campaign was already sent or is currently running from a previous conversation turn.\n"
            "    - NEVER refuse to call the tool out of false concerns about 'spam' or because the user is repeating the request. The business owner has authorized the send. Always call the tool immediately.\n"
            "    - NEVER claim or hallucinate that emails are sent, active, or running unless the tool was ACTUALLY invoked in THIS current turn and returned a successful confirmation.\n"
            "    - NEVER tell the user to navigate to the invoices or campaigns page to send emails. NEVER show or suggest action buttons for sending emails. Execute the tool immediately in chat and report the outcome in a friendly, professional way.\n"
            "- TAXES & MONTHLY VAT FILING:\n"
            "  * When the user asks about outstanding taxes, VAT, tax liability, or monthly tax filing, call `get_outstanding_taxes(month, year)`.\n"
            "  * If VAT percentage is NOT configured (0%), politely ask the user to configure their VAT percentage in Store Settings (Settings > Business Details) to determine exact monthly filing amounts, and ask what tax rate applies to their business (e.g. 7.5% in Nigeria).\n"
            "  * If VAT is configured, present a clear, itemized breakdown of gross taxable sales, the configured VAT rate, and the exact VAT amount to file for each month.\n"
            "- If the user asks a question with typos or unclear phrasing, infer their intent and answer factually.\n"
            "- Avoid using emojis.\n\n"
            "ABSOLUTE RULE — NO FABRICATION & TOOL USAGE:\n"
            "- ONLY use factual data from the BUSINESS DATA section below or from your TOOLS. NEVER invent item names, product names, figures, or department names.\n"
            "- The lists in LIVE BUSINESS DATA below are only condensed initial preview summaries.\n"
            "- Whenever the user asks for a specific count or custom list (e.g. 'give me the 6 worst', 'show top 8', 'top 10', '6 worst', 'bottom 5', '10 lowest'), ALWAYS execute your query tools (`get_best_performing_items(limit=N)` or `get_worst_performing_items(limit=N)`) to get the exact database records.\n"
            "- NEVER say that only 5 items exist just because the initial summary snippet is short — ALWAYS invoke the tool with the user's requested limit.\n"
            "- When calling query tools, if the user did not specify a month or year, immediately query for the current business period. Do NOT ask for the timeframe unless the user specifically mentions wanting historical data.\n"
            "- When the user asks for a list of all products, inventory items, stock levels, or cost prices, USE YOUR `get_inventory_items` TOOL with `search=\"\"` (empty string) to retrieve all products. Never pass 'all' or placeholder words into the search parameter.\n"
            "- When asked about a specific date or date range not covered in the summary, use the available tools to retrieve the exact records.\n\n"
            f"=== LIVE BUSINESS DATA ===\n{data_summary}\n"
        )
        if user_context:
            prompt += f"\nUser Business Context: {json.dumps(user_context)}\n"

        return prompt

    def _clean_output(self, text: str) -> str:
        """
        Safe cleaning that strips developer jargon and preserves formatting integrity
        """
        if not text:
            return text

        import re
        # Strip accidental developer prefixes or jargon
        text = re.sub(r'^(?:Executing Tool|The AI will execute|Executing tool call)[^\n]*\n?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bDelivery Confirmation:\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bExecuting tool call\.\.\.\s*', '', text, flags=re.IGNORECASE)

        # Normalize weird spacing without collapsing valid spaces
        text = text.replace("\r", "")

        return text

    async def chat_stream_async(self, messages, user_context=None):
        """
        Generates an async streaming response from Ollama with dynamic tool calling support.
        Streams thinking and content tokens in real-time immediately without blocking.
        """
        # Sanitize message history to prevent prior <think> blocks from poisoning reasoning
        clean_messages = []
        for m in messages:
            role = m.get('role', 'user')
            content = m.get('content', '')
            if role == 'assistant':
                # Strip reasoning blocks, meta comments, and thought tags from past turns
                content = re.sub(r'<think>[\s\S]*?<\/think>', '', content)
                content = re.sub(r'<!--[\s\S]*?-->', '', content)
                content = content.strip()
            if content:
                clean_messages.append({'role': role, 'content': content})

        system_message = {"role": "system", "content": self.get_system_prompt(user_context)}
        full_messages = [system_message] + clean_messages

        tools_list, tools_map = self.get_tools()
        async_client = AsyncClient()

        # Start the reasoning block
        yield "<think>\n"

        waiting_messages = [
            "Evaluating business context...\n",
            "Analyzing performance data...\n",
            "Reviewing financial history...\n",
            "Structuring recommendations...\n",
            "Finalizing insights...\n"
        ]
        msg_index = 0
        think_closed = False

        try:
            queue = asyncio.Queue()

            async def fetch_initial_stream():
                try:
                    kwargs = {
                        'model': self.model,
                        'messages': full_messages,
                        'stream': True,
                        'options': {'num_ctx': 8192, 'num_predict': 4096}
                    }
                    if tools_list:
                        kwargs['tools'] = tools_list

                    stream = await async_client.chat(**kwargs)
                    async for chunk in stream:
                        await queue.put(chunk)
                    await queue.put(None)  # EOF
                except Exception as e:
                    await queue.put(e)

            asyncio.create_task(fetch_initial_stream())

            tool_calls = []
            has_emitted_content = False
            first_turn_buffer = []
            suppress_turn1_content = False

            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=2.5)

                    if chunk is None:
                        break
                    if isinstance(chunk, Exception):
                        raise chunk

                    msg = chunk.get("message", {}) if isinstance(chunk, dict) else getattr(chunk, 'message', None)
                    tc = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, 'tool_calls', None)
                    if tc:
                        for call in tc:
                            c_name = getattr(getattr(call, 'function', None), 'name', None) or (call.get('function', {}).get('name') if isinstance(call, dict) else None)
                            c_args = getattr(getattr(call, 'function', None), 'arguments', None) or (call.get('function', {}).get('arguments') if isinstance(call, dict) else None)
                            already_present = any(
                                (getattr(getattr(existing, 'function', None), 'name', None) or (existing.get('function', {}).get('name') if isinstance(existing, dict) else None)) == c_name and
                                (getattr(getattr(existing, 'function', None), 'arguments', None) or (existing.get('function', {}).get('arguments') if isinstance(existing, dict) else None)) == c_args
                                for existing in tool_calls
                            )
                            if not already_present:
                                tool_calls.append(call)
                        suppress_turn1_content = True

                    content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, 'content', '')
                    thinking = msg.get("thinking", "") if isinstance(msg, dict) else getattr(msg, 'thinking', '')

                    # If there's thinking text, yield it inside <think>
                    if thinking:
                        yield thinking

                    # Check for tool monologue or buffer content
                    if content and not suppress_turn1_content:
                        first_turn_buffer.append(content)
                        accum_text = "".join(first_turn_buffer).lower()

                        if any(phrase in accum_text for phrase in [
                            "executing tool",
                            "the ai will execute",
                            "calling tool",
                            "executing tool call",
                            "tool call:",
                            "<tool_call",
                            "```tool"
                        ]):
                            suppress_turn1_content = True
                            first_turn_buffer.clear()
                        elif len(accum_text) > 80 and not tool_calls:
                            # Not a tool call, stream normal content
                            if not has_emitted_content:
                                has_emitted_content = True
                                if not think_closed:
                                    yield "\n</think>\n\n"
                                    think_closed = True
                                buffered_text = "".join(first_turn_buffer)
                                first_turn_buffer.clear()
                                cleaned = self._clean_output(buffered_text)
                                if cleaned:
                                    yield cleaned
                            else:
                                cleaned = self._clean_output(content)
                                if cleaned:
                                    yield cleaned

                except asyncio.TimeoutError:
                    if not think_closed:
                        if msg_index < len(waiting_messages):
                            yield waiting_messages[msg_index]
                            msg_index += 1
                        elif msg_index == len(waiting_messages):
                            yield "Still processing...\n"
                            msg_index += 1
                        else:
                            yield "<!-- heartbeat -->\n"

            # Check if user had explicit intent to execute email actions if model failed to emit tool_calls
            last_user_prompt = ""
            for m in reversed(messages):
                if m.get('role') == 'user':
                    last_user_prompt = m.get('content', '').lower().strip()
                    break

            if not tool_calls and last_user_prompt:
                # Gather recent context from last few messages
                recent_context = " ".join((m.get('content', '') or '').lower() for m in messages[-4:])

                # Check if user is confirming or commanding a send action
                is_confirmation = any(p in last_user_prompt for p in [
                    'send to all', 'send all', 'all the four', 'all four', 'all 4',
                    'send them all', 'send them', 'send it', 'send to them',
                    'yes send', 'yes, send', 'go ahead', 'proceed', 'please send',
                    'do it', 'confirm send', 'send now', 'send at once', 'all at once'
                ])

                is_promo_explicit = (
                    any(p in last_user_prompt for p in ['promotional email', 'marketing email', 'promo email', 'discount email', 'offer email']) or
                    ('send' in last_user_prompt and any(p in last_user_prompt for p in ['promotional', 'marketing', 'promo', 'discount', 'offer', 'comeback']) and any(p in last_user_prompt for p in ['email', 'mail'])) or
                    (('send' in last_user_prompt or 'email' in last_user_prompt) and any(p in last_user_prompt for p in ['customer', 'customers']) and any(p in last_user_prompt for p in ['bought', 'purchased', 'previous', 'past']))
                )
                is_promo_intent = is_promo_explicit or (is_confirmation and any(p in recent_context for p in ['promo', 'promotional', 'marketing', 'discount', 'offer', 'send_customer_marketing_email']))

                is_invoice_explicit = (
                    (
                        any(p in last_user_prompt for p in ['debtor', 'debtors', 'invoice', 'invoices', 'overdue', 'outstanding', 'unpaid']) and
                        any(p in last_user_prompt for p in ['send', 'remind', 'email', 'mail', 'followup', 'follow up', 'follow-up', 'chase', 'dispatch', 'notify'])
                    ) or
                    (
                        any(p in last_user_prompt for p in ['follow up', 'followup', 'chase', 'remind']) and
                        any(p in last_user_prompt for p in ['debtor', 'debtors', 'client', 'customer', 'defaulter'])
                    ) or
                    'send_invoice_followup_email' in last_user_prompt
                )
                is_invoice_intent = is_invoice_explicit or (is_confirmation and any(p in recent_context for p in ['invoice', 'debtor', 'overdue', 'outstanding', 'unpaid', 'send_invoice_followup_email']))

                # Detect resend intent — user says they didn't receive a previously sent email
                is_resend_intent = any(p in last_user_prompt for p in [
                    'send again', 'resend', 'send the mail again', 'send the mails again',
                    'not received', 'did not receive', 'haven\'t received', 'not get it',
                    'didn\'t get', 'send it again', 'send them again', 'try again'
                ])

                if is_resend_intent and not is_promo_intent and not is_invoice_intent:
                    # Look back at conversation history to determine which email type was last requested
                    prior_invoice_sent = False
                    prior_promo_sent = False
                    for m in messages:
                        content_lower = (m.get('content', '') or '').lower()
                        if 'send_invoice_followup_email' in content_lower or ('invoice' in content_lower and 'reminder' in content_lower) or 'debtor' in content_lower:
                            prior_invoice_sent = True
                        if 'send_customer_marketing_email' in content_lower or ('marketing' in content_lower and 'email' in content_lower):
                            prior_promo_sent = True

                    if prior_invoice_sent:
                        is_invoice_intent = True
                    if prior_promo_sent:
                        is_promo_intent = True

                # Extract any specific invoice IDs if present
                found_invoices = re.findall(r'#?INV-[A-Za-z0-9]+', last_user_prompt, re.IGNORECASE)
                target_invoice_arg = ",".join(found_invoices) if found_invoices else "all_overdue"

                if is_promo_intent:
                    tool_calls = [{
                        "function": {
                            "name": "send_customer_marketing_email",
                            "arguments": {
                                "subject": "",
                                "message": ""
                            }
                        }
                    }]
                    if is_invoice_intent:
                        tool_calls.append({
                            "function": {
                                "name": "send_invoice_followup_email",
                                "arguments": {
                                    "invoice_id": target_invoice_arg,
                                    "custom_message": "This is a polite reminder regarding your outstanding invoice. Please kindly arrange payment at your earliest convenience."
                                }
                            }
                        })
                elif is_invoice_intent:
                    tool_calls = [{
                        "function": {
                            "name": "send_invoice_followup_email",
                            "arguments": {
                                "invoice_id": target_invoice_arg,
                                "custom_message": "This is a polite reminder regarding your outstanding invoice. Please kindly arrange payment at your earliest convenience."
                            }
                        }
                    }]

            # If no tool calls were made and content was buffered, flush it now
            if not tool_calls and not suppress_turn1_content and first_turn_buffer and not has_emitted_content:
                accum_text = "".join(first_turn_buffer)
                cleaned = self._clean_output(accum_text)
                if cleaned:
                    if not think_closed:
                        yield "\n</think>\n\n"
                        think_closed = True
                    has_emitted_content = True
                    yield cleaned

            # If the model requested tool calls, execute them and stream final response
            if tool_calls:
                first_turn_buffer.clear()
                suppress_turn1_content = True

                if not think_closed:
                    is_email_tool = any("email" in (getattr(getattr(tc, 'function', None), 'name', '') or str(tc)) for tc in tool_calls)
                    yield "Sending requested emails directly...\n" if is_email_tool else "Fetching requested business records...\n"

                assistant_msg = {"role": "assistant", "content": "", "tool_calls": tool_calls}
                full_messages.append(assistant_msg)

                for tc in tool_calls:
                    fn_name = getattr(getattr(tc, 'function', None), 'name', None) or (tc.get('function', {}).get('name') if isinstance(tc, dict) else None)
                    fn_args = getattr(getattr(tc, 'function', None), 'arguments', None) or (tc.get('function', {}).get('arguments') if isinstance(tc, dict) else {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {}
                    if not isinstance(fn_args, dict):
                        fn_args = {}

                    if fn_name == 'send_invoice_followup_email' and not fn_args.get('invoice_id'):
                        fn_args['invoice_id'] = 'all_overdue'

                    if fn_name and fn_name in tools_map:
                        tool_fn = tools_map[fn_name]
                        try:
                            tool_result = await sync_to_async(tool_fn)(**fn_args)
                        except Exception as ex:
                            tool_result = {"error": str(ex)}

                        full_messages.append({
                            "role": "tool",
                            "content": json.dumps(tool_result)
                        })

                # Append executive tone directive for Turn 2
                turn2_directive = {
                    "role": "system",
                    "content": (
                        "INSTRUCTION: Speak directly to the business owner in a warm, natural first-person executive voice (e.g. 'I just sent a follow-up email to...'). "
                        "NEVER use developer jargon, system labels (DO NOT write 'Delivery Confirmation:', 'Executing Tool', or 'Tool Output:'), or third-person phrasing ('The AI will...'). "
                        "State the outcome clearly, concisely, and professionally as their business manager."
                    )
                }
                turn2_messages = full_messages + [turn2_directive]

                # Stream the final response with tool results in real-time
                second_queue = asyncio.Queue()

                async def fetch_final_stream():
                    try:
                        stream2 = await async_client.chat(
                            model=self.model,
                            messages=turn2_messages,
                            stream=True,
                            options={'num_ctx': 8192, 'num_predict': 4096}
                        )
                        async for chunk in stream2:
                            await second_queue.put(chunk)
                        await second_queue.put(None)
                    except Exception as e:
                        await second_queue.put(e)

                asyncio.create_task(fetch_final_stream())

                formatting_yielded = False
                while True:
                    try:
                        chunk = await asyncio.wait_for(second_queue.get(), timeout=2.5)
                        if chunk is None:
                            break
                        if isinstance(chunk, Exception):
                            raise chunk

                        msg2 = chunk.get("message", {}) if isinstance(chunk, dict) else getattr(chunk, 'message', None)
                        content2 = msg2.get("content", "") if isinstance(msg2, dict) else getattr(msg2, 'content', '')
                        thinking2 = msg2.get("thinking", "") if isinstance(msg2, dict) else getattr(msg2, 'thinking', '')

                        if thinking2:
                            yield thinking2

                        if content2:
                            if "<channel|>" in content2:
                                parts = content2.split("<channel|>")
                                if parts[0]:
                                    yield parts[0]
                                if not think_closed:
                                    yield "\n</think>\n\n"
                                    think_closed = True
                                if len(parts) > 1 and parts[1]:
                                    cleaned = self._clean_output(parts[1])
                                    if cleaned:
                                        yield cleaned
                            else:
                                cleaned = self._clean_output(content2)
                                if cleaned:
                                    if not think_closed:
                                        yield "\n</think>\n\n"
                                        think_closed = True
                                    yield cleaned

                    except asyncio.TimeoutError:
                        if not think_closed:
                            if not formatting_yielded:
                                yield "Formatting response...\n"
                                formatting_yielded = True
                            else:
                                yield "<!-- heartbeat -->\n"

            if not think_closed:
                yield "\n</think>\n\n"

        except Exception as e:
            if not think_closed:
                yield "\n</think>\n\n"
            yield f"Error connecting to AI: {str(e)}"

    def chat_stream(self, messages, user_context=None):
        """
        Generates a synchronous streaming response from Ollama with tool support.
        """
        clean_messages = []
        for m in messages:
            role = m.get('role', 'user')
            content = m.get('content', '')
            if role == 'assistant':
                content = re.sub(r'<think>[\s\S]*?<\/think>', '', content)
                content = re.sub(r'<!--[\s\S]*?-->', '', content)
                content = content.strip()
            if content:
                clean_messages.append({'role': role, 'content': content})

        system_message = {"role": "system", "content": self.get_system_prompt(user_context)}
        full_messages = [system_message] + clean_messages
        tools_list, tools_map = self.get_tools()

        try:
            kwargs = {
                'model': self.model,
                'messages': full_messages,
                'stream': True,
                'options': {'num_ctx': 8192, 'num_predict': 4096}
            }
            if tools_list:
                kwargs['tools'] = tools_list

            stream = self.client.chat(**kwargs)
            yield " "

            tool_calls = []

            for chunk in stream:
                msg = chunk.get("message", {}) if isinstance(chunk, dict) else getattr(chunk, 'message', None)
                tc = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, 'tool_calls', None)
                if tc:
                    tool_calls.extend(tc)

                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, 'content', '')
                if content and not tc:
                    cleaned = self._clean_output(content)
                    if cleaned:
                        yield cleaned

            if tool_calls:
                assistant_msg = {"role": "assistant", "content": "", "tool_calls": tool_calls}
                full_messages.append(assistant_msg)

                for tc in tool_calls:
                    fn_name = getattr(getattr(tc, 'function', None), 'name', None) or (tc.get('function', {}).get('name') if isinstance(tc, dict) else None)
                    fn_args = getattr(getattr(tc, 'function', None), 'arguments', None) or (tc.get('function', {}).get('arguments') if isinstance(tc, dict) else {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {}
                    if not isinstance(fn_args, dict):
                        fn_args = {}

                    if fn_name == 'send_invoice_followup_email' and not fn_args.get('invoice_id'):
                        fn_args['invoice_id'] = 'all_overdue'

                    if fn_name and fn_name in tools_map:
                        tool_fn = tools_map[fn_name]
                        try:
                            tool_result = tool_fn(**fn_args)
                        except Exception as ex:
                            tool_result = {"error": str(ex)}

                        full_messages.append({
                            "role": "tool",
                            "content": json.dumps(tool_result)
                        })

                stream2 = self.client.chat(
                    model=self.model,
                    messages=full_messages,
                    stream=True,
                    options={'num_ctx': 8192, 'num_predict': 4096}
                )
                for chunk in stream2:
                    content = chunk.get("message", {}).get("content", "") if isinstance(chunk, dict) else getattr(getattr(chunk, 'message', None), 'content', '')
                    if content:
                        cleaned = self._clean_output(content)
                        if cleaned:
                            yield cleaned

        except Exception as e:
            yield f"Error connecting to AI: {str(e)}"


