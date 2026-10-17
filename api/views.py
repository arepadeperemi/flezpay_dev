from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import logout
import json


def custom_page_not_found(request, exception=None):
    if request.is_ajax() or request.accepts('application/json'):
        return JsonResponse({'status': False}, status=404)

    return JsonResponse({'status': False}, status=404)

def signup_view(request):
    from api.models import AllowedCountries
    countries = AllowedCountries.objects.filter(is_active=True).order_by('name')
    return render(request, 'views/onboarding/signup.html', {'allowed_countries': countries})

def user_logout(request):
    logout(request)
    html = """
    <html>
    <body>
    <script>
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_data');
        localStorage.removeItem('last_data_refresh');
        window.location.href = '/login';
    </script>
    <p>Logging out...</p>
    </body>
    </html>
    """
    from django.http import HttpResponse
    return HttpResponse(html)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from django.core.files.storage import default_storage
import uuid

class LivechatAttachmentUpload(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)
    
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'status': False, 'message': 'No file uploaded'}, status=400)
            
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
        if file.content_type not in allowed_types:
            return Response({'status': False, 'message': 'Invalid file type. Only JPG, PNG, and PDF are allowed.'}, status=400)
            
        if file.size > 2 * 1024 * 1024:
            return Response({'status': False, 'message': 'File too large. Max 2MB allowed.'}, status=400)
            
        ext = file.name.split('.')[-1].lower()
        if ext == 'pdf':
            content_type = 'pdf'
        else:
            content_type = 'image'
            
        from flezpay.storage import LivechatStorage
        storage = LivechatStorage()
        filename = f"{uuid.uuid4()}.{ext}"
        saved_path = storage.save(filename, file)
        url = storage.url(saved_path)
        
        return Response({
            'status': True,
            'url': url,
            'type': content_type
        })


import requests
import decimal
from django.views.generic import TemplateView
from api.models import SubscriptionPlans, Backer
from api.templatetags.currency_tags import currency_symbol

class LandingPageView(TemplateView):
    template_name = 'views/public/index.html'

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        current_ip = self.get_client_ip()
        
        # Determine currency
        user_currency = self.request.session.get('landing_currency')
        cached_ip = self.request.session.get('landing_ip')
        
        # Check for manual override via URL (e.g., ?currency=CAD)
        override_currency = self.request.GET.get('currency')
        if override_currency:
            user_currency = override_currency.upper()
            self.request.session['landing_currency'] = user_currency
            self.request.session['landing_ip'] = current_ip
            
        elif not user_currency or cached_ip != current_ip:
            try:
                if current_ip in ['127.0.0.1', 'localhost']:
                    user_currency = 'USD'
                else:
                    res = requests.get(f'http://ip-api.com/json/{current_ip}?fields=countryCode', timeout=3)
                    if res.status_code == 200:
                        cc = res.json().get('countryCode')
                        
                        COUNTRY_CURRENCY = {
                            'US': 'USD', 'GB': 'GBP', 'NG': 'NGN', 'CA': 'CAD', 
                            'AU': 'AUD', 'ZA': 'ZAR', 'KE': 'KES', 'GH': 'GHS', 
                            'IN': 'INR', 'AE': 'AED', 'SA': 'SAR', 'CH': 'CHF'
                        }
                        
                        eurozone = ['AT', 'BE', 'CY', 'EE', 'FI', 'FR', 'DE', 'GR', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PT', 'SK', 'SI', 'ES']
                        if cc in eurozone:
                            user_currency = 'EUR'
                        else:
                            user_currency = COUNTRY_CURRENCY.get(cc, 'USD')
                    else:
                        user_currency = 'USD'
            except Exception:
                user_currency = 'USD'
                
            self.request.session['landing_currency'] = user_currency
            self.request.session['landing_ip'] = current_ip
            
        # Get exchange rate
        exchange_rate = 1.0
        if user_currency != 'NGN':
            try:
                res = requests.get('https://open.er-api.com/v6/latest/NGN', timeout=3)
                if res.status_code == 200:
                    rates = res.json().get('rates', {})
                    exchange_rate = float(rates.get(user_currency, 1.0))
            except Exception:
                pass
                
        # Fetch and process plans
        plans = list(SubscriptionPlans.objects.all())
        
        def safe_float(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0.0
                
        # Sort by lowest amount
        plans.sort(key=lambda p: safe_float(p.one_amount))
        
        processed_plans = []
        for p in plans:
            amount_val = safe_float(p.one_amount) * exchange_rate
            year_val = safe_float(p.twelve_months) * exchange_rate
            
            def format_amount(val):
                if val <= 0:
                    return "0"
                if val < 100 and user_currency in ['USD', 'EUR', 'GBP']:
                    return f"{val:,.2f}"
                return f"{val:,.0f}"
                
            processed_plans.append({
                'uniq_id': p.uniq_id,
                'plan_name': p.plan_name,
                'description': p.description,
                'one_amount': format_amount(amount_val),
                'twelve_months': format_amount(year_val),
                'one_amount_raw': safe_float(p.one_amount),
                'twelve_months_raw': safe_float(p.twelve_months),
                'is_popular': p.is_popular,
                'inventory': p.inventory,
                'ai_manager': p.ai_manager,
                'managers': getattr(p, 'managers', 1),
                'business_reporting': p.business_reporting,
                'installment_payment': p.installment_payment,
                'online_store': p.online_store,
                'cashiers': p.cashiers,
                'max_products': p.max_products,
                'payroll': p.payroll,
                'support': p.support,
                'collection_accounts': p.collection_accounts
            })
            
        context['pricing_plans'] = processed_plans
        context['plans'] = processed_plans
        context['blogs'] = BlogPost.objects.filter(is_published=True).order_by('-timestamp')[:3]
        context['total_blogs'] = BlogPost.objects.filter(is_published=True).count()
        context['local_currency_symbol'] = currency_symbol(user_currency)
        context['local_currency'] = user_currency
        context['backers'] = Backer.objects.filter(is_active=True).order_by('-created_at')
        return context


class PricingPageView(LandingPageView):
    template_name = 'views/public/pricing.html'


from django.views import View
from django.contrib import messages
from .models import BlogPost, JobPosition, JobApplication, TeamMember, SiteSettings, ContactMessage

class CareersPageView(View):
    def get(self, request):
        jobs = JobPosition.objects.filter(is_active=True)
        return render(request, 'views/public/careers.html', {'jobs': jobs})
        
    def post(self, request):
        job_id = request.POST.get('job_id')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        resume_link = request.POST.get('resume_link')
        cover_letter = request.POST.get('cover_letter')
        
        try:
            job = JobPosition.objects.get(id=job_id, is_active=True)
            JobApplication.objects.create(
                job=job,
                full_name=full_name,
                email=email,
                resume_link=resume_link,
                cover_letter=cover_letter
            )
            messages.success(request, "Your application has been submitted successfully!")
        except JobPosition.DoesNotExist:
            messages.error(request, "The selected job is no longer available.")
            
        return redirect('careers')

from django.shortcuts import get_object_or_404

class JobDetailsView(View):
    def get(self, request, slug):
        job = get_object_or_404(JobPosition, slug=slug, is_active=True)
        return render(request, 'views/public/career-details.html', {'job': job})
        
    def post(self, request, slug):
        job = get_object_or_404(JobPosition, slug=slug, is_active=True)
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        resume_link = request.POST.get('resume_link')
        cover_letter = request.POST.get('cover_letter')
        
        JobApplication.objects.create(
            job=job,
            full_name=full_name,
            email=email,
            resume_link=resume_link,
            cover_letter=cover_letter
        )
        messages.success(request, "Your application has been submitted successfully!")
        return redirect('career_details', slug=slug)

class AboutUsPageView(View):
    def get(self, request):
        team_members = TeamMember.objects.filter(is_active=True)
        departments = {
            'leadership': [],
            'engineering': [],
            'product': [],
            'marketing': [],
            'sales': []
        }
        for member in team_members:
            if member.department in departments:
                departments[member.department].append(member)
                
        backers = Backer.objects.filter(is_active=True).order_by('-created_at')
        return render(request, 'views/public/about-us.html', {'departments': departments, 'backers': backers})


class ContactPageView(View):
    def get(self, request):
        settings = SiteSettings.load()
        return render(request, 'views/public/contact.html', {'site': settings})

def submit_contact_form(request):
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json' or (request.body and request.body.strip().startswith(b'{')):
                data = json.loads(request.body)
            else:
                data = request.POST
            ContactMessage.objects.create(
                name=data.get('name', ''),
                position=data.get('position', ''),
                email=data.get('email', ''),
                phone=data.get('phone', ''),
                message=data.get('message', ''),
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'status': True, 'message': 'Contact message saved successfully.'})
            messages.success(request, 'Your message has been sent successfully!')
            return redirect('/public/contact')
        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'status': False, 'message': str(e)}, status=400)
            messages.error(request, f'Failed to send message: {e}')
            return redirect('/public/contact')
    return JsonResponse({'status': False, 'message': 'Invalid request method.'}, status=405)


def public_blogs_ajax(request):
    """AJAX endpoint for blog pagination on the landing page."""
    try:
        page = int(request.GET.get('page', 1))
        per_page = 3
        offset = (page - 1) * per_page
        total = BlogPost.objects.filter(is_published=True).count()
        posts = BlogPost.objects.filter(is_published=True).order_by('-timestamp')[offset:offset + per_page]
        has_next = (offset + per_page) < total
        has_prev = page > 1

        posts_data = []
        for post in posts:
            posts_data.append({
                'title': post.title,
                'summary': ' '.join(post.summary.split()[:12]) + ('...' if len(post.summary.split()) > 12 else '') if post.summary else '',
                'image': post.image.url if post.image else None,
                'slug': post.slug if hasattr(post, 'slug') else '',
            })

        return JsonResponse({
            'status': True,
            'posts': posts_data,
            'has_next': has_next,
            'has_prev': has_prev,
            'page': page,
            'total': total,
        })
    except Exception as e:
        return JsonResponse({'status': False, 'message': str(e)}, status=400)
